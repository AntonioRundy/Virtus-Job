"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Briefcase } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useAuthStore } from "@/store/auth.store";
import { ANGOLA_PROVINCES } from "@/lib/utils";
import type { TokenResponse, User } from "@/types";

const schema = z.object({
  full_name: z.string().min(2, "Nome deve ter no mínimo 2 caracteres"),
  email: z.string().email("Email inválido"),
  password: z.string().min(8, "Mínimo 8 caracteres"),
  province: z.string().optional(),
});

type FormData = z.infer<typeof schema>;

export default function RegisterPage() {
  const router = useRouter();
  const { setAuth } = useAuthStore();
  const [error, setError] = useState<string | null>(null);

  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<FormData>({
    resolver: zodResolver(schema),
  });

  async function onSubmit(data: FormData) {
    setError(null);
    try {
      await api.post("/auth/register", data);
      const tokens = await api.post<TokenResponse>("/auth/login", {
        email: data.email,
        password: data.password,
      });
      const user = await api.get<User>("/auth/me");
      setAuth(user, tokens.access_token, tokens.refresh_token);
      router.push("/dashboard");
    } catch (e: any) {
      setError(e.response?.data?.detail ?? "Erro ao criar conta. Tente novamente.");
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-muted/30 px-4">
      <div className="w-full max-w-md">
        <Link href="/" className="flex items-center gap-2.5 justify-center mb-8">
          <div className="gradient-primary h-10 w-10 rounded-xl flex items-center justify-center">
            <Briefcase className="h-5 w-5 text-white" />
          </div>
          <span className="font-bold text-xl text-primary">
            Virtus<span className="text-accent">Job</span>
          </span>
        </Link>

        <div className="bg-card border border-border rounded-2xl p-8 shadow-sm">
          <h1 className="text-xl font-bold text-foreground mb-1">Criar conta gratuita</h1>
          <p className="text-sm text-muted-foreground mb-6">
            Já tem conta?{" "}
            <Link href="/login" className="text-primary font-medium hover:underline">
              Entrar
            </Link>
          </p>

          {error && (
            <div className="mb-4 px-4 py-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div>
              <label className="text-sm font-medium text-foreground mb-1.5 block">Nome completo</label>
              <input
                {...register("full_name")}
                type="text"
                placeholder="Seu nome completo"
                className="w-full h-10 px-3 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
              />
              {errors.full_name && <p className="mt-1 text-xs text-red-600">{errors.full_name.message}</p>}
            </div>

            <div>
              <label className="text-sm font-medium text-foreground mb-1.5 block">Email</label>
              <input
                {...register("email")}
                type="email"
                placeholder="seu@email.com"
                className="w-full h-10 px-3 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
              />
              {errors.email && <p className="mt-1 text-xs text-red-600">{errors.email.message}</p>}
            </div>

            <div>
              <label className="text-sm font-medium text-foreground mb-1.5 block">Palavra-passe</label>
              <input
                {...register("password")}
                type="password"
                placeholder="Mínimo 8 caracteres"
                className="w-full h-10 px-3 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
              />
              {errors.password && <p className="mt-1 text-xs text-red-600">{errors.password.message}</p>}
            </div>

            <div>
              <label className="text-sm font-medium text-foreground mb-1.5 block">
                Província <span className="text-muted-foreground font-normal">(opcional)</span>
              </label>
              <select
                {...register("province")}
                className="w-full h-10 px-3 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
              >
                <option value="">Selecionar província</option>
                {ANGOLA_PROVINCES.map((p) => (
                  <option key={p} value={p}>{p}</option>
                ))}
              </select>
            </div>

            <Button type="submit" className="w-full" size="lg" loading={isSubmitting}>
              Criar conta
            </Button>

            <p className="text-xs text-muted-foreground text-center">
              Ao criar conta, aceita os nossos{" "}
              <Link href="/termos" className="underline hover:text-foreground">Termos de uso</Link>
              {" "}e{" "}
              <Link href="/privacidade" className="underline hover:text-foreground">Política de privacidade</Link>
            </p>
          </form>
        </div>
      </div>
    </div>
  );
}
