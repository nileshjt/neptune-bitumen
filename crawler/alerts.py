import logging
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from models import Tender, AlertSubscription
from config import (
    DATABASE_URL, SENDGRID_API_KEY, TWILIO_ACCOUNT_SID,
    TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM,
)

logger = logging.getLogger(__name__)
engine = create_engine(DATABASE_URL)


def send_email_alert(tender: Tender, subscriber: AlertSubscription) -> bool:
    """Send email alert via SendGrid."""
    if not SENDGRID_API_KEY or not subscriber.email:
        return False
    try:
        import sendgrid
        from sendgrid.helpers.mail import Mail

        deadline_str = tender.submission_deadline.strftime("%d %b %Y") if tender.submission_deadline else "TBD"
        quantity_str = f"{tender.quantity_mt:,.0f} MT" if tender.quantity_mt else "Not specified"
        value_str = f"USD {tender.estimated_value_usd:,.0f}" if tender.estimated_value_usd else "Not disclosed"

        html_content = f"""
<html><body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">
<div style="background:#1a365d;padding:20px;color:white">
  <h2 style="margin:0">Neptune Petrochemicals — New Bitumen Tender Alert</h2>
</div>
<div style="padding:20px;border:1px solid #e2e8f0;border-top:none">
  <h3 style="color:#2d3748">{tender.title}</h3>
  <table style="width:100%;border-collapse:collapse">
    <tr><td style="padding:8px;background:#f7fafc;font-weight:bold">Buyer</td>
        <td style="padding:8px">{tender.buyer or 'N/A'}</td></tr>
    <tr><td style="padding:8px;background:#f7fafc;font-weight:bold">Country</td>
        <td style="padding:8px">{tender.country or 'N/A'}</td></tr>
    <tr><td style="padding:8px;background:#f7fafc;font-weight:bold">Region</td>
        <td style="padding:8px">{tender.region or 'N/A'}</td></tr>
    <tr><td style="padding:8px;background:#f7fafc;font-weight:bold">Quantity</td>
        <td style="padding:8px">{quantity_str}</td></tr>
    <tr><td style="padding:8px;background:#f7fafc;font-weight:bold">Grade</td>
        <td style="padding:8px">{tender.grade_spec or 'Not specified'}</td></tr>
    <tr><td style="padding:8px;background:#f7fafc;font-weight:bold">Deadline</td>
        <td style="padding:8px;color:#e53e3e;font-weight:bold">{deadline_str}</td></tr>
    <tr><td style="padding:8px;background:#f7fafc;font-weight:bold">Est. Value</td>
        <td style="padding:8px">{value_str}</td></tr>
  </table>
  <div style="margin-top:20px">
    <a href="{tender.source_url}" style="background:#2b6cb0;color:white;padding:10px 20px;text-decoration:none;border-radius:4px">
      View Tender Details
    </a>
  </div>
</div>
<div style="padding:10px 20px;color:#718096;font-size:12px">
  Neptune Petrochemicals Bid Aggregator | To unsubscribe reply with STOP
</div>
</body></html>
"""
        sg = sendgrid.SendGridAPIClient(api_key=SENDGRID_API_KEY)
        message = Mail(
            from_email="alerts@neptunepetro.com",
            to_emails=subscriber.email,
            subject=f"[Neptune] New Bitumen Tender: {tender.country} — {tender.title[:60]}",
            html_content=html_content,
        )
        response = sg.send(message)
        return response.status_code in (200, 202)
    except Exception as e:
        logger.error(f"SendGrid error: {e}")
        return False


def send_whatsapp_alert(tender: Tender, subscriber: AlertSubscription) -> bool:
    """Send WhatsApp alert via Twilio."""
    if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and subscriber.whatsapp):
        return False
    try:
        from twilio.rest import Client

        deadline_str = tender.submission_deadline.strftime("%d %b %Y") if tender.submission_deadline else "TBD"
        quantity_str = f"{tender.quantity_mt:,.0f} MT" if tender.quantity_mt else "N/A"

        body = (
            f"🛢 *New Bitumen Tender Alert*\n\n"
            f"*{tender.title[:100]}*\n\n"
            f"📍 Country: {tender.country or 'N/A'}\n"
            f"🏢 Buyer: {tender.buyer or 'N/A'}\n"
            f"📦 Quantity: {quantity_str}\n"
            f"🔬 Grade: {tender.grade_spec or 'N/A'}\n"
            f"⏰ Deadline: {deadline_str}\n\n"
            f"🔗 {tender.source_url}"
        )

        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        client.messages.create(
            from_=TWILIO_WHATSAPP_FROM,
            to=f"whatsapp:{subscriber.whatsapp}",
            body=body,
        )
        return True
    except Exception as e:
        logger.error(f"Twilio error: {e}")
        return False


def _tender_matches_subscription(tender: Tender, sub: AlertSubscription) -> bool:
    """Check if a tender matches a subscriber's preferences."""
    if sub.regions and tender.region and tender.region not in sub.regions:
        return False
    if sub.min_quantity_mt and tender.quantity_mt and tender.quantity_mt < sub.min_quantity_mt:
        return False
    if sub.keywords:
        text = f"{tender.title} {tender.grade_spec} {tender.buyer}".lower()
        if not any(kw.lower() in text for kw in sub.keywords):
            return False
    return True


def check_and_send_alerts() -> int:
    """Find new tenders and send alerts to matching subscribers."""
    sent_count = 0
    cutoff = datetime.utcnow() - timedelta(hours=1)

    with Session(engine) as session:
        new_tenders = (
            session.query(Tender)
            .filter(Tender.scraped_at >= cutoff, Tender.notified == False)
            .all()
        )
        if not new_tenders:
            logger.info("No new tenders to alert")
            return 0

        active_subs = session.query(AlertSubscription).filter_by(active=True).all()
        if not active_subs:
            logger.info("No active alert subscriptions")
            # Still mark as notified
            for t in new_tenders:
                t.notified = True
            session.commit()
            return 0

        for tender in new_tenders:
            for sub in active_subs:
                if not _tender_matches_subscription(tender, sub):
                    continue
                if sub.email:
                    ok = send_email_alert(tender, sub)
                    if ok:
                        sent_count += 1
                        logger.info(f"Email sent to {sub.email} for tender {tender.tender_id}")
                if sub.whatsapp:
                    ok = send_whatsapp_alert(tender, sub)
                    if ok:
                        sent_count += 1
                        logger.info(f"WhatsApp sent to {sub.whatsapp} for tender {tender.tender_id}")

            tender.notified = True

        session.commit()

    return sent_count
