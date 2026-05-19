import Link from "next/link";
import { ArrowRight, CheckCircle, Briefcase, GraduationCap, Building, Award } from "lucide-react";
import { Button } from "@/components/ui/button";
import { SearchBar } from "@/components/opportunities/SearchBar";

// Fetch real counts from API at render time
async function getStats() {
  try {
    const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    const res = await fetch(`${BASE}/api/v1/opportunities?per_page=1`, {
      next: { revalidate: 300 }, // cache 5 min
    });
    if (!res.ok) throw new Error("API unavailable");
    const data = await res.json();
    return { total: data.total ?? 0, available: true };
  } catch {
    return { total: 0, available: false };
  }
}

const CATEGORIES = [
  { label: "Vagas de Emprego",   icon: Briefcase,      href: "/oportunidades?type=VAGA",     color: "bg-blue-50 text-blue-700 border-blue-200" },
  { label: "Concursos Públicos", icon: Award,          href: "/oportunidades?type=CONCURSO", color: "bg-purple-50 text-purple-700 border-purple-200" },
  { label: "Bolsas de Estudo",   icon: GraduationCap,  href: "/oportunidades?type=BOLSA",    color: "bg-green-50 text-green-700 border-green-200" },
  { label: "Estágios",           icon: Building,       href: "/oportunidades?type=ESTAGIO",  color: "bg-amber-50 text-amber-700 border-amber-200" },
];

// Only features that actually work
const FEATURES = [
  "Oportunidades verificadas com indicador de confiança",
  "Fonte original sempre citada e acessível",
  "Cobertura de editais, vagas, bolsas e estágios",
];

export default async function HomePage() {
  const stats = await getStats();

  return (
    <div>
      {/* ─── Hero ─────────────────────────────────────────── */}
      <section className="relative overflow-hidden">
        <div className="gradient-primary absolute inset-0 opacity-[0.03] pointer-events-none" />
        <div className="container mx-auto px-4 max-w-7xl pt-16 pb-20">
          <div className="max-w-3xl mx-auto text-center">
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-accent/10 border border-accent/20 text-accent-600 text-sm font-medium mb-6">
              <span className="h-1.5 w-1.5 rounded-full bg-accent animate-pulse" />
              Versão Beta — em crescimento activo
            </div>

            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold text-foreground leading-tight text-balance mb-6">
              Oportunidades reais,{" "}
              <span className="text-primary">organizadas</span>{" "}
              para Angola
            </h1>

            <p className="text-lg text-muted-foreground leading-relaxed mb-8 max-w-2xl mx-auto">
              Encontre vagas, concursos públicos, bolsas e estágios num só lugar.
              Informação verificada, estruturada com IA e actualizada regularmente.
            </p>

            {/* Functional search — uses HTML form + server navigation */}
            <SearchBar className="max-w-lg mx-auto mb-8" />

            {/* Only real, working features */}
            <ul className="flex flex-col sm:flex-row flex-wrap justify-center gap-3 text-sm text-muted-foreground">
              {FEATURES.map((f) => (
                <li key={f} className="flex items-center gap-1.5">
                  <CheckCircle className="h-4 w-4 text-green-600 flex-shrink-0" />
                  {f}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      {/* ─── Stats — real data or honest beta state ───────── */}
      {stats.available && stats.total > 0 && (
        <section className="border-y border-border bg-muted/20">
          <div className="container mx-auto px-4 max-w-7xl py-10">
            <div className="flex items-center justify-center gap-2 text-sm text-muted-foreground">
              <span className="h-2 w-2 rounded-full bg-green-500 animate-pulse" />
              <span>
                <strong className="text-foreground font-semibold">{stats.total}</strong>{" "}
                oportunidades indexadas actualmente
              </span>
            </div>
          </div>
        </section>
      )}

      {/* ─── Categories ───────────────────────────────────── */}
      <section className="container mx-auto px-4 max-w-7xl py-16">
        <div className="text-center mb-10">
          <h2 className="text-2xl sm:text-3xl font-bold text-foreground mb-2">
            Explore por categoria
          </h2>
          <p className="text-muted-foreground">
            Oportunidades organizadas e com fonte verificada
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {CATEGORIES.map(({ label, icon: Icon, href, color }) => (
            <Link key={href} href={href}>
              <div className={`flex flex-col items-center gap-3 p-6 rounded-xl border ${color} hover:shadow-md transition-all duration-200 cursor-pointer`}>
                <div className="p-3 rounded-xl bg-white/80">
                  <Icon className="h-6 w-6" />
                </div>
                <span className="font-semibold text-sm text-center">{label}</span>
              </div>
            </Link>
          ))}
        </div>
      </section>

      {/* ─── CTA ─────────────────────────────────────────── */}
      <section className="gradient-primary text-white">
        <div className="container mx-auto px-4 max-w-7xl py-16 text-center">
          <h2 className="text-2xl sm:text-3xl font-bold mb-3">
            Não perca nenhuma oportunidade
          </h2>
          <p className="text-white/80 mb-8 max-w-lg mx-auto">
            Crie a sua conta gratuitamente e guarde as oportunidades que lhe interessam.
          </p>
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <Link href="/register">
              <Button variant="accent" size="lg">
                Criar conta gratuita
              </Button>
            </Link>
            <Link href="/oportunidades">
              <Button variant="outline" size="lg" className="bg-white/10 border-white/30 text-white hover:bg-white/20">
                Ver oportunidades
              </Button>
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
