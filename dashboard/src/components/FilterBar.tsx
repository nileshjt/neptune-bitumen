"use client";
import { TenderFilters } from "@/types/tender";

const REGIONS = [
  { value: "", label: "All Regions" },
  { value: "india", label: "India" },
  { value: "africa", label: "Africa" },
  { value: "southeast_asia", label: "Southeast Asia" },
];

const STATUSES = [
  { value: "", label: "All Statuses" },
  { value: "active", label: "Active" },
  { value: "awarded", label: "Awarded" },
  { value: "closed", label: "Closed" },
  { value: "cancelled", label: "Cancelled" },
];

const GRADES = ["VG-10", "VG-30", "VG-40", "PMB", "CRMB", "60/70", "80/100"];

interface FilterBarProps {
  filters: TenderFilters;
  onChange: (filters: TenderFilters) => void;
}

export default function FilterBar({ filters, onChange }: FilterBarProps) {
  const update = (patch: Partial<TenderFilters>) =>
    onChange({ ...filters, ...patch, page: 1 });

  return (
    <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-4">
      <div className="flex flex-wrap gap-3 items-end">
        {/* Search */}
        <div className="flex-1 min-w-[200px]">
          <label className="block text-xs font-medium text-gray-500 mb-1">Search</label>
          <input
            type="text"
            placeholder="Title, buyer, country…"
            value={filters.search || ""}
            onChange={(e) => update({ search: e.target.value })}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        {/* Region */}
        <div className="min-w-[150px]">
          <label className="block text-xs font-medium text-gray-500 mb-1">Region</label>
          <select
            value={filters.region || ""}
            onChange={(e) => update({ region: e.target.value || undefined })}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {REGIONS.map((r) => (
              <option key={r.value} value={r.value}>{r.label}</option>
            ))}
          </select>
        </div>

        {/* Status */}
        <div className="min-w-[130px]">
          <label className="block text-xs font-medium text-gray-500 mb-1">Status</label>
          <select
            value={filters.status || ""}
            onChange={(e) => update({ status: e.target.value || undefined })}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {STATUSES.map((s) => (
              <option key={s.value} value={s.value}>{s.label}</option>
            ))}
          </select>
        </div>

        {/* Grade */}
        <div className="min-w-[130px]">
          <label className="block text-xs font-medium text-gray-500 mb-1">Grade</label>
          <select
            value={filters.grade_spec || ""}
            onChange={(e) => update({ grade_spec: e.target.value || undefined })}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Any Grade</option>
            {GRADES.map((g) => (
              <option key={g} value={g}>{g}</option>
            ))}
          </select>
        </div>

        {/* Min Quantity */}
        <div className="min-w-[120px]">
          <label className="block text-xs font-medium text-gray-500 mb-1">Min Qty (MT)</label>
          <input
            type="number"
            placeholder="0"
            value={filters.min_quantity_mt || ""}
            onChange={(e) => update({ min_quantity_mt: e.target.value ? Number(e.target.value) : undefined })}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        {/* Max Quantity */}
        <div className="min-w-[120px]">
          <label className="block text-xs font-medium text-gray-500 mb-1">Max Qty (MT)</label>
          <input
            type="number"
            placeholder="∞"
            value={filters.max_quantity_mt || ""}
            onChange={(e) => update({ max_quantity_mt: e.target.value ? Number(e.target.value) : undefined })}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        {/* Deadline after */}
        <div className="min-w-[140px]">
          <label className="block text-xs font-medium text-gray-500 mb-1">Deadline From</label>
          <input
            type="date"
            value={filters.deadline_after || ""}
            onChange={(e) => update({ deadline_after: e.target.value || undefined })}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        {/* Clear */}
        <button
          onClick={() => onChange({})}
          className="px-4 py-2 text-sm text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
        >
          Clear
        </button>
      </div>
    </div>
  );
}
