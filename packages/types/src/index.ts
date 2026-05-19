// ─── Enums ───────────────────────────────────────────────────────────────────

export type OpportunityType = "VAGA" | "CONCURSO" | "BOLSA" | "ESTAGIO" | "FORMACAO";
export type OpportunityStatus = "ACTIVE" | "EXPIRED" | "UNVERIFIED" | "DRAFT";
export type Modality = "PRESENCIAL" | "REMOTO" | "HIBRIDO";
export type DevicePlatform = "android" | "ios";
export type TrustLevel =
  | "OFFICIAL_GOVERNMENT"
  | "OFFICIAL_COMPANY"
  | "INSTITUTIONAL"
  | "VERIFIED_PARTNER"
  | "UNVERIFIED";
export type ApplicationType = "EMAIL" | "FORM" | "DOCUMENT" | "URL" | "IN_PERSON";

// ─── Organization ─────────────────────────────────────────────────────────────

export interface Organization {
  id: string;
  name: string;
  slug: string;
  logo_url: string | null;
  is_verified: boolean;
}

export interface Category {
  category: string;
}

// ─── Opportunity ─────────────────────────────────────────────────────────────

export interface OpportunityListItem {
  id: string;
  slug: string;
  title: string;
  type: OpportunityType;
  status: OpportunityStatus;
  modality: Modality | null;
  province: string | null;
  source_name: string;
  source_logo_url: string | null;
  source_url_ok: boolean | null;
  trust_level: TrustLevel;
  trust_score: number;
  deadline: string | null;
  salary_min: number | null;
  salary_max: number | null;
  salary_currency: string;
  view_count: number;
  save_count: number;
  created_at: string;
  organization: Organization | null;
  categories: Category[];
}

export interface Opportunity extends OpportunityListItem {
  description_structured: string | null;
  requirements: string[] | null;
  benefits: string[] | null;
  tags: string[] | null;
  municipality: string | null;
  source_url: string;
  source_url_checked_at: string | null;
  contact_email: string | null;
  application_url: string | null;
  document_url: string | null;
  application_type: ApplicationType | null;
  ai_confidence_score: number | null;
  published_at: string | null;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

// ─── Auth & User ──────────────────────────────────────────────────────────────

export interface User {
  id: string;
  email: string;
  full_name: string;
  province: string | null;
  is_verified: boolean;
  is_admin: boolean;
  avatar_url: string | null;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  full_name: string;
  province?: string;
}

export interface ApiError {
  detail: string;
  status?: number;
}

// ─── Filters ─────────────────────────────────────────────────────────────────

export interface OpportunityFilters {
  page?: number;
  per_page?: number;
  type?: OpportunityType;
  province?: string;
  category?: string;
  search?: string;
  sort?: "recent" | "deadline";
}

// ─── Device / Push Notifications ─────────────────────────────────────────────

export interface DeviceRegistration {
  push_token: string;
  platform: DevicePlatform;
}

export interface PushNotificationPayload {
  type: "new_opportunity" | "deadline_reminder" | "alert_match";
  opportunity_id?: string;
  opportunity_slug?: string;
  title: string;
  body: string;
}

// ─── Alert Preferences (future) ──────────────────────────────────────────────

export interface AlertPreferences {
  types: OpportunityType[];
  provinces: string[];
  categories: string[];
  min_salary?: number;
  push_enabled: boolean;
  email_enabled: boolean;
}

// ─── Angola provinces ─────────────────────────────────────────────────────────

export const ANGOLA_PROVINCES = [
  "Bengo", "Benguela", "Bié", "Cabinda", "Cuando Cubango",
  "Cuanza Norte", "Cuanza Sul", "Cunene", "Huambo", "Huíla",
  "Luanda", "Lunda Norte", "Lunda Sul", "Malanje", "Moxico",
  "Namibe", "Uíge", "Zaire",
] as const;

export type AngolaProvince = typeof ANGOLA_PROVINCES[number];

// ─── UI Labels ────────────────────────────────────────────────────────────────

export const OPPORTUNITY_TYPE_LABELS: Record<OpportunityType, string> = {
  VAGA: "Vaga de Emprego",
  CONCURSO: "Concurso Público",
  BOLSA: "Bolsa de Estudo",
  ESTAGIO: "Estágio",
  FORMACAO: "Formação",
};

export const OPPORTUNITY_TYPE_COLORS: Record<OpportunityType, string> = {
  VAGA: "#2563EB",
  CONCURSO: "#7C3AED",
  BOLSA: "#059669",
  ESTAGIO: "#D97706",
  FORMACAO: "#0891B2",
};
