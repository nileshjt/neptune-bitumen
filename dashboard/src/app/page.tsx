"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Download, RefreshCw } from "lucide-react";
import { getTenders, buildExportUrl } from "@/lib/api";
import type { TenderFilters } from "@/types/tender";
import StatsCards from "@/components/StatsCards";
import FilterBar from "@/components/FilterBar";
import TenderTable from "@/components/TenderTable";

export default function DashboardPage() {
  const [filters, setFilters] = useState<TenderFilters>({ status: "active", page: 1, per_page: 50 });

  const { data, isLoading, isFetching, refetch } = useQuery({
    queryKey: ["tenders", filters],
    queryFn: () => getTenders(filters),
    placeholderData: (prev) => prev,
  });

  const handleFilterChange = (newFilters: TenderFilters) => {
    setFilters({ ...newFilters, page: 1, per_page: 50 });
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Bitumen Tender Dashboard</h2>
          <p className="text-sm text-gray-500 mt-0.5">
            Live aggregation across Africa, Southeast Asia &amp; India
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => refetch()}
            className="flex items-center gap-1.5 px-3 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${isFetching ? "animate-spin" : ""}`} />
            Refresh
          </button>
          <a
            href={buildExportUrl("csv", filters)}
            className="flex items-center gap-1.5 px-3 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            <Download className="w-4 h-4" />
            Export CSV
          </a>
          <a
            href={buildExportUrl("excel", filters)}
            className="flex items-center gap-1.5 px-3 py-2 text-sm bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors"
          >
            <Download className="w-4 h-4" />
            Export Excel
          </a>
        </div>
      </div>

      <StatsCards />

      <FilterBar filters={filters} onChange={handleFilterChange} />

      {isLoading ? (
        <div className="bg-white rounded-xl border border-gray-100 p-16 text-center text-gray-400">
          Loading tenders…
        </div>
      ) : data ? (
        <TenderTable
          data={data}
          page={filters.page || 1}
          onPageChange={(p) => setFilters((f) => ({ ...f, page: p }))}
        />
      ) : null}
    </div>
  );
}
