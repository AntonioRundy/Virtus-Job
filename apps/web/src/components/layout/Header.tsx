"use client";

import Link from "next/link";
import { useState } from "react";
import { Menu, X, Briefcase, User, LogOut, Bell } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuthStore } from "@/store/auth.store";
import { cn } from "@/lib/utils";

const navLinks = [
  { label: "Vagas", href: "/oportunidades?type=VAGA" },
  { label: "Concursos", href: "/oportunidades?type=CONCURSO" },
  { label: "Bolsas", href: "/oportunidades?type=BOLSA" },
  { label: "Estágios", href: "/oportunidades?type=ESTAGIO" },
];

export function Header() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const { user, isAuthenticated, clearAuth } = useAuthStore();

  return (
    <header className="sticky top-0 z-50 w-full border-b border-border/60 bg-white/95 backdrop-blur supports-[backdrop-filter]:bg-white/80">
      <div className="container mx-auto px-4 max-w-7xl">
        <div className="flex h-16 items-center justify-between gap-4">
          {/* Logo */}
          <Link href="/" className="flex items-center gap-2.5 flex-shrink-0">
            <div className="gradient-primary h-8 w-8 rounded-lg flex items-center justify-center">
              <Briefcase className="h-4 w-4 text-white" />
            </div>
            <span className="font-bold text-lg text-primary tracking-tight">
              Virtus<span className="text-accent">Job</span>
            </span>
          </Link>

          {/* Desktop Nav */}
          <nav className="hidden md:flex items-center gap-1">
            {navLinks.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:bg-muted rounded-md transition-colors font-medium"
              >
                {link.label}
              </Link>
            ))}
          </nav>

          {/* Actions */}
          <div className="flex items-center gap-2">
            {isAuthenticated && user ? (
              <>
                <Button variant="ghost" size="icon" className="hidden sm:flex">
                  <Bell className="h-4 w-4" />
                </Button>
                <div className="hidden sm:flex items-center gap-2">
                  <Link href="/dashboard">
                    <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center text-primary text-sm font-semibold hover:bg-primary/20 transition-colors cursor-pointer">
                      {user.full_name[0].toUpperCase()}
                    </div>
                  </Link>
                </div>
                <Button variant="ghost" size="icon" onClick={clearAuth} className="hidden sm:flex">
                  <LogOut className="h-4 w-4" />
                </Button>
              </>
            ) : (
              <div className="hidden sm:flex items-center gap-2">
                <Link href="/login">
                  <Button variant="outline" size="sm">Entrar</Button>
                </Link>
                <Link href="/register">
                  <Button size="sm">Criar conta</Button>
                </Link>
              </div>
            )}

            {/* Mobile menu toggle */}
            <Button
              variant="ghost"
              size="icon"
              className="md:hidden"
              onClick={() => setMobileOpen(!mobileOpen)}
            >
              {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </Button>
          </div>
        </div>

        {/* Mobile Nav */}
        {mobileOpen && (
          <div className="md:hidden border-t border-border py-3 pb-4 space-y-1">
            {navLinks.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="block px-3 py-2 text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-muted rounded-md"
                onClick={() => setMobileOpen(false)}
              >
                {link.label}
              </Link>
            ))}
            {!isAuthenticated && (
              <div className="pt-2 flex flex-col gap-2">
                <Link href="/login" onClick={() => setMobileOpen(false)}>
                  <Button variant="outline" className="w-full">Entrar</Button>
                </Link>
                <Link href="/register" onClick={() => setMobileOpen(false)}>
                  <Button className="w-full">Criar conta</Button>
                </Link>
              </div>
            )}
          </div>
        )}
      </div>
    </header>
  );
}
