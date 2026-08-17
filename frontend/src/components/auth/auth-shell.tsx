import Link from "next/link";
import { BarChart3, CheckCircle2, MapPinned, ShieldCheck } from "lucide-react";
import { Brand } from "@/components/brand";

const benefits = [
  { icon: ShieldCheck, text: "Bank-grade operational controls" },
  { icon: MapPinned, text: "Live field collection visibility" },
  { icon: BarChart3, text: "Real-time financial intelligence" },
];

export function AuthShell({ children }: { children: React.ReactNode }) {
  return (
    <main className="min-h-screen bg-slate-50 lg:grid lg:grid-cols-[minmax(420px,0.9fr)_minmax(560px,1.1fr)]">
      <section className="relative hidden overflow-hidden bg-slate-950 px-12 py-10 lg:flex lg:flex-col xl:px-16">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_15%,rgba(16,185,129,0.2),transparent_32%),radial-gradient(circle_at_85%_80%,rgba(5,150,105,0.16),transparent_36%)]" />
        <div className="absolute inset-0 opacity-[0.07] [background-image:linear-gradient(rgba(255,255,255,.5)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,.5)_1px,transparent_1px)] [background-size:52px_52px]" />
        <div className="relative z-10">
          <Link href="/" className="inline-flex items-center gap-3 text-white">
            <span className="flex size-11 items-center justify-center rounded-xl bg-emerald-500 font-bold text-slate-950">zC</span>
            <span className="text-xl font-bold tracking-tight">zChit</span>
          </Link>
        </div>
        <div className="relative z-10 my-auto max-w-xl py-16">
          <span className="inline-flex items-center gap-2 rounded-full border border-emerald-400/30 bg-emerald-400/10 px-4 py-2 text-sm font-semibold text-emerald-300">
            <CheckCircle2 className="size-4" /> Purpose-built for chit operations
          </span>
          <h1 className="mt-8 text-4xl font-bold leading-tight tracking-tight text-white xl:text-5xl">
            Run every collection with clarity and control.
          </h1>
          <p className="mt-6 max-w-lg text-base leading-7 text-slate-200">
            One secure workspace for members, funds, field teams, payments, payroll, and compliance.
          </p>
          <div className="mt-10 space-y-5">
            {benefits.map(({ icon: Icon, text }) => (
              <div key={text} className="flex items-center gap-4 text-sm font-medium text-white">
                <span className="flex size-10 items-center justify-center rounded-xl border border-white/15 bg-white/10 text-emerald-300"><Icon className="size-5" /></span>
                {text}
              </div>
            ))}
          </div>
        </div>
        <p className="relative z-10 text-xs font-medium text-slate-300">© 2026 zChit. Secure fund operations.</p>
      </section>

      <section className="flex min-h-screen flex-col bg-white">
        <header className="flex items-center justify-between border-b border-slate-200 px-6 py-5 lg:justify-end lg:border-0 lg:px-10">
          <div className="lg:hidden"><Brand /></div>
          <Link href="/" className="text-sm font-semibold text-slate-700 transition hover:text-emerald-700">Back to website</Link>
        </header>
        <div className="flex flex-1 items-center justify-center px-6 py-12 sm:px-10 lg:px-16">
          <div className="w-full max-w-md">{children}</div>
        </div>
      </section>
    </main>
  );
}
