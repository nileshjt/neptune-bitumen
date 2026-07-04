export interface Tender {
  id: number;
  tender_id: string;
  title: string;
  country: string | null;
  region: "africa" | "southeast_asia" | "india" | null;
  buyer: string | null;
  quantity_mt: number | null;
  grade_spec: string | null;
  submission_deadline: string | null;
  estimated_value_usd: number | null;
  currency: string | null;
  source_url: string | null;
  document_urls: string[];
  raw_text: string | null;
  scraped_at: string | null;
  status: "active" | "awarded" | "closed" | "cancelled" | null;
  awarded_price_usd: number | null;
}

export interface TenderFilters {
  region?: string;
  country?: string;
  status?: string;
  min_quantity_mt?: number;
  max_quantity_mt?: number;
  grade_spec?: string;
  deadline_before?: string;
  deadline_after?: string;
  search?: string;
  page?: number;
  per_page?: number;
}

export interface TenderListResponse {
  total: number;
  page: number;
  per_page: number;
  items: Tender[];
}

export interface TenderStats {
  total_active: number;
  by_region: Record<string, number>;
  by_status: Record<string, number>;
  total_estimated_value_usd: number | null;
  avg_quantity_mt: number | null;
  countries_covered: number;
  new_this_week: number;
}

export interface AlertSubscription {
  id?: number;
  email?: string;
  whatsapp?: string;
  keywords: string[];
  regions: string[];
  min_quantity_mt: number;
  active?: boolean;
}
