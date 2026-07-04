"use client";
import { useRouter } from "next/navigation";
import { format, parseISO } from "date-fns";
import { ExternalLink, ChevronLeft, ChevronRight } from "lucide-react";
import type { Tender, TenderListResponse } from "@/types/tender";

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

function Badge({ text, colorClass }: { text: string; colorClass: string }) {
  return (
    <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${colorClass}`}>
      {text}
    </span>
  );
}

function formatDeadline(iso: string | null) {
  if (!iso) return <span className="text-gray-400">—</span>;
  try {
    const d = parseISO(iso);
    const daysLeft = Math.ceil((d.getTime() - Date.now()) / 86400000);
    const color = daysLeft < 7 ? "text-red-600 font-semibold" : daysLeft < 30 ? "text-amber-600" : "text-gray-700";
    return <span className={color}>{format(d, "dd MMM yyyy")}</span>;
  } catch {
    return <span className="text-gray-400">—</span>;
  }
}

interface Props {
  data: TenderListResponse;
  page: number;
  onPageChange: (page: number) => void;
}

export default function TenderTable({ data, page, onPageChange }: Props) {
  const router = useRouter();
  const totalPages = Math.ceil(data.total / data.per_page);

  return (
    <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-100">
            <tr>
              {["Title / Buyer", "Country", "Region", "Qty (MT)", "Grade", "Deadline", "Value (USD)", "Status", ""].map(
                (h) => (
                  <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500 whitespace-nowrap">
                    {h}
                  </th>
                )
              )}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {data.items.length === 0 && (
              <tr>
                <td colSpan={9} className="text-center py-16 text-gray-400">
                  No tenders found. Adjust filters or run a crawl.
                </td>
              </tr>
            )}
            {data.items.map((t: Tender) => (
              <tr
                key={t.id}
                onClick={() => router.push(`/tenders/${t.id}`)}
                className="hover:bg-blue-50/50 cursor-pointer transition-colors"
              >
                <td className="px-4 py-3 max-w-xs">
                  <p className="font-medium text-gray-800 line-clamp-2 leading-snug">{t.title}</p>
                  {t.buyer && <p className="text-xs text-gray-400 mt-0.5 truncate">{t.buyer}</p>}
                </td>
                <td className="px-4 py-3 text-gray-600 whitespace-nowrap">{t.country || "—"}</td>
                <td className="px-4 py-3">
                  {t.region ? (
                    <Badge
                      text={t.region.replace("_", " ")}
                      colorClass={REGION_COLORS[t.region] || "bg-gray-100 text-gray-600"}
                    />
                  ) : "—"}
                </td>
                <td className="px-4 py-3 text-right text-gray-700 whitespace-nowrap">
                  {t.quantity_mt ? t.quantity_mt.toLocaleString(undefined, { maximumFractionDigits: 0 }) : "—"}
                </td>
                <td className="px-4 py-3 text-gray-600 whitespace-nowrap">{t.grade_spec || "—"}</td>
                <td className="px-4 py-3 whitespace-nowrap">{formatDeadline(t.submission_deadline)}</td>
                <td className="px-4 py-3 text-right text-gray-700 whitespace-nowrap">
                  {t.estimated_value_usd
                    ? `$${(t.estimated_value_usd / 1000).toFixed(0)}K`
                    : "—"}
                </td>
                <td className="px-4 py-3">
                  {t.status ? (
                    <Badge
                      text={t.status}
                      colorClass={STATUS_COLORS[t.status] || "bg-gray-100 text-gray-500"}
                    />
                  ) : "—"}
                </td>
                <td className="px-4 py-3">
                  {t.source_url && (
                    <a
                      href={t.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={(e) => e.stopPropagation()}
                      className="text-blue-500 hover:text-blue-700"
                    >
                      <ExternalLink className="w-4 h-4" />
                    </a>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between px-4 py-3 border-t border-gray-100">
          <p className="text-sm text-gray-500">
            Showing {(page - 1) * data.per_page + 1}–{Math.min(page * data.per_page, data.total)} of{" "}
            {data.total.toLocaleString()} tenders
          </p>
          <div className="flex gap-2">
            <button
              disabled={page <= 1}
              onClick={() => onPageChange(page - 1)}
              className="p-1.5 rounded border border-gray-200 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="px-3 py-1.5 text-sm text-gray-600">
              {page} / {totalPages}
            </span>
            <button
              disabled={page >= totalPages}
              onClick={() => onPageChange(page + 1)}
              className="p-1.5 rounded border border-gray-200 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
