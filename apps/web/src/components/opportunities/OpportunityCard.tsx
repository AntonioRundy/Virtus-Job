import Link from "next/link";
import { MapPin, Clock, ExternalLink, Bookmark, Building2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { TrustBadge } from "@/components/opportunities/TrustBadge";
import { cn, formatRelative, formatSalary, getDeadlineStatus, OPPORTUNITY_TYPES } from "@/lib/utils";
import type { OpportunityListItem } from "@/types";

interface Props {
  opportunity: OpportunityListItem;
  saved?: boolean;
}

const typeVariantMap: Record<string, string> = {
  VAGA: "vaga",
  CONCURSO: "concurso",
  BOLSA: "bolsa",
  ESTAGIO: "estagio",
  FORMACAO: "formacao",
};

export function OpportunityCard({ opportunity, saved }: Props) {
  const deadline = getDeadlineStatus(opportunity.deadline);
  const typeInfo = OPPORTUNITY_TYPES[opportunity.type];

  return (
    <Link href={`/oportunidades/${opportunity.slug}`}>
      <article className={cn(
        "group relative flex flex-col rounded-xl border border-border bg-card p-5",
        "hover:border-primary/30 hover:shadow-md transition-all duration-200",
        "animate-fade-in"
      )}>
        {/* Header */}
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="flex items-center gap-2.5 min-w-0">
            {/* Organization logo or initials */}
            <div className="flex-shrink-0 h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center">
              {opportunity.organization?.logo_url ? (
                <img
                  src={opportunity.organization.logo_url}
                  alt={opportunity.organization.name}
                  className="h-8 w-8 object-contain rounded"
                />
              ) : (
                <Building2 className="h-5 w-5 text-primary/60" />
              )}
            </div>
            <div className="min-w-0">
              <p className="text-xs text-muted-foreground truncate">
                {opportunity.organization?.name ?? opportunity.source_name}
                {opportunity.organization?.is_verified && (
                  <span className="ml-1 text-accent-500 font-medium">✓</span>
                )}
              </p>
              <p className="text-xs text-muted-foreground/60 truncate">
                {opportunity.province ?? "Angola"}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 flex-shrink-0 flex-wrap justify-end">
            <TrustBadge trustLevel={opportunity.trust_level} size="sm" />
            <Badge variant={typeVariantMap[opportunity.type] as any}>
              {typeInfo?.label ?? opportunity.type}
            </Badge>
            {saved && <Bookmark className="h-4 w-4 text-accent fill-accent" />}
          </div>
        </div>

        {/* Title */}
        <h3 className="font-semibold text-foreground leading-snug mb-2 line-clamp-2 group-hover:text-primary transition-colors">
          {opportunity.title}
        </h3>

        {/* Categories */}
        {opportunity.categories.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mb-3">
            {opportunity.categories.slice(0, 3).map((c) => (
              <span
                key={c.category}
                className="text-xs px-2 py-0.5 rounded-full bg-muted text-muted-foreground"
              >
                {c.category}
              </span>
            ))}
          </div>
        )}

        {/* Salary */}
        {(opportunity.salary_min || opportunity.salary_max) && (
          <p className="text-sm font-medium text-primary mb-3">
            {formatSalary(opportunity.salary_min, opportunity.salary_max, opportunity.salary_currency)}
          </p>
        )}

        {/* Footer */}
        <div className="flex items-center justify-between mt-auto pt-3 border-t border-border/50">
          <div className="flex items-center gap-3 text-xs text-muted-foreground">
            <span className="flex items-center gap-1">
              <Clock className="h-3.5 w-3.5" />
              {formatRelative(opportunity.created_at)}
            </span>
            {opportunity.province && (
              <span className="flex items-center gap-1">
                <MapPin className="h-3.5 w-3.5" />
                {opportunity.province}
              </span>
            )}
          </div>

          {/* Deadline badge */}
          {opportunity.deadline && (
            <span className={cn(
              "text-xs font-medium px-2 py-0.5 rounded-full",
              deadline.variant === "urgent" && "bg-red-100 text-red-700",
              deadline.variant === "soon" && "bg-amber-100 text-amber-700",
              deadline.variant === "normal" && "bg-green-100 text-green-700",
              deadline.variant === "expired" && "bg-muted text-muted-foreground line-through",
            )}>
              {deadline.label}
            </span>
          )}
        </div>

        {/* Source attribution with status indicator */}
        <div className="mt-2 flex items-center gap-1.5 text-xs text-muted-foreground/70">
          <ExternalLink className="h-3 w-3 flex-shrink-0" />
          <span className="truncate">Fonte: {opportunity.source_name}</span>
          {opportunity.source_url_ok === true && (
            <span title="Fonte verificada" className="text-green-600 flex-shrink-0">✓</span>
          )}
          {opportunity.source_url_ok === false && (
            <span title="Link indisponível" className="text-red-500 flex-shrink-0 font-medium">⚠</span>
          )}
        </div>
      </article>
    </Link>
  );
}
