// Runtime constants local ao mobile.
// Tipos vêm de @virtus/types (import type, apagados em runtime — sem impacto).
import type { OpportunityType, TrustLevel, ApplicationType } from "@virtus/types";

// ─── Opportunity types ────────────────────────────────────────────────────────

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

export const ANGOLA_PROVINCES = [
  "Bengo", "Benguela", "Bié", "Cabinda", "Cuando Cubango",
  "Cuanza Norte", "Cuanza Sul", "Cunene", "Huambo", "Huíla",
  "Luanda", "Lunda Norte", "Lunda Sul", "Malanje", "Moxico",
  "Namibe", "Uíge", "Zaire",
] as const;

// ─── Trust system — SINGLE SOURCE OF TRUTH for mobile UI ─────────────────────
// Must stay in sync with:
//   - apps/api/app/services/trust_classifier.py  (backend logic)
//   - apps/web/src/components/opportunities/TrustBadge.tsx  (web UI)

export const TRUST_COLORS: Record<TrustLevel, string> = {
  OFFICIAL_GOVERNMENT: "#1D4ED8",   // blue-700  — matches web
  OFFICIAL_COMPANY:    "#3B82F6",   // blue-500
  INSTITUTIONAL:       "#059669",   // emerald-600
  VERIFIED_PARTNER:    "#0D9488",   // teal-600
  UNVERIFIED:          "#9CA3AF",   // gray-400
};

export const TRUST_LABELS: Record<TrustLevel, string> = {
  OFFICIAL_GOVERNMENT: "Fonte Oficial — Governo",
  OFFICIAL_COMPANY:    "Empresa Oficial",
  INSTITUTIONAL:       "Fonte Institucional",
  VERIFIED_PARTNER:    "Fonte Verificada",
  UNVERIFIED:          "Fonte Não Verificada",
};

export const TRUST_SHORT_LABELS: Record<TrustLevel, string> = {
  OFFICIAL_GOVERNMENT: "Oficial GOV",
  OFFICIAL_COMPANY:    "Empresa Oficial",
  INSTITUTIONAL:       "Institucional",
  VERIFIED_PARTNER:    "Verificado",
  UNVERIFIED:          "",
};

export const TRUST_ICONS: Record<TrustLevel, string> = {
  OFFICIAL_GOVERNMENT: "shield-checkmark",
  OFFICIAL_COMPANY:    "business",
  INSTITUTIONAL:       "school",
  VERIFIED_PARTNER:    "checkmark-circle",
  UNVERIFIED:          "help-circle-outline",
};

// ─── Application types ────────────────────────────────────────────────────────

export const APPLICATION_TYPE_LABELS: Record<ApplicationType, string> = {
  EMAIL:      "Candidatar por Email",
  FORM:       "Preencher Formulário",
  DOCUMENT:   "Submeter Documentos",
  URL:        "Ver publicação original",
  IN_PERSON:  "Candidatura Presencial",
};

export const APPLICATION_TYPE_ICONS: Record<ApplicationType, string> = {
  EMAIL:      "mail",
  FORM:       "browsers",
  DOCUMENT:   "document-text",
  URL:        "open-outline",
  IN_PERSON:  "walk",
};

// ─── Source status helpers ────────────────────────────────────────────────────

/** True = link funcional ou não verificado; False = link confirmado quebrado. */
export function isSourceClickable(sourceUrlOk: boolean | null | undefined): boolean {
  return sourceUrlOk !== false;
}

/** Cor do indicador de estado da fonte. */
export function sourceStatusColor(sourceUrlOk: boolean | null | undefined): string {
  if (sourceUrlOk === true)  return "#059669"; // verde
  if (sourceUrlOk === false) return "#EF4444"; // vermelho
  return "#9CA3AF";                            // cinzento — não verificado
}

/** Label do estado da fonte. */
export function sourceStatusLabel(sourceUrlOk: boolean | null | undefined): string {
  if (sourceUrlOk === true)  return "Fonte verificada";
  if (sourceUrlOk === false) return "Link indisponível";
  return "Não verificado";
}
