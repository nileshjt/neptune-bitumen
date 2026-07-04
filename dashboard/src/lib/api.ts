import axios from "axios";
import type { Tender, TenderFilters, TenderListResponse, TenderStats, AlertSubscription } from "@/types/tender";

// In browser: use /api/ (proxied by Next.js → GCP)
// In server-side rendering: use direct API URL
const getBaseURL = () => {
  if (typeof window !== "undefined") return "/api";
  return process.env.API_URL || "http://34.57.190.1:8000";
};

const api = axios.create({ baseURL: getBaseURL() });

export async function getTenders(filters: TenderFilters = {}): Promise<TenderListResponse> {
  const params = Object.fromEntries(
    Object.entries(filters).filter(([, v]) => v !== undefined && v !== "" && v !== null)
  );
  const { data } = await api.get<TenderListResponse>("/tenders", { params });
  return data;
}

export async function getTender(id: string | number): Promise<Tender> {
  const { data } = await api.get<Tender>(`/tenders/${id}`);
  return data;
}

export async function getStats(): Promise<TenderStats> {
  const { data } = await api.get<TenderStats>("/tenders/stats");
  return data;
}

export function buildExportUrl(endpoint: "csv" | "excel", filters: TenderFilters = {}): string {
  const params = new URLSearchParams(
    Object.entries(filters)
      .filter(([, v]) => v !== undefined && v !== "" && v !== null)
      .map(([k, v]) => [k, String(v)])
  );
  return `/api/tenders/export/${endpoint}?${params.toString()}`;
}

export async function subscribeAlerts(subscription: Omit<AlertSubscription, "id">): Promise<AlertSubscription> {
  const { data } = await api.post<AlertSubscription>("/alerts/subscribe", subscription);
  return data;
}

export async function getSubscriptions(): Promise<AlertSubscription[]> {
  const { data } = await api.get<AlertSubscription[]>("/alerts/subscriptions");
  return data;
}

export async function deleteSubscription(id: number): Promise<void> {
  await api.delete(`/alerts/subscriptions/${id}`);
}
