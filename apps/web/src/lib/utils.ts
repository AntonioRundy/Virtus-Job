import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import { formatDistanceToNow, differenceInDays, format } from "date-fns";
import { ptBR } from "date-fns/locale";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(date: string | Date): string {
  const d = typeof date === "string" ? new Date(date) : date;
  return format(d, "dd 'de' MMMM 'de' yyyy", { locale: ptBR });
}

export function formatRelative(date: string | Date): string {
  const d = typeof date === "string" ? new Date(date) : date;
  return formatDistanceToNow(d, { addSuffix: true, locale: ptBR });
}

export function getDaysUntilDeadline(deadline: string | Date): number {
  const d = typeof deadline === "string" ? new Date(deadline) : deadline;
  return differenceInDays(d, new Date());
}

export function formatSalary(
  min: number | null,
  max: number | null,
  currency = "AOA"
): string {
  if (!min && !max) return "Salário não divulgado";
  const fmt = (n: number) =>
    new Intl.NumberFormat("pt-AO", {
      style: "currency",
      currency,
      maximumFractionDigits: 0,
    }).format(n);
  if (min && max) return `${fmt(min)} – ${fmt(max)}`;
  if (min) return `A partir de ${fmt(min)}`;
  return `Até ${fmt(max!)}`;
}

export function getDeadlineStatus(deadline: string | null): {
  label: string;
  variant: "urgent" | "soon" | "normal" | "expired";
} {
  if (!deadline) return { label: "Sem prazo definido", variant: "normal" };
  const days = getDaysUntilDeadline(deadline);
  if (days < 0) return { label: "Prazo encerrado", variant: "expired" };
  if (days <= 3) return { label: `${days}d restantes`, variant: "urgent" };
  if (days <= 7) return { label: `${days}d restantes`, variant: "soon" };
  return { label: `${days}d restantes`, variant: "normal" };
}

export const OPPORTUNITY_TYPES = {
  VAGA: { label: "Vaga", color: "bg-blue-100 text-blue-800" },
  CONCURSO: { label: "Concurso Público", color: "bg-purple-100 text-purple-800" },
  BOLSA: { label: "Bolsa", color: "bg-green-100 text-green-800" },
  ESTAGIO: { label: "Estágio", color: "bg-amber-100 text-amber-800" },
  FORMACAO: { label: "Formação", color: "bg-rose-100 text-rose-800" },
} as const;

export const ANGOLA_PROVINCES = [
  "Luanda", "Benguela", "Huambo", "Bié", "Malanje", "Kuanza Sul",
  "Uíge", "Zaire", "Cabinda", "Cunene", "Huíla", "Kuando Kubango",
  "Kuanza Norte", "Lunda Norte", "Lunda Sul", "Moxico", "Namibe",
  "Bengo",
] as const;
