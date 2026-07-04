"use client";
import { useQuery } from "@tanstack/react-query";
import { getStats } from "@/lib/api";
import { TrendingUp, Globe, DollarSign, Calendar } from "lucide-react";

function StatCard({
  icon: Icon,
  label,
  value,
  sub,
  color,
}: {
  icon: React.ElementType;
  label: string;
  value: string | number;
  sub?: string;
  color: string;
}) {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5 flex items-start gap-4">
      <div className={`p-3 rounded-lg ${color}`}>
        <Icon className="w-5 h-5 text-white" />
      </div>
      <div>
        <p className="text-sm text-gray-500">{label}</p>
        <p className="text-2xl font-bold text-gray-800">{value}</p>
        {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
      </div>
    </div>
  );
}

export default function StatsCards() {
  const { data: stats, isLoading } = useQuery({
    queryKey: ["stats"],
    queryFn: getStats,
  });

  if (isLoading || !stats) {
    return (
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="bg-white rounded-xl border border-gray-100 p-5 h-24 animate-pulse bg-gray-50" />
        ))}
      </div>
    );
  }

  const valueFormatted = stats.total_estimated_value_usd
    ? `$${(stats.total_estimated_value_usd / 1_000_000).toFixed(1)}M`
    : "N/A";

  const regionBreakdown = Object.entries(stats.by_region)
    .map(([r, c]) => `${r.replace("_", " ")}: ${c}`)
    .join(" · ");

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <StatCard
        icon={TrendingUp}
        label="Active Tenders"
        value={stats.total_active.toLocaleString()}
        sub={`${stats.new_this_week} new this week`}
        color="bg-blue-600"
      />
      <StatCard
        icon={Globe}
        label="Countries Covered"
        value={stats.countries_covered}
        sub={regionBreakdown}
        color="bg-emerald-600"
      />
      <StatCard
        icon={DollarSign}
        label="Total Est. Value"
        value={valueFormatted}
        sub="Combined pipeline"
        color="bg-amber-500"
      />
      <StatCard
        icon={Calendar}
        label="New This Week"
        value={stats.new_this_week}
        sub="Across all regions"
        color="bg-purple-600"
      />
    </div>
  );
}
