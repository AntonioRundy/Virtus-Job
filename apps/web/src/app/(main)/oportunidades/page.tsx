import { Suspense } from "react";
import { Loader2 } from "lucide-react";
import { OpportunitiesContent } from "./OpportunitiesContent";

export const metadata = {
  title: "Oportunidades",
  description: "Vagas, concursos públicos, bolsas e estágios em Angola",
};

export default function OpportunitiesPage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center min-h-[60vh]">
          <Loader2 className="h-8 w-8 animate-spin text-primary/50" />
        </div>
      }
    >
      <OpportunitiesContent />
    </Suspense>
  );
}
