import { Shield, Building2, GraduationCap, CheckCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import type { TrustLevel } from "@/types";

interface TrustConfig {
  label: string;
  shortLabel: string;
  icon: React.ComponentType<{ className?: string }>;
  className: string;
  description: string;
}

const TRUST_CONFIG: Record<Exclude<TrustLevel, "UNVERIFIED">, TrustConfig> = {
  OFFICIAL_GOVERNMENT: {
    label: "Fonte Oficial — Governo",
    shortLabel: "Oficial GOV",
    icon: Shield,
    className: "bg-blue-700 text-white border-blue-800",
    description: "Publicado directamente por um organismo oficial do Governo de Angola",
  },
  OFFICIAL_COMPANY: {
    label: "Empresa Oficial",
    shortLabel: "Empresa Oficial",
    icon: Building2,
    className: "bg-blue-500 text-white border-blue-600",
    description: "Publicado por empresa pública ou privada verificada e registada em Angola",
  },
  INSTITUTIONAL: {
    label: "Fonte Institucional",
    shortLabel: "Institucional",
    icon: GraduationCap,
    className: "bg-emerald-600 text-white border-emerald-700",
    description: "Publicado por universidade, organização internacional ou instituição reconhecida",
  },
  VERIFIED_PARTNER: {
    label: "Fonte Verificada",
    shortLabel: "Verificado",
    icon: CheckCircle,
    className: "bg-teal-600 text-white border-teal-700",
    description: "Fonte com domínio angolano verificado",
  },
};

interface Props {
  trustLevel: TrustLevel;
  size?: "sm" | "md";
  showDescription?: boolean;
}

export function TrustBadge({ trustLevel, size = "sm", showDescription = false }: Props) {
  if (trustLevel === "UNVERIFIED") return null;

  const config = TRUST_CONFIG[trustLevel];
  const Icon = config.icon;

  return (
    <div>
      <span
        className={cn(
          "inline-flex items-center gap-1 rounded-full border font-medium",
          config.className,
          size === "sm" ? "text-xs px-2 py-0.5" : "text-sm px-3 py-1"
        )}
        title={config.description}
      >
        <Icon className={size === "sm" ? "h-3 w-3" : "h-4 w-4"} />
        {size === "sm" ? config.shortLabel : config.label}
      </span>
      {showDescription && (
        <p className="text-xs text-muted-foreground mt-1.5">{config.description}</p>
      )}
    </div>
  );
}

export function TrustScoreBar({ score }: { score: number }) {
  const pct = Math.round(score);
  const color =
    pct >= 85 ? "bg-blue-600" :
    pct >= 75 ? "bg-emerald-500" :
    pct >= 55 ? "bg-teal-500" :
    "bg-muted-foreground/30";

  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 rounded-full bg-muted overflow-hidden">
        <div className={cn("h-full rounded-full transition-all", color)} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-muted-foreground w-8 text-right">{pct}%</span>
    </div>
  );
}
