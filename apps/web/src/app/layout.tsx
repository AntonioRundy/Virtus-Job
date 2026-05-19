import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "Virtus Job — Oportunidades Profissionais em Angola",
    template: "%s | Virtus Job",
  },
  description:
    "Encontre vagas de emprego, concursos públicos, bolsas de estudo e estágios em Angola. Oportunidades verificadas e organizadas com inteligência artificial.",
  keywords: ["vagas angola", "concurso público angola", "emprego luanda", "bolsas angola"],
  openGraph: {
    title: "Virtus Job",
    description: "A plataforma inteligente de oportunidades profissionais em Angola",
    locale: "pt_AO",
    type: "website",
  },
  robots: { index: true, follow: true },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-AO" suppressHydrationWarning className={inter.variable}>
      <body className="min-h-screen flex flex-col font-sans">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
