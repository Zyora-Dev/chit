import Link from "next/link";
import { Landmark } from "lucide-react";

export function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <Link href="/" className="inline-flex items-center gap-3" aria-label="zChit home">
      <span className="flex size-10 items-center justify-center rounded-xl bg-emerald-600 text-white shadow-sm shadow-emerald-900/20">
        <Landmark className="size-5" strokeWidth={2.2} />
      </span>
      {!compact && (
        <span className="flex flex-col leading-none">
          <span className="text-xl font-bold tracking-tight text-slate-950">zChit</span>
          <span className="mt-1 text-[10px] font-semibold uppercase tracking-[0.2em] text-emerald-700">Fund operations</span>
        </span>
      )}
    </Link>
  );
}
