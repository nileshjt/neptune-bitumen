"use client";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Bell, Trash2, Plus } from "lucide-react";
import { getSubscriptions, subscribeAlerts, deleteSubscription } from "@/lib/api";
import type { AlertSubscription } from "@/types/tender";

const REGIONS = ["india", "africa", "southeast_asia"];

export default function AlertsPage() {
  const qc = useQueryClient();
  const [form, setForm] = useState<Omit<AlertSubscription, "id">>({
    email: "",
    whatsapp: "",
    keywords: [],
    regions: [],
    min_quantity_mt: 0,
  });
  const [keywordInput, setKeywordInput] = useState("");
  const [error, setError] = useState("");

  const { data: subs = [], isLoading } = useQuery({
    queryKey: ["subscriptions"],
    queryFn: getSubscriptions,
  });

  const createMutation = useMutation({
    mutationFn: subscribeAlerts,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["subscriptions"] });
      setForm({ email: "", whatsapp: "", keywords: [], regions: [], min_quantity_mt: 0 });
      setKeywordInput("");
      setError("");
    },
    onError: (e: any) => setError(e.response?.data?.detail || "Failed to subscribe"),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteSubscription,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["subscriptions"] }),
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.email && !form.whatsapp) {
      setError("Provide at least an email or WhatsApp number");
      return;
    }
    createMutation.mutate(form);
  };

  const toggleRegion = (r: string) => {
    setForm((f) => ({
      ...f,
      regions: f.regions.includes(r) ? f.regions.filter((x) => x !== r) : [...f.regions, r],
    }));
  };

  const addKeyword = () => {
    const kw = keywordInput.trim();
    if (kw && !form.keywords.includes(kw)) {
      setForm((f) => ({ ...f, keywords: [...f.keywords, kw] }));
    }
    setKeywordInput("");
  };

  return (
    <div className="max-w-2xl mx-auto space-y-8">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Alert Subscriptions</h2>
        <p className="text-sm text-gray-500 mt-1">
          Get notified via email or WhatsApp when new matching tenders are found.
        </p>
      </div>

      {/* Create form */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
        <h3 className="text-base font-semibold text-gray-800 mb-4 flex items-center gap-2">
          <Plus className="w-4 h-4" /> New Subscription
        </h3>
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && <p className="text-sm text-red-600 bg-red-50 rounded px-3 py-2">{error}</p>}

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Email</label>
              <input
                type="email"
                value={form.email}
                onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
                placeholder="you@example.com"
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">WhatsApp Number</label>
              <input
                type="tel"
                value={form.whatsapp}
                onChange={(e) => setForm((f) => ({ ...f, whatsapp: e.target.value }))}
                placeholder="+91xxxxxxxxxx"
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Regions (leave blank for all)</label>
            <div className="flex gap-2 flex-wrap">
              {REGIONS.map((r) => (
                <button
                  key={r}
                  type="button"
                  onClick={() => toggleRegion(r)}
                  className={`px-3 py-1.5 text-sm rounded-lg border transition-colors ${
                    form.regions.includes(r)
                      ? "bg-blue-600 text-white border-blue-600"
                      : "border-gray-200 text-gray-600 hover:bg-gray-50"
                  }`}
                >
                  {r.replace("_", " ")}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Keyword Filters (optional)</label>
            <div className="flex gap-2">
              <input
                type="text"
                value={keywordInput}
                onChange={(e) => setKeywordInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addKeyword())}
                placeholder="e.g. VG-30, PMB"
                className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <button type="button" onClick={addKeyword} className="px-3 py-2 bg-gray-100 rounded-lg text-sm hover:bg-gray-200">
                Add
              </button>
            </div>
            {form.keywords.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-2">
                {form.keywords.map((kw) => (
                  <span key={kw} className="flex items-center gap-1 bg-gray-100 text-gray-700 px-2 py-0.5 rounded text-xs">
                    {kw}
                    <button
                      type="button"
                      onClick={() => setForm((f) => ({ ...f, keywords: f.keywords.filter((k) => k !== kw) }))}
                      className="text-gray-400 hover:text-red-500"
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Min Quantity (MT)</label>
            <input
              type="number"
              value={form.min_quantity_mt}
              onChange={(e) => setForm((f) => ({ ...f, min_quantity_mt: Number(e.target.value) }))}
              className="w-32 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <button
            type="submit"
            disabled={createMutation.isPending}
            className="w-full py-2.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors disabled:opacity-60"
          >
            {createMutation.isPending ? "Subscribing…" : "Subscribe to Alerts"}
          </button>
        </form>
      </div>

      {/* Existing subscriptions */}
      <div>
        <h3 className="text-base font-semibold text-gray-800 mb-3 flex items-center gap-2">
          <Bell className="w-4 h-4" /> Active Subscriptions
        </h3>
        {isLoading ? (
          <p className="text-sm text-gray-400">Loading…</p>
        ) : subs.length === 0 ? (
          <p className="text-sm text-gray-400">No active subscriptions.</p>
        ) : (
          <div className="space-y-3">
            {subs.map((sub) => (
              <div key={sub.id} className="bg-white rounded-xl border border-gray-100 p-4 flex items-start justify-between">
                <div className="space-y-1 text-sm">
                  {sub.email && <p className="text-gray-800">📧 {sub.email}</p>}
                  {sub.whatsapp && <p className="text-gray-800">📱 {sub.whatsapp}</p>}
                  {sub.regions && sub.regions.length > 0 && (
                    <p className="text-gray-500">Regions: {sub.regions.join(", ")}</p>
                  )}
                  {sub.keywords && sub.keywords.length > 0 && (
                    <p className="text-gray-500">Keywords: {sub.keywords.join(", ")}</p>
                  )}
                  {sub.min_quantity_mt ? (
                    <p className="text-gray-500">Min qty: {sub.min_quantity_mt} MT</p>
                  ) : null}
                </div>
                <button
                  onClick={() => sub.id && deleteMutation.mutate(sub.id)}
                  className="text-gray-400 hover:text-red-500 transition-colors p-1"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
