"use client";
import { useQuery } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { format, parseISO } from "date-fns";
import { ArrowLeft, ExternalLink, Calendar, Package, DollarSign, MapPin, Building2 } from "lucide-react";
import { getTender } from "@/lib/api";

const REGION_COLORS: Record<string, string> = {
  india: "bg-orange-100 text-orange-700",
  africa: "bg-green-100 text-green-700",
  southeast_asia: "bg-blue-100 text-blue-700",
};

const STATUS_COLORS: Record<string, string> = {
  active: "bg-emerald-100 text-emerald-700",
  awarded: "bg-purple-100 text-purple-700",
  closed: "bg-gray-100 text-gray-500",
  cancelled: "bg-red-100 text-red-600",
};

function InfoRow({ icon: Icon, label, value }: { icon: React.ElementType; label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-start gap-3 py-3 border-b border-gray-50 last:border-0">
      <div className="p-2 bg-gray-50 rounded-lg mt-0.5">
        <Icon className="w-4 h-4 text-gray-500" />
      </div>
      <div>
        <p className="text-xs text-gray-400 font-medium">{label}</p>
        <div className="text-sm text-gray-800 mt-0.5">{value}</div>
      </div>
    </div>
  );
}

export default function TenderDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  const { data: tender, isLoading } = useQuery({
    queryKey: ["tender", id],
    queryFn: () => getTender(id),
  });

  if (isLoading) {
    return (
      <div className="max-w-3xl mx-auto py-16 text-center text-gray-400">Loading…</div>
    );
  }

  if (!tender) {
    return (
      <div className="max-w-3xl mx-auto py-16 text-center">
        <p className="text-gray-500">Tender not found.</p>
        <button onClick={() => router.back()} className="mt-4 text-blue-600 hover:underline text-sm">
          Go back
        </button>
      </div>
    );
  }

  const deadline = tender.submission_deadline
    ? (() => {
        try { return format(parseISO(tender.submission_deadline), "dd MMMM yyyy"); } catch { return tender.submission_deadline; }
      })()
    : "Not specified";

  const daysLeft = tender.submission_deadline
    ? Math.ceil((new Date(tender.submission_deadline).getTime() - Date.now()) / 86400000)
    : null;

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <button
        onClick={() => router.back()}
        className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-800 transition-colors"
      >
        <ArrowLeft className="w-4 h-4" /> Back to Dashboard
      </button>

      <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
        <div className="flex items-start justify-between gap-4 mb-4">
          <div className="flex-1">
            <div className="flex flex-wrap gap-2 mb-3">
              {tender.region && (
                <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${REGION_COLORS[tender.region] || "bg-gray-100 text-gray-600"}`}>
                  {tender.region.replace("_", " ")}
                </span>
              )}
              {tender.status && (
                <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[tender.status] || "bg-gray-100 text-gray-500"}`}>
                  {tender.status}
                </span>
              )}
            </div>
            <h2 className="text-xl font-bold text-gray-900 leading-snug">{tender.title}</h2>
            <p className="text-xs text-gray-400 mt-1">ID: {tender.tender_id}</p>
          </div>
          {tender.source_url && (
            <a
              href={tender.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 px-3 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors whitespace-nowrap shrink-0"
            >
              <ExternalLink className="w-4 h-4" />
              View Source
            </a>
          )}
        </div>

        <div className="mt-4">
          <InfoRow icon={Building2} label="Buyer / Procuring Entity" value={tender.buyer || "Not specified"} />
          <InfoRow icon={MapPin} label="Country" value={tender.country || "Not specified"} />
          <InfoRow
            icon={Package}
            label="Quantity"
            value={
              tender.quantity_mt
                ? `${tender.quantity_mt.toLocaleString()} MT`
                : "Not specified"
            }
          />
          <InfoRow icon={Package} label="Grade Specification" value={tender.grade_spec || "Not specified"} />
          <InfoRow
            icon={Calendar}
            label="Submission Deadline"
            value={
              <span className={daysLeft !== null && daysLeft < 7 ? "text-red-600 font-semibold" : ""}>
                {deadline}
                {daysLeft !== null && daysLeft > 0 && (
                  <span className="ml-2 text-xs text-gray-400">({daysLeft} days left)</span>
                )}
                {daysLeft !== null && daysLeft <= 0 && (
                  <span className="ml-2 text-xs text-red-500">(Expired)</span>
                )}
              </span>
            }
          />
          <InfoRow
            icon={DollarSign}
            label="Estimated Value"
            value={
              tender.estimated_value_usd
                ? `USD ${tender.estimated_value_usd.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
                : "Not disclosed"
            }
          />
          {tender.awarded_price_usd && (
            <InfoRow
              icon={DollarSign}
              label="Awarded Price"
              value={`USD ${tender.awarded_price_usd.toLocaleString(undefined, { maximumFractionDigits: 0 })}`}
            />
          )}
          <InfoRow
            icon={Calendar}
            label="Scraped At"
            value={tender.scraped_at ? format(parseISO(tender.scraped_at), "dd MMM yyyy HH:mm") : "—"}
          />
        </div>

        {tender.document_urls && tender.document_urls.length > 0 && (
          <div className="mt-6">
            <h3 className="text-sm font-semibold text-gray-700 mb-2">Documents</h3>
            <ul className="space-y-1">
              {tender.document_urls.map((url, i) => (
                <li key={i}>
                  <a
                    href={url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1.5 text-sm text-blue-600 hover:underline"
                  >
                    <ExternalLink className="w-3.5 h-3.5" />
                    Document {i + 1}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        )}

        {tender.raw_text && (
          <div className="mt-6">
            <h3 className="text-sm font-semibold text-gray-700 mb-2">Full Tender Details</h3>
            <pre className="bg-gray-50 rounded-lg p-4 text-xs text-gray-700 whitespace-pre-wrap break-words leading-relaxed max-h-96 overflow-y-auto border border-gray-100">
              {tender.raw_text}
            </pre>
            {tender.source_url && (
              <p className="text-xs text-gray-400 mt-2">
                Original source (login required):{" "}
                <a href={tender.source_url} target="_blank" rel="noopener noreferrer" className="text-blue-500 hover:underline">
                  {tender.source_url}
                </a>
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
