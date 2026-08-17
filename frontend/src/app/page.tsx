import Link from "next/link";
import {
  ArrowRight,
  BadgeIndianRupee,
  BarChart3,
  BellRing,
  Check,
  ChevronRight,
  ClipboardCheck,
  MapPinned,
  ShieldCheck,
  Smartphone,
  Sparkles,
  UsersRound,
} from "lucide-react";
import { Brand } from "@/components/brand";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

const capabilities = [
  { icon: UsersRound, title: "Member operations", description: "Onboard members, manage KYC records, nominations, and complete relationship histories." },
  { icon: BadgeIndianRupee, title: "Chit & collections", description: "Structure funds, track installments, auctions, dividends, payouts, and overdue collections." },
  { icon: MapPinned, title: "Field intelligence", description: "Assign collection routes and monitor agent location, visits, and collection performance." },
  { icon: BellRing, title: "Smart communication", description: "Keep members informed through automated WhatsApp and email payment notifications." },
  { icon: ClipboardCheck, title: "Payroll & workforce", description: "Run attendance, incentives, payroll, and agent accountability from one workspace." },
  { icon: BarChart3, title: "Decision-ready reports", description: "See cash flow, liabilities, member health, and operational risk in real time." },
];

const metrics = [
  ["₹24.8L", "Collections tracked"],
  ["98.4%", "On-time recovery"],
  ["1,284", "Active members"],
];

export default function Home() {
  return (
    <main className="min-h-screen overflow-hidden bg-white">
      <header className="sticky top-0 z-50 border-b border-slate-200/80 bg-white/90 backdrop-blur-xl">
        <div className="mx-auto flex h-20 max-w-7xl items-center justify-between px-6 lg:px-8">
          <Brand />
          <nav className="hidden items-center gap-8 lg:flex">
            <a href="#platform" className="text-sm font-semibold text-slate-700 hover:text-emerald-700">Platform</a>
            <a href="#operations" className="text-sm font-semibold text-slate-700 hover:text-emerald-700">Operations</a>
            <a href="#security" className="text-sm font-semibold text-slate-700 hover:text-emerald-700">Security</a>
          </nav>
          <div className="flex items-center gap-3">
            <Button nativeButton={false} variant="ghost" className="h-10 px-4 font-semibold text-slate-800" render={<Link href="/login" />}>Sign in</Button>
            <Button nativeButton={false} className="h-10 bg-emerald-600 px-5 font-semibold text-white shadow-sm hover:bg-emerald-700" render={<Link href="/register" />}>Get started <ArrowRight className="size-4" /></Button>
          </div>
        </div>
      </header>

      <section className="relative border-b border-slate-200 bg-slate-50">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_75%_25%,rgba(16,185,129,0.14),transparent_32%),radial-gradient(circle_at_12%_75%,rgba(5,150,105,0.09),transparent_28%)]" />
        <div className="relative mx-auto grid max-w-7xl gap-16 px-6 py-20 lg:grid-cols-[1.02fr_.98fr] lg:px-8 lg:py-28">
          <div className="flex flex-col justify-center">
            <Badge variant="outline" className="mb-7 w-fit border-emerald-200 bg-emerald-50 px-3 py-1.5 text-emerald-800">
              <Sparkles className="size-3.5" /> Built for modern chit fund businesses
            </Badge>
            <h1 className="max-w-3xl text-5xl font-bold leading-[1.08] tracking-[-0.04em] text-slate-950 sm:text-6xl lg:text-7xl">
              Every chit operation. <span className="text-emerald-600">One clear system.</span>
            </h1>
            <p className="mt-7 max-w-2xl text-lg leading-8 text-slate-600 sm:text-xl">
              Replace fragmented registers and follow-ups with a secure operating platform for funds, members, collections, field teams, payroll, and payments.
            </p>
            <div className="mt-9 flex flex-col gap-3 sm:flex-row">
              <Button nativeButton={false} size="lg" className="h-12 bg-emerald-600 px-6 text-base font-semibold text-white shadow-lg shadow-emerald-900/10 hover:bg-emerald-700" render={<Link href="/register" />}>Create your workspace <ArrowRight className="size-4" /></Button>
              <Button nativeButton={false} size="lg" variant="outline" className="h-12 border-slate-300 px-6 text-base font-semibold text-slate-900" render={<a href="#platform" />}>Explore the platform</Button>
            </div>
            <div className="mt-8 flex flex-wrap gap-x-6 gap-y-3 text-sm font-medium text-slate-700">
              {["Fast onboarding", "Role-based access", "Audit-ready records"].map((item) => <span key={item} className="flex items-center gap-2"><Check className="size-4 text-emerald-600" />{item}</span>)}
            </div>
          </div>

          <div className="relative flex items-center justify-center">
            <div className="absolute -inset-10 rounded-full bg-emerald-400/10 blur-3xl" />
            <Card className="relative w-full overflow-visible border border-slate-200 bg-white p-2 shadow-2xl shadow-slate-900/10 ring-0">
              <CardContent className="overflow-visible p-4 sm:p-6">
                <div className="flex items-center justify-between border-b border-slate-200 pb-5">
                  <div><p className="text-sm font-semibold text-slate-950">Operations overview</p><p className="mt-1 text-xs font-medium text-slate-500">August 2026</p></div>
                  <span className="rounded-full bg-emerald-50 px-3 py-1.5 text-xs font-bold text-emerald-700">Live</span>
                </div>
                <div className="grid gap-3 py-5 sm:grid-cols-3">
                  {metrics.map(([value, label]) => <div key={label} className="rounded-xl border border-slate-200 bg-slate-50 p-4"><p className="text-xl font-bold text-slate-950">{value}</p><p className="mt-1 text-xs font-medium leading-5 text-slate-600">{label}</p></div>)}
                </div>
                <div className="rounded-2xl bg-slate-950 p-5 text-white">
                  <div className="flex items-center justify-between"><div><p className="text-sm font-semibold">Monthly collection trend</p><p className="mt-1 text-xs text-slate-300">Across all active groups</p></div><BarChart3 className="size-5 text-emerald-400" /></div>
                  <div className="mt-8 flex h-32 items-end gap-3">
                    {[42, 58, 48, 72, 64, 82, 76, 92, 88, 96].map((height, index) => <div key={index} className="flex-1 rounded-t bg-emerald-400/80" style={{ height: `${height}%` }} />)}
                  </div>
                  <div className="mt-4 flex justify-between text-[10px] font-semibold uppercase tracking-wider text-slate-300"><span>May</span><span>June</span><span>July</span><span>August</span></div>
                </div>
                <div className="mt-5 flex items-center justify-between rounded-xl border border-emerald-200 bg-emerald-50 p-4">
                  <div className="flex items-center gap-3"><span className="flex size-10 items-center justify-center rounded-xl bg-emerald-600 text-white"><MapPinned className="size-5" /></span><div><p className="text-sm font-semibold text-slate-950">12 agents active</p><p className="text-xs font-medium text-slate-600">Field collections on schedule</p></div></div>
                  <ChevronRight className="size-5 text-emerald-700" />
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      <section id="platform" className="mx-auto max-w-7xl px-6 py-24 lg:px-8 lg:py-28">
        <div className="max-w-3xl"><p className="text-sm font-bold uppercase tracking-[0.18em] text-emerald-700">Complete operating control</p><h2 className="mt-4 text-4xl font-bold tracking-tight text-slate-950 sm:text-5xl">Built around the work your team does every day.</h2><p className="mt-5 text-lg leading-8 text-slate-600">From head office to the collection route, zChit keeps every team aligned around accurate, current information.</p></div>
        <div className="mt-14 grid gap-5 md:grid-cols-2 lg:grid-cols-3">
          {capabilities.map(({ icon: Icon, title, description }) => <Card key={title} className="border border-slate-200 bg-white py-0 shadow-sm ring-0 transition hover:-translate-y-1 hover:border-emerald-200 hover:shadow-xl hover:shadow-emerald-900/5"><CardContent className="p-7"><span className="flex size-12 items-center justify-center rounded-xl bg-emerald-50 text-emerald-700"><Icon className="size-6" /></span><h3 className="mt-6 text-lg font-bold text-slate-950">{title}</h3><p className="mt-3 text-sm leading-6 text-slate-600">{description}</p></CardContent></Card>)}
        </div>
      </section>

      <section id="operations" className="bg-slate-950 py-24 text-white lg:py-28">
        <div className="mx-auto grid max-w-7xl gap-14 px-6 lg:grid-cols-2 lg:px-8">
          <div><p className="text-sm font-bold uppercase tracking-[0.18em] text-emerald-400">Operational confidence</p><h2 className="mt-4 text-4xl font-bold tracking-tight sm:text-5xl">Know what is happening before it becomes a problem.</h2><p className="mt-6 text-lg leading-8 text-slate-200">Track collection performance, member commitments, cash movement, agent activity, and outstanding actions without waiting for end-of-day reconciliation.</p></div>
          <div className="grid gap-4 sm:grid-cols-2">{["Live collection status", "Agent route visibility", "Automated due reminders", "Complete audit history"].map((item) => <div key={item} className="rounded-2xl border border-white/15 bg-white/5 p-6"><ShieldCheck className="size-6 text-emerald-400" /><p className="mt-5 font-semibold text-white">{item}</p></div>)}</div>
        </div>
      </section>

      <section id="security" className="mx-auto max-w-7xl px-6 py-24 lg:px-8">
        <div className="rounded-3xl border border-emerald-200 bg-emerald-50 px-7 py-12 text-center sm:px-12 lg:py-16">
          <Smartphone className="mx-auto size-10 text-emerald-700" />
          <h2 className="mx-auto mt-6 max-w-3xl text-3xl font-bold tracking-tight text-slate-950 sm:text-4xl">Bring your chit operations into one accountable workspace.</h2>
          <p className="mx-auto mt-5 max-w-2xl text-base leading-7 text-slate-600">Start with your company profile, bring in your team, and manage every member and collection with confidence.</p>
          <Button nativeButton={false} size="lg" className="mt-8 h-12 bg-emerald-600 px-7 text-base font-semibold text-white hover:bg-emerald-700" render={<Link href="/register" />}>Start with zChit <ArrowRight className="size-4" /></Button>
        </div>
      </section>

      <footer className="border-t border-slate-200 bg-slate-50">
        <div className="mx-auto flex max-w-7xl flex-col gap-6 px-6 py-10 sm:flex-row sm:items-center sm:justify-between lg:px-8"><Brand /><p className="text-sm font-medium text-slate-500">© 2026 zChit. Built for accountable fund operations.</p></div>
      </footer>
    </main>
  );
}
