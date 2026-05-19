import Link from "next/link";
import { Briefcase } from "lucide-react";

export function Footer() {
  return (
    <footer className="border-t border-border bg-muted/30 mt-auto">
      <div className="container mx-auto px-4 max-w-7xl py-10">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
          {/* Brand */}
          <div className="md:col-span-1">
            <Link href="/" className="flex items-center gap-2.5 mb-3">
              <div className="gradient-primary h-7 w-7 rounded-lg flex items-center justify-center">
                <Briefcase className="h-3.5 w-3.5 text-white" />
              </div>
              <span className="font-bold text-base text-primary">
                Virtus<span className="text-accent">Job</span>
              </span>
            </Link>
            <p className="text-sm text-muted-foreground leading-relaxed">
              A plataforma inteligente de oportunidades profissionais em Angola.
            </p>
          </div>

          {/* Oportunidades */}
          <div>
            <h4 className="font-semibold text-sm text-foreground mb-3">Oportunidades</h4>
            <ul className="space-y-2 text-sm text-muted-foreground">
              {[
                ["Vagas de Emprego", "/oportunidades?type=VAGA"],
                ["Concursos Públicos", "/oportunidades?type=CONCURSO"],
                ["Bolsas de Estudo", "/oportunidades?type=BOLSA"],
                ["Estágios", "/oportunidades?type=ESTAGIO"],
                ["Formações", "/oportunidades?type=FORMACAO"],
              ].map(([label, href]) => (
                <li key={href}>
                  <Link href={href} className="hover:text-foreground transition-colors">
                    {label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* Plataforma */}
          <div>
            <h4 className="font-semibold text-sm text-foreground mb-3">Plataforma</h4>
            <ul className="space-y-2 text-sm text-muted-foreground">
              {[
                ["Sobre nós", "/sobre"],
                ["Como funciona", "/como-funciona"],
                ["Para Empresas", "/empresas"],
                ["Publicar vaga", "/publicar"],
              ].map(([label, href]) => (
                <li key={href}>
                  <Link href={href} className="hover:text-foreground transition-colors">
                    {label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* Legal */}
          <div>
            <h4 className="font-semibold text-sm text-foreground mb-3">Legal</h4>
            <ul className="space-y-2 text-sm text-muted-foreground">
              {[
                ["Termos de uso", "/termos"],
                ["Privacidade", "/privacidade"],
                ["Direitos autorais", "/direitos"],
              ].map(([label, href]) => (
                <li key={href}>
                  <Link href={href} className="hover:text-foreground transition-colors">
                    {label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="mt-8 pt-6 border-t border-border flex flex-col sm:flex-row items-center justify-between gap-3">
          <p className="text-xs text-muted-foreground">
            © {new Date().getFullYear()} Virtus Job. Todos os direitos reservados.
          </p>
          <p className="text-xs text-muted-foreground">
            Construído com propósito para Angola 🇦🇴
          </p>
        </div>
      </div>
    </footer>
  );
}
