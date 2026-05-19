"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/auth.store";
import { Loader2, Briefcase, Bookmark, Bell, User } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function DashboardPage() {
  const { user, isAuthenticated } = useAuthStore();
  const router = useRouter();

  useEffect(() => {
    if (!isAuthenticated) {
      router.push("/login");
    }
  }, [isAuthenticated, router]);

  if (!isAuthenticated || !user) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="h-8 w-8 animate-spin text-primary/50" />
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 max-w-5xl py-10">
      {/* Welcome */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-foreground">
          Bem-vindo, {user.full_name?.split(" ")[0] ?? "utilizador"}
        </h1>
        <p className="text-muted-foreground mt-1">
          Gerencie as suas oportunidades e preferências
        </p>
      </div>

      {/* Quick actions — only real ones, honest "em breve" for planned */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
        <Link href="/oportunidades">
          <div className="rounded-xl border border-border bg-card p-5 hover:border-primary/30 hover:shadow-sm transition-all cursor-pointer">
            <Briefcase className="h-6 w-6 text-primary mb-3" />
            <p className="font-semibold text-sm text-foreground">Explorar oportunidades</p>
            <p className="text-xs text-muted-foreground mt-0.5">Novas vagas e concursos</p>
          </div>
        </Link>

        <div className="rounded-xl border border-dashed border-border/50 bg-muted/20 p-5 cursor-not-allowed select-none">
          <div className="flex items-start justify-between mb-3">
            <Bookmark className="h-6 w-6 text-muted-foreground/50" />
            <span className="text-[10px] font-semibold text-muted-foreground/60 border border-border/40 px-1.5 py-0.5 rounded">EM BREVE</span>
          </div>
          <p className="font-semibold text-sm text-muted-foreground/60">Guardadas</p>
          <p className="text-xs text-muted-foreground/40 mt-0.5">Guarde oportunidades para depois</p>
        </div>

        <div className="rounded-xl border border-dashed border-border/50 bg-muted/20 p-5 cursor-not-allowed select-none">
          <div className="flex items-start justify-between mb-3">
            <Bell className="h-6 w-6 text-muted-foreground/50" />
            <span className="text-[10px] font-semibold text-muted-foreground/60 border border-border/40 px-1.5 py-0.5 rounded">EM BREVE</span>
          </div>
          <p className="font-semibold text-sm text-muted-foreground/60">Alertas</p>
          <p className="text-xs text-muted-foreground/40 mt-0.5">Notificações personalizadas</p>
        </div>

      </div>

      {/* Profile info */}
      <div className="rounded-xl border border-border bg-card p-6">
        <div className="flex items-center gap-3 mb-4">
          <User className="h-5 w-5 text-primary" />
          <h2 className="font-semibold text-foreground">O meu perfil</h2>
        </div>
        <dl className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
          <div>
            <dt className="text-muted-foreground">Nome</dt>
            <dd className="font-medium text-foreground mt-0.5">{user.full_name}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Email</dt>
            <dd className="font-medium text-foreground mt-0.5">{user.email}</dd>
          </div>
          {user.province && (
            <div>
              <dt className="text-muted-foreground">Província</dt>
              <dd className="font-medium text-foreground mt-0.5">{user.province}</dd>
            </div>
          )}
          <div>
            <dt className="text-muted-foreground">Estado da conta</dt>
            <dd className="mt-0.5">
              {user.is_verified ? (
                <span className="text-green-700 font-medium">Verificada</span>
              ) : (
                <span className="text-amber-700 font-medium">Pendente de verificação</span>
              )}
            </dd>
          </div>
        </dl>
      </div>
    </div>
  );
}
