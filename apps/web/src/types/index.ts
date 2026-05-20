// All types live in packages/types — web imports from there via tsconfig path alias.
// Existing imports of '@/types' continue to work unchanged.
export type {
  OpportunityType,
  OpportunityStatus,
  Modality,
  Organization,
  Category,
  OpportunityListItem,
  Opportunity,
  PaginatedResponse,
  User,
  TokenResponse,
  LoginRequest,
  RegisterRequest,
  ApiError,
  OpportunityFilters,
  DeviceRegistration,
  PushNotificationPayload,
  AlertPreferences,
  AngolaProvince,
  DevicePlatform,
} from "@virtus/types";
export { ANGOLA_PROVINCES, OPPORTUNITY_TYPE_LABELS, OPPORTUNITY_TYPE_COLORS } from "@virtus/types";

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

export interface ApiError {
  detail: string;
  status?: number;
}

// Query params for opportunity list
export interface OpportunityFilters {
  page?: number;
  per_page?: number;
  type?: OpportunityType;
  province?: string;
  category?: string;
  search?: string;
  sort?: "recent" | "deadline";
}
