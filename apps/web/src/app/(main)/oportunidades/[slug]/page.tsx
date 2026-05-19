"use client";

import { useParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  MapPin,
  Calendar,
  ExternalLink,
  Clock,
  Building2,
  Loader2,
  CheckCircle,
  Briefcase,
  AlertTriangle,
  XCircle,
  HelpCircle,
  Mail,
  FileText,
  MousePointerClick,
} from "lucide-react";
import { TrustBadge, TrustScoreBar } from "@/components/opportunities/TrustBadge";
import Link from "next/link";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  formatDate,
  formatRelative,
  formatSalary,
  getDeadlineStatus,
  OPPORTUNITY_TYPES,
} from "@/lib/utils";
import type { Opportunity } from "@/types";

// ─── Source status helpers ────────────────────────────────────────────────────

function SourceStatusBadge({ ok }: { ok: boolean | null | undefined }) {
  if (ok === true)
    return (
      <span className="inline-flex items-center gap-1 text-xs font-medium text-green-700 bg-green-50 border border-green-200 px-2 py-0.5 rounded-full">
        <CheckCircle className="h-3 w-3" /> Fonte verificada
      </span>
    );
  if (ok === false)
    return (
      <span className="inline-flex items-center gap-1 text-xs font-medium text-red-700 bg-red-50 border border-red-200 px-2 py-0.5 rounded-full">
        <XCircle className="h-3 w-3" /> Link indisponível
      </span>
    );
  return (
    <span className="inline-flex items-center gap-1 text-xs font-medium text-muted-foreground bg-muted px-2 py-0.5 rounded-full">
      <HelpCircle className="h-3 w-3" /> Não verificado
    </span>
  );
}

function SourceAttributionBox({ opp }: { opp: Opportunity }) {
  const isOk = opp.source_url_ok;
  const borderColor = isOk === false ? "border-red-200 bg-red-50" : "border-amber-200 bg-amber-50";
  const iconColor = isOk === false ? "text-red-500" : "text-amber-700";

  return (
    <div className={`rounded-xl border ${borderColor} p-4 flex items-start gap-3`}>
      {isOk === false ? (
        <AlertTriangle className={`h-5 w-5 ${iconColor} flex-shrink-0 mt-0.5`} />
      ) : (
        <ExternalLink className={`h-5 w-5 ${iconColor} flex-shrink-0 mt-0.5`} />
      )}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <p className="text-sm font-medium text-amber-900">Fonte original</p>
          <SourceStatusBadge ok={isOk} />
        </div>
        <p className="text-xs text-amber-700">
          Esta informação foi extraída de:{" "}
          <span className="font-medium">{opp.source_name}</span>
        </p>
        {isOk === false ? (
          <p className="text-xs text-red-700 mt-1 font-medium">
            ⚠ O link original está temporariamente indisponível. Tente mais tarde.
          </p>
        ) : (
          <a
            href={opp.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-amber-800 underline hover:text-amber-900 mt-1 block truncate"
          >
            Ver publicação original →
          </a>
        )}
      </div>
    </div>
  );
}

function ApplicationTypeIcon({ type }: { type: string | null }) {
  if (type === "EMAIL") return <Mail className="h-4 w-4" />;
  if (type === "FORM") return <MousePointerClick className="h-4 w-4" />;
  if (type === "DOCUMENT") return <FileText className="h-4 w-4" />;
  return <ExternalLink className="h-4 w-4" />;
}

function ApplicationTypeLabel({ type }: { type: string | null }) {
  const labels: Record<string, string> = {
    EMAIL: "Candidatar por Email",
    FORM: "Preencher Formulário",
    DOCUMENT: "Submeter Documentos",
    URL: "Candidatar na Fonte",
    IN_PERSON: "Candidatura Presencial",
  };
  return <>{labels[type ?? ""] ?? "Candidatar na Fonte Original"}</>;
}

function SourceCTAButton({ opp }: { opp: Opportunity }) {
  const isOk = opp.source_url_ok;
  const isBroken = isOk === false;

  if (isBroken) {
    return (
      <div className="space-y-2">
        <button
          disabled
          className="w-full h-11 rounded-lg bg-muted text-muted-foreground text-sm font-medium flex items-center justify-center gap-2 cursor-not-allowed"
        >
          <XCircle className="h-4 w-4" />
          Link indisponível
        </button>
        <p className="text-xs text-red-600 text-center">
          O link original está temporariamente indisponível.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {opp.application_type === "EMAIL" && opp.contact_email ? (
        <a href={`mailto:${opp.contact_email}`}>
          <Button className="w-full" size="lg">
            <Mail className="h-4 w-4" />
            {opp.contact_email}
          </Button>
        </a>
      ) : (
        <a
          href={opp.application_url ?? opp.source_url}
          target="_blank"
          rel="noopener noreferrer"
        >
          <Button className="w-full" size="lg">
            <ApplicationTypeIcon type={opp.application_type} />
            <ApplicationTypeLabel type={opp.application_type} />
          </Button>
        </a>
      )}
      <p className="text-xs text-muted-foreground text-center">
        Será redirecionado para {opp.source_name}
        {isOk === true && (
          <span className="ml-1 text-green-600 font-medium">✓</span>
        )}
      </p>
    </div>
  );
}

const typeVariantMap: Record<string, string> = {
  VAGA: "vaga",
  CONCURSO: "concurso",
  BOLSA: "bolsa",
  ESTAGIO: "estagio",
  FORMACAO: "formacao",
};

export default function OpportunityDetailPage() {
  const { slug } = useParams<{ slug: string }>();
  const router = useRouter();

  const { data: opp, isLoading, isError } = useQuery({
    queryKey: ["opportunity", slug],
    queryFn: () => api.get<Opportunity>(`/opportunities/${slug}`),
    enabled: !!slug,
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="h-8 w-8 animate-spin text-primary/50" />
      </div>
    );
  }

  if (isError || !opp) {
    return (
      <div className="container mx-auto px-4 max-w-4xl py-16 text-center">
        <p className="text-muted-foreground text-lg mb-4">Oportunidade não encontrada.</p>
        <Button variant="outline" onClick={() => router.push("/oportunidades")}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          Voltar às oportunidades
        </Button>
      </div>
    );
  }

  const deadline = getDeadlineStatus(opp.deadline);
  const typeInfo = OPPORTUNITY_TYPES[opp.type as keyof typeof OPPORTUNITY_TYPES];

  return (
    <div className="container mx-auto px-4 max-w-4xl py-8">
      {/* Back */}
      <button
        onClick={() => router.back()}
        className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground mb-6 transition-colors"
      >
        <ArrowLeft className="h-4 w-4" />
        Voltar
      </button>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* ─── Main Content ──────────────────────────── */}
        <div className="lg:col-span-2 space-y-6">
          {/* Header */}
          <div className="rounded-xl border border-border bg-card p-6">
            <div className="flex items-start gap-4 mb-4">
              <div className="flex-shrink-0 h-14 w-14 rounded-xl bg-primary/10 flex items-center justify-center">
                {opp.organization?.logo_url ? (
                  <img
                    src={opp.organization.logo_url}
                    alt={opp.organization.name}
                    className="h-10 w-10 object-contain rounded"
                  />
                ) : (
                  <Building2 className="h-7 w-7 text-primary/60" />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex flex-wrap items-center gap-2 mb-2">
                  <Badge variant={typeVariantMap[opp.type] as "vaga"}>
                    {typeInfo?.label ?? opp.type}
                  </Badge>
                  {opp.organization?.is_verified && (
                    <span className="flex items-center gap-1 text-xs text-green-700 font-medium">
                      <CheckCircle className="h-3.5 w-3.5" />
                      Verificado
                    </span>
                  )}
                </div>
                <h1 className="text-xl font-bold text-foreground leading-tight">{opp.title}</h1>
                <p className="text-sm text-muted-foreground mt-1">
                  {opp.organization?.name ?? opp.source_name}
                </p>
              </div>
            </div>

            {/* Meta info */}
            <div className="flex flex-wrap gap-4 text-sm text-muted-foreground pt-4 border-t border-border">
              {opp.province && (
                <span className="flex items-center gap-1.5">
                  <MapPin className="h-4 w-4" />
                  {opp.province}
                  {opp.municipality && `, ${opp.municipality}`}
                </span>
              )}
              {opp.modality && (
                <span className="flex items-center gap-1.5">
                  <Briefcase className="h-4 w-4" />
                  {opp.modality}
                </span>
              )}
              <span className="flex items-center gap-1.5">
                <Clock className="h-4 w-4" />
                Publicado {formatRelative(opp.created_at)}
              </span>
            </div>
          </div>

          {/* Description */}
          {opp.description_structured && (
            <div className="rounded-xl border border-border bg-card p-6">
              <h2 className="font-semibold text-foreground mb-3">Descrição</h2>
              <p className="text-sm text-muted-foreground leading-relaxed whitespace-pre-wrap">
                {opp.description_structured}
              </p>
            </div>
          )}

          {/* Requirements */}
          {opp.requirements && opp.requirements.length > 0 && (
            <div className="rounded-xl border border-border bg-card p-6">
              <h2 className="font-semibold text-foreground mb-3">Requisitos</h2>
              <ul className="space-y-2">
                {opp.requirements.map((req, i) => (
                  <li key={i} className="flex items-start gap-2.5 text-sm text-muted-foreground">
                    <CheckCircle className="h-4 w-4 text-primary flex-shrink-0 mt-0.5" />
                    {req}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Benefits */}
          {opp.benefits && opp.benefits.length > 0 && (
            <div className="rounded-xl border border-border bg-card p-6">
              <h2 className="font-semibold text-foreground mb-3">Benefícios</h2>
              <ul className="space-y-2">
                {opp.benefits.map((benefit, i) => (
                  <li key={i} className="flex items-start gap-2.5 text-sm text-muted-foreground">
                    <CheckCircle className="h-4 w-4 text-green-600 flex-shrink-0 mt-0.5" />
                    {benefit}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Source attribution */}
          <SourceAttributionBox opp={opp} />
        </div>

        {/* ─── Sidebar ───────────────────────────────── */}
        <div className="space-y-4">
          {/* Apply CTA */}
          <div className="rounded-xl border border-border bg-card p-5">
            <h3 className="font-semibold text-foreground mb-4">Candidatar-se</h3>

            {opp.deadline && (
              <div className="mb-4">
                <p className="text-xs text-muted-foreground mb-1">Prazo</p>
                <div className="flex items-center gap-2">
                  <Calendar className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm font-medium">{formatDate(opp.deadline)}</span>
                </div>
                <span
                  className={`mt-1.5 inline-block text-xs font-medium px-2 py-0.5 rounded-full ${
                    deadline.variant === "urgent"
                      ? "bg-red-100 text-red-700"
                      : deadline.variant === "soon"
                        ? "bg-amber-100 text-amber-700"
                        : deadline.variant === "expired"
                          ? "bg-muted text-muted-foreground"
                          : "bg-green-100 text-green-700"
                  }`}
                >
                  {deadline.label}
                </span>
              </div>
            )}

            {(opp.salary_min || opp.salary_max) && (
              <div className="mb-4">
                <p className="text-xs text-muted-foreground mb-1">Remuneração</p>
                <p className="text-sm font-semibold text-primary">
                  {formatSalary(opp.salary_min, opp.salary_max, opp.salary_currency)}
                </p>
              </div>
            )}

            <SourceCTAButton opp={opp} />
          </div>

          {/* Trust Panel */}
          <div className="rounded-xl border border-border bg-card p-5">
            <h3 className="font-semibold text-foreground mb-3 text-sm">Credibilidade da Fonte</h3>
            <div className="flex items-center gap-2 mb-3">
              <TrustBadge trustLevel={opp.trust_level as any} size="md" showDescription />
            </div>
            <TrustScoreBar score={opp.trust_score} />
            <p className="text-xs text-muted-foreground mt-2">
              Score de confiança: {Math.round(opp.trust_score)}/100
            </p>
          </div>

          {/* Categories */}
          {opp.categories.length > 0 && (
            <div className="rounded-xl border border-border bg-card p-5">
              <h3 className="font-semibold text-foreground mb-3 text-sm">Categorias</h3>
              <div className="flex flex-wrap gap-2">
                {opp.categories.map((c) => (
                  <Link
                    key={c.category}
                    href={`/oportunidades?category=${encodeURIComponent(c.category)}`}
                    className="text-xs px-2.5 py-1 rounded-full bg-muted hover:bg-primary/10 hover:text-primary text-muted-foreground transition-colors"
                  >
                    {c.category}
                  </Link>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
