"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { BadgeIndianRupee, Download, Filter, Printer, ReceiptIndianRupee, RotateCcw, WalletCards, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { API_URL, authenticatedApiRequest } from "@/lib/api";

type Scheme = { id: number; group_code: string; scheme_name: string };
type Member = { id: number; member_code: string; full_name: string; mobile_number: string };
type Row = {
  payment_id: number; payment_date: string; amount: string; received_amount: string;
  late_fee_amount: string; penalty_amount: string; waiver_amount: string; waiver_reason:string|null; excess_amount: string;
  refunded_amount: string; net_received_amount: string; payment_mode: string;
  reference_number: string | null; notes: string | null; group_id: number; group_code: string;
  scheme_name: string; member_id: number; member_code: string; member_name: string;
  mobile_number: string; installment_number: number; due_date: string; payable_amount: string;
  receipt_number: string | null; branch_id: number | null; branch_code:string|null; branch_name:string|null; collected_by_user_id:number|null; collector_email:string|null; payment_source: string;
  collection_location_text: string | null; collection_latitude:string|null; collection_longitude:string|null; status: string;
};
type Summary = { payment_mode: string; count: number; amount: string };
type Daily = { date: string; count: number; amount: string };
type Report = {
  rows: Row[]; total_amount: string; total_received_amount: string; total_refunded_amount: string;
  net_received_amount: string; total_transactions: number; unique_members: number;
  schemes_count: number; mode_summary: Summary[]; daily_summary: Daily[];
};
type AgeingRow = {
  group_id: number; scheme_name: string; member_id: number; member_name: string;
  member_code: string; installment_number: number; due_date: string; days_overdue: number;
  ageing_bucket: string; outstanding_amount: string;
};

const emptyReport: Report = {
  rows: [], total_amount: "0", total_received_amount: "0", total_refunded_amount: "0",
  net_received_amount: "0", total_transactions: 0, unique_members: 0, schemes_count: 0,
  mode_summary: [], daily_summary: [],
};
const paymentStatuses = [
  { value: "posted", label: "Posted" },
  { value: "partially_refunded", label: "Partially refunded" },
  { value: "refunded", label: "Refunded" },
  { value: "reversed", label: "Reversed" },
];

function money(value: string | number) {
  return `₹${Number(value).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}
function formatDate(value: string) {
  return new Date(`${value.slice(0, 10)}T00:00:00`).toLocaleDateString("en-IN");
}
function readable(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export default function CollectionsPage() {
  const [schemes, setSchemes] = useState<Scheme[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [report, setReport] = useState<Report>(emptyReport);
  const [ageing, setAgeing] = useState<AgeingRow[]>([]);
  const [scheme, setScheme] = useState<string | null>(null);
  const [member, setMember] = useState<string | null>(null);
  const [mode, setMode] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load(filters = true) {
    setLoading(true); setError("");
    try {
      const reportParams = new URLSearchParams();
      const ageingParams = new URLSearchParams();
      if (filters && scheme) { reportParams.set("scheme_id", scheme); ageingParams.set("scheme_id", scheme); }
      if (filters && member) reportParams.set("member_id", member);
      if (filters && mode) reportParams.set("payment_mode", mode);
      if (filters && status) reportParams.set("status", status);
      if (filters && dateFrom) reportParams.set("date_from", dateFrom);
      if (filters && dateTo) reportParams.set("date_to", dateTo);
      const [reportData, ageingData] = await Promise.all([
        authenticatedApiRequest<Report>(`/api/v1/chits/collections/report?${reportParams}`),
        authenticatedApiRequest<AgeingRow[]>(`/api/v1/chits/collections/ageing?${ageingParams}`),
      ]);
      setReport(reportData); setAgeing(ageingData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load collection reports.");
    } finally { setLoading(false); }
  }

  useEffect(() => {
    const timer = setTimeout(async () => {
      try {
        const [schemeData, memberData, initialReport, initialAgeing] = await Promise.all([
          authenticatedApiRequest<Scheme[]>("/api/v1/chits"),
          authenticatedApiRequest<{ items: Member[] }>("/api/v1/members?page_size=100"),
          authenticatedApiRequest<Report>("/api/v1/chits/collections/report"),
          authenticatedApiRequest<AgeingRow[]>("/api/v1/chits/collections/ageing"),
        ]);
        setSchemes(schemeData); setMembers(memberData.items); setReport(initialReport); setAgeing(initialAgeing);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to load collection reports.");
      } finally { setLoading(false); }
    }, 0);
    return () => clearTimeout(timer);
  }, []);

  function submit(event: FormEvent) { event.preventDefault(); void load(true); }
  function clear() {
    setScheme(null); setMember(null); setMode(null); setStatus(null); setDateFrom(""); setDateTo("");
    setTimeout(() => void load(false), 0);
  }
  async function exportCsv(){const params=new URLSearchParams();if(scheme)params.set("scheme_id",scheme);if(member)params.set("member_id",member);if(mode)params.set("payment_mode",mode);if(status)params.set("status",status);if(dateFrom)params.set("date_from",dateFrom);if(dateTo)params.set("date_to",dateTo);const token=localStorage.getItem("zchit_access_token");const response=await fetch(`${API_URL}/api/v1/chits/collections/export.csv?${params}`,{headers:{Authorization:`Bearer ${token}`}});if(!response.ok){setError("Unable to export collections.");return;}const url=URL.createObjectURL(await response.blob());const anchor=document.createElement("a");anchor.href=url;anchor.download="zchit-collections.csv";anchor.click();URL.revokeObjectURL(url);}
  async function refundRow(row:Row){const refundable=Number(row.received_amount)-Number(row.refunded_amount);const amount=window.prompt(`Refund amount (maximum ₹${refundable.toLocaleString("en-IN")})`);if(!amount)return;const reason=window.prompt("Refund reason");if(!reason)return;try{await authenticatedApiRequest(`/api/v1/chits/receipts/payments/${row.payment_id}/refund`,{method:"POST",body:JSON.stringify({amount:Number(amount),refund_date:new Date().toISOString().slice(0,10),refund_mode:row.payment_mode,reference_number:null,reason})});await load(true);}catch(err){setError(err instanceof Error?err.message:"Unable to post refund.");}}

  return <div className="mx-auto max-w-[1600px] space-y-4">
    <div className="flex items-end justify-between"><div><p className="text-xs font-bold uppercase tracking-[0.14em] text-emerald-700">Financial reports</p><h1 className="mt-1.5 text-2xl font-bold text-slate-950">Collections</h1><p className="mt-1 text-[13px] text-slate-600">Analyze principal, charges, refunds, net receipts, and overdue installments.</p></div><div className="flex gap-2 print:hidden"><Button type="button" variant="outline" onClick={()=>void exportCsv()}><Download className="size-4"/>CSV</Button><Button type="button" variant="outline" onClick={()=>window.print()}><Printer className="size-4"/>Print / PDF</Button></div></div>

    <Card className="overflow-visible border border-slate-200 bg-white py-0 shadow-sm ring-0"><CardContent className="overflow-visible p-4">
      <div className="mb-3 flex items-center gap-2"><span className="flex size-7 items-center justify-center rounded-md bg-emerald-50 text-emerald-700"><Filter className="size-3.5" /></span><div><CardTitle className="text-xs font-bold text-slate-950">Report filters</CardTitle><p className="text-[10px] text-slate-500">Filter collections by scheme, member, channel, status, or date range</p></div></div>
      <form onSubmit={submit} className="grid items-end gap-3 md:grid-cols-2 xl:grid-cols-7">
        <ReadableSelect label="Scheme" value={scheme} setValue={setScheme} placeholder="All schemes" items={schemes.map((item) => ({ value: String(item.id), label: `${item.scheme_name} · ${item.group_code}` }))} />
        <ReadableSelect label="Member" value={member} setValue={setMember} placeholder="All members" items={members.map((item) => ({ value: String(item.id), label: `${item.full_name} · ${item.member_code}` }))} />
        <ReadableSelect label="Payment mode" value={mode} setValue={setMode} placeholder="All modes" items={["cash", "upi", "bank", "cheque"].map((value) => ({ value, label: value.toUpperCase() }))} />
        <ReadableSelect label="Status" value={status} setValue={setStatus} placeholder="All statuses" items={paymentStatuses} />
        <DateField label="From date" value={dateFrom} setValue={setDateFrom} /><DateField label="To date" value={dateTo} setValue={setDateTo} />
        <div className="flex h-9 gap-2"><Button type="submit" disabled={loading} className="h-9 flex-1 bg-emerald-600 px-4 font-semibold text-white hover:bg-emerald-700">Apply filters</Button><Button type="button" variant="outline" size="icon" className="size-9 shrink-0" onClick={clear} aria-label="Clear filters"><X className="size-4" /></Button></div>
      </form>
    </CardContent></Card>

    {error && <p className="rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-700">{error}</p>}
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <Stat icon={BadgeIndianRupee} label="Principal collected" value={money(report.total_amount)} tone="blue" />
      <Stat icon={ReceiptIndianRupee} label="Total received" value={money(report.total_received_amount)} tone="emerald" />
      <Stat icon={RotateCcw} label="Total refunded" value={money(report.total_refunded_amount)} tone="amber" />
      <Stat icon={WalletCards} label="Net received" value={money(report.net_received_amount)} tone="violet" />
    </div>

    <Card className="overflow-hidden border border-slate-200 bg-white py-0 shadow-sm ring-0">
      <CardHeader className="flex flex-row items-center justify-between border-b border-slate-200 bg-gradient-to-r from-slate-50 to-white p-4"><div><CardTitle className="text-sm text-slate-950">Collection records</CardTitle><p className="mt-0.5 text-[10px] text-slate-500">Principal, fees, waivers, refunds, source, and net receipt details</p></div><Badge variant="outline" className="border-emerald-200 bg-emerald-50 text-emerald-700">{report.total_transactions} records</Badge></CardHeader>
      <CardContent className="overflow-x-auto p-0">{loading ? <p className="p-10 text-center text-xs text-slate-500">Loading report…</p> : report.rows.length === 0 ? <Empty text="No collection records match these filters." /> : <table className="w-full min-w-[2100px] text-xs">
        <thead className="border-b border-slate-200 bg-slate-50"><tr>{["Payment date", "Receipt", "Scheme", "Member", "Installment", "Mode / source", "Collector / branch", "Collection location", "Principal", "Late fee", "Penalty", "Waiver", "Excess", "Received", "Refunded", "Net received", "Status"].map((label) => <th key={label} className="whitespace-nowrap px-3 py-3 text-left text-[10px] font-bold text-slate-700">{label}</th>)}</tr></thead>
        <tbody>{report.rows.map((row, index) => <tr key={row.payment_id} className={`border-b border-slate-100 transition hover:bg-emerald-50 ${index % 2 ? "bg-slate-50/60" : "bg-white"}`}>
          <td className="whitespace-nowrap px-3 py-3 font-semibold text-slate-900">{formatDate(row.payment_date)}</td>
          <td className="px-3 py-3"><Link href={`/dashboard/receipts/${row.payment_id}`} className="font-bold text-emerald-700 hover:underline">{row.receipt_number ?? "Legacy receipt"}</Link><p className="mt-0.5 text-[9px] text-slate-500">{row.reference_number ?? "No reference"}</p></td>
          <td className="px-3 py-3"><Link href={`/dashboard/chits/${row.group_id}`} className="font-bold text-slate-950 hover:text-emerald-700">{row.scheme_name}</Link><p className="text-[9px] text-slate-500">{row.group_code}</p></td>
          <td className="px-3 py-3"><Link href={`/dashboard/members/${row.member_id}`} className="font-bold text-slate-950 hover:text-emerald-700">{row.member_name}</Link><p className="text-[9px] text-slate-500">{row.member_code}</p></td>
          <td className="whitespace-nowrap px-3 py-3"><span className="font-semibold text-slate-900">Installment {row.installment_number}</span><p className="text-[9px] text-slate-500">Due {formatDate(row.due_date)}</p></td>
          <td className="px-3 py-3"><span className="font-semibold uppercase text-slate-900">{row.payment_mode}</span><p className="text-[9px] text-slate-500">{readable(row.payment_source)}</p></td>
          <td className="px-3 py-3"><p className="font-semibold text-slate-900">{row.collector_email??"System"}</p><p className="text-[9px] text-slate-500">{row.branch_name?`${row.branch_name} · ${row.branch_code}`:"No branch"}</p></td>
          <td className="max-w-[180px] px-3 py-3 text-slate-800">{row.collection_location_text ?? "Not recorded"}{row.collection_latitude&&row.collection_longitude&&<p className="mt-1 text-[9px] text-slate-500">{row.collection_latitude}, {row.collection_longitude}</p>}{row.notes&&<p className="mt-1 text-[9px] text-slate-500">{row.notes}</p>}</td>
          <MoneyCell value={row.amount} /><MoneyCell value={row.late_fee_amount} /><MoneyCell value={row.penalty_amount} /><td className="px-3 py-3"><span className={Number(row.waiver_amount)>0?"font-semibold text-red-700":"text-slate-800"}>{money(row.waiver_amount)}</span>{row.waiver_reason&&<p className="mt-1 max-w-32 text-[9px] text-slate-500">{row.waiver_reason}</p>}</td><MoneyCell value={row.excess_amount} /><MoneyCell value={row.received_amount} strong /><MoneyCell value={row.refunded_amount} negative /><MoneyCell value={row.net_received_amount} strong />
          <td className="px-3 py-3"><StatusBadge status={row.status} />{row.status!=="reversed"&&Number(row.received_amount)>Number(row.refunded_amount)&&<Button type="button" variant="outline" size="sm" className="mt-1 h-7 text-[10px]" onClick={()=>void refundRow(row)}>Refund</Button>}</td>
        </tr>)}</tbody>
      </table>}</CardContent>
    </Card>

    <Card className="overflow-hidden border border-slate-200 bg-white py-0 shadow-sm ring-0">
      <CardHeader className="flex flex-row items-center justify-between border-b border-slate-200 bg-gradient-to-r from-amber-50 to-white p-4"><div><CardTitle className="text-sm text-slate-950">Overdue ageing</CardTitle><p className="mt-0.5 text-[10px] text-slate-500">Outstanding installments past each scheme&apos;s grace period; the scheme filter applies here</p></div><Badge variant="outline" className="border-amber-200 bg-amber-50 text-amber-800">{ageing.length} overdue</Badge></CardHeader>
      <CardContent className="overflow-x-auto p-0">{loading ? <p className="p-10 text-center text-xs text-slate-500">Loading ageing report…</p> : ageing.length === 0 ? <Empty text="No overdue installments found for the selected scheme." /> : <table className="w-full min-w-[1050px] text-xs">
        <thead className="border-b border-slate-200 bg-slate-50"><tr>{["Scheme", "Member", "Installment", "Due date", "Days overdue", "Ageing bucket", "Outstanding"].map((label) => <th key={label} className="px-4 py-3 text-left text-[10px] font-bold text-slate-700">{label}</th>)}</tr></thead>
        <tbody>{ageing.map((row, index) => <tr key={`${row.group_id}-${row.member_id}-${row.installment_number}`} className={`border-b border-slate-100 hover:bg-amber-50 ${index % 2 ? "bg-slate-50/60" : "bg-white"}`}>
          <td className="px-4 py-3"><Link href={`/dashboard/chits/${row.group_id}`} className="font-bold text-slate-950 hover:text-emerald-700">{row.scheme_name}</Link></td>
          <td className="px-4 py-3"><Link href={`/dashboard/members/${row.member_id}`} className="font-bold text-slate-950 hover:text-emerald-700">{row.member_name}</Link><p className="text-[9px] text-slate-500">{row.member_code}</p></td>
          <td className="px-4 py-3 font-semibold text-slate-900">Installment {row.installment_number}</td><td className="whitespace-nowrap px-4 py-3 text-slate-800">{formatDate(row.due_date)}</td><td className="px-4 py-3 font-semibold text-slate-900">{row.days_overdue} days</td><td className="px-4 py-3"><Badge variant="outline" className="border-amber-200 bg-amber-50 text-amber-800">{readable(row.ageing_bucket)}</Badge></td><td className="px-4 py-3 font-bold text-red-700">{money(row.outstanding_amount)}</td>
        </tr>)}</tbody>
      </table>}</CardContent>
    </Card>
  </div>;
}

function ReadableSelect({ label, value, setValue, placeholder, items }: { label: string; value: string | null; setValue: (value: string | null) => void; placeholder: string; items: { value: string; label: string }[] }) {
  const selectedLabel = items.find((item) => item.value === value)?.label;
  return <div className="space-y-1.5"><Label className="text-[10px] font-semibold text-slate-700">{label}</Label><Select value={value} onValueChange={setValue}><SelectTrigger className="h-9 w-full border-slate-300 bg-white"><SelectValue>{selectedLabel ?? placeholder}</SelectValue></SelectTrigger><SelectContent>{items.map((item) => <SelectItem key={item.value} value={item.value}>{item.label}</SelectItem>)}</SelectContent></Select></div>;
}
function DateField({ label, value, setValue }: { label: string; value: string; setValue: (value: string) => void }) {
  return <div className="space-y-1.5"><Label className="text-[10px] font-semibold text-slate-700">{label}</Label><Input type="date" value={value} onChange={(event) => setValue(event.target.value)} className="h-9 border-slate-300 bg-white" /></div>;
}
function Stat({ icon: Icon, label, value, tone }: { icon: typeof BadgeIndianRupee; label: string; value: string; tone: string }) {
  const colors: Record<string, string> = { emerald: "bg-emerald-50 text-emerald-700", blue: "bg-blue-50 text-blue-700", violet: "bg-violet-50 text-violet-700", amber: "bg-amber-50 text-amber-700" };
  return <Card className="border border-slate-200 bg-white py-0 shadow-sm ring-0"><CardContent className="flex items-center gap-3 p-4"><span className={`flex size-10 items-center justify-center rounded-lg ${colors[tone]}`}><Icon className="size-[18px]" /></span><div><p className="text-[10px] font-semibold text-slate-600">{label}</p><p className="mt-0.5 text-lg font-bold text-slate-950">{value}</p></div></CardContent></Card>;
}
function MoneyCell({ value, negative = false, strong = false }: { value: string; negative?: boolean; strong?: boolean }) {
  return <td className={`whitespace-nowrap px-3 py-3 ${negative && Number(value) > 0 ? "font-semibold text-red-700" : strong ? "font-bold text-slate-950" : "text-slate-800"}`}>{money(value)}</td>;
}
function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = { posted: "border-emerald-200 bg-emerald-50 text-emerald-700", partially_refunded: "border-amber-200 bg-amber-50 text-amber-800", refunded: "border-red-200 bg-red-50 text-red-700", reversed:"border-slate-300 bg-slate-100 text-slate-700" };
  return <Badge variant="outline" className={`whitespace-nowrap ${styles[status] ?? "border-slate-200 bg-slate-50 text-slate-700"}`}>{readable(status)}</Badge>;
}
function Empty({ text }: { text: string }) {
  return <div className="p-8 text-center"><ReceiptIndianRupee className="mx-auto size-7 text-slate-300" /><p className="mt-2 text-xs text-slate-500">{text}</p></div>;
}
/* Stale duplicate retained only because the patch backend would not truncate it.

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { BadgeIndianRupee, Filter, ReceiptIndianRupee, UsersRound, WalletCards, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { authenticatedApiRequest } from "@/lib/api";

type Scheme = { id: number; group_code: string; scheme_name: string };
type Member = { id: number; member_code: string; full_name: string; mobile_number: string };
type Row = { payment_id: number; payment_date: string; amount: string; payment_mode: string; reference_number: string | null; notes: string | null; group_id: number; group_code: string; scheme_name: string; member_id: number; member_code: string; member_name: string; mobile_number: string; installment_number: number; due_date: string; payable_amount: string; receipt_number: string | null; status: string };
type Summary = { payment_mode: string; count: number; amount: string };
type Daily = { date: string; count: number; amount: string };
type Report = { rows: Row[]; total_amount: string; total_transactions: number; unique_members: number; schemes_count: number; mode_summary: Summary[]; daily_summary: Daily[] };
const emptyReport: Report = { rows: [], total_amount: "0", total_transactions: 0, unique_members: 0, schemes_count: 0, mode_summary: [], daily_summary: [] };

export default function CollectionsPage() {
  const [schemes, setSchemes] = useState<Scheme[]>([]); const [members, setMembers] = useState<Member[]>([]); const [report, setReport] = useState<Report>(emptyReport); const [scheme, setScheme] = useState<string | null>(null); const [member, setMember] = useState<string | null>(null); const [mode, setMode] = useState<string | null>(null); const [dateFrom, setDateFrom] = useState(""); const [dateTo, setDateTo] = useState(""); const [loading, setLoading] = useState(true); const [error, setError] = useState("");
  async function load(filters = true) { setLoading(true); setError(""); try { const params = new URLSearchParams(); if (filters && scheme) params.set("scheme_id", scheme); if (filters && member) params.set("member_id", member); if (filters && mode) params.set("payment_mode", mode); if (filters && dateFrom) params.set("date_from", dateFrom); if (filters && dateTo) params.set("date_to", dateTo); setReport(await authenticatedApiRequest<Report>(`/api/v1/chits/collections/report?${params}`)); } catch (err) { setError(err instanceof Error ? err.message : "Unable to load collection report."); } finally { setLoading(false); } }
  useEffect(() => { const timer = setTimeout(async () => { try { const [schemeData, memberData, initialReport] = await Promise.all([authenticatedApiRequest<Scheme[]>("/api/v1/chits"), authenticatedApiRequest<{ items: Member[] }>("/api/v1/members?page_size=100"), authenticatedApiRequest<Report>("/api/v1/chits/collections/report")]); setSchemes(schemeData); setMembers(memberData.items); setReport(initialReport); } catch (err) { setError(err instanceof Error ? err.message : "Unable to load filters."); } finally { setLoading(false); } }, 0); return () => clearTimeout(timer); }, []);
  function submit(event: FormEvent) { event.preventDefault(); void load(true); }
  function clear() { setScheme(null); setMember(null); setMode(null); setDateFrom(""); setDateTo(""); setTimeout(() => void load(false), 0); }
  return <div className="mx-auto max-w-[1600px] space-y-4"><div><p className="text-xs font-bold uppercase tracking-[0.14em] text-emerald-700">Financial reports</p><h1 className="mt-1.5 text-2xl font-bold text-slate-950">Collections</h1><p className="mt-1 text-[13px] text-slate-600">Analyze member payments by scheme, date range, member, and payment channel.</p></div>
  <Card className="overflow-visible border border-slate-200 bg-white py-0 shadow-sm ring-0"><CardContent className="overflow-visible p-4"><div className="mb-3 flex items-center gap-2"><span className="flex size-7 items-center justify-center rounded-md bg-emerald-50 text-emerald-700"><Filter className="size-3.5" /></span><div><CardTitle className="text-xs font-bold text-slate-950">Report filters</CardTitle><p className="text-[10px] text-slate-500">Narrow collection records by scheme, member, channel, or date range</p></div></div><form onSubmit={submit} className="grid items-end gap-3 md:grid-cols-2 xl:grid-cols-[minmax(190px,1.2fr)_minmax(190px,1.2fr)_minmax(145px,.75fr)_150px_150px_auto]"><ReadableSelect label="Scheme" value={scheme} setValue={setScheme} placeholder="All schemes" items={schemes.map(item => ({ value: String(item.id), label: `${item.scheme_name} · ${item.group_code}` }))} /><ReadableSelect label="Member" value={member} setValue={setMember} placeholder="All members" items={members.map(item => ({ value: String(item.id), label: `${item.full_name} · ${item.member_code}` }))} /><ReadableSelect label="Payment mode" value={mode} setValue={setMode} placeholder="All modes" items={["cash","upi","bank","cheque"].map(value => ({ value, label: value.toUpperCase() }))} /><DateField label="From date" value={dateFrom} setValue={setDateFrom} /><DateField label="To date" value={dateTo} setValue={setDateTo} /><div className="flex h-9 gap-2"><Button type="submit" disabled={loading} className="h-9 bg-emerald-600 px-4 font-semibold text-white hover:bg-emerald-700">Apply filters</Button><Button type="button" variant="outline" size="icon" className="size-9" onClick={clear} aria-label="Clear filters"><X className="size-4" /></Button></div></form></CardContent></Card>
  {error && <p className="rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-700">{error}</p>}
  <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><Stat icon={BadgeIndianRupee} label="Total collected" value={`₹${Number(report.total_amount).toLocaleString("en-IN")}`} tone="emerald" /><Stat icon={ReceiptIndianRupee} label="Transactions" value={String(report.total_transactions)} tone="blue" /><Stat icon={UsersRound} label="Members paid" value={String(report.unique_members)} tone="violet" /><Stat icon={WalletCards} label="Schemes covered" value={String(report.schemes_count)} tone="amber" /></div>
  <Card className="overflow-hidden border border-slate-200 bg-white py-0 shadow-sm ring-0"><CardHeader className="flex flex-row items-center justify-between border-b border-slate-200 bg-gradient-to-r from-slate-50 to-white p-4"><div><CardTitle className="text-sm">Collection records</CardTitle><p className="mt-0.5 text-[10px] text-slate-500">Complete payment details matching the selected filters</p></div><Badge variant="outline" className="border-emerald-200 bg-emerald-50 text-emerald-700">{report.rows.length} records</Badge></CardHeader><CardContent className="overflow-x-auto p-0">{loading ? <p className="p-10 text-center text-xs text-slate-500">Loading report…</p> : report.rows.length === 0 ? <Empty text="No collection records match these filters." /> : <table className="w-full min-w-[1100px] text-xs"><thead className="border-b border-slate-200 bg-slate-50"><tr>{["Payment date","Receipt","Scheme","Member","Installment","Mode","Reference","Amount"].map(label => <th key={label} className="px-4 py-3 text-left text-[10px] font-bold text-slate-600">{label}</th>)}</tr></thead><tbody>{report.rows.map((row, index) => <tr key={row.payment_id} className={`border-b border-slate-100 transition hover:bg-emerald-50 ${index % 2 ? "bg-slate-50/60" : "bg-white"}`}><td className="px-4 py-3 font-semibold">{new Date(row.payment_date).toLocaleDateString("en-IN")}</td><td className="px-4 py-3"><Link href={`/dashboard/receipts/${row.payment_id}`} className="font-bold text-emerald-700 hover:underline">{row.receipt_number ?? "Legacy receipt"}</Link></td><td className="px-4 py-3"><Link href={`/dashboard/chits/${row.group_id}`} className="font-bold text-slate-950 hover:text-emerald-700">{row.scheme_name}</Link><p className="text-[9px] text-slate-500">{row.group_code}</p></td><td className="px-4 py-3"><Link href={`/dashboard/members/${row.member_id}`} className="font-bold text-slate-950 hover:text-emerald-700">{row.member_name}</Link><p className="text-[9px] text-slate-500">{row.member_code} · {row.mobile_number}</p></td><td className="px-4 py-3"><span className="rounded bg-blue-50 px-2 py-1 font-bold text-blue-700">#{row.installment_number}</span></td><td className="px-4 py-3"><Badge className="bg-slate-100 text-slate-700">{row.payment_mode.toUpperCase()}</Badge></td><td className="px-4 py-3 text-slate-600">{row.reference_number ?? "—"}</td><td className="px-4 py-3 text-right text-sm font-bold text-emerald-700">₹{Number(row.amount).toLocaleString("en-IN")}</td></tr>)}</tbody></table>}</CardContent></Card></div>;
}
function ReadableSelect({ label, value, setValue, placeholder, items }: { label: string; value: string | null; setValue: (value: string | null) => void; placeholder: string; items: { value: string; label: string }[] }) { const selectedLabel = items.find(item => item.value === value)?.label; return <div className="space-y-1.5"><Label className="text-[10px] font-semibold text-slate-600">{label}</Label><Select value={value} onValueChange={setValue}><SelectTrigger className="h-9 w-full border-slate-300 bg-white"><SelectValue>{selectedLabel ?? placeholder}</SelectValue></SelectTrigger><SelectContent>{items.map(item => <SelectItem key={item.value} value={item.value}>{item.label}</SelectItem>)}</SelectContent></Select></div>; }
function DateField({ label, value, setValue }: { label: string; value: string; setValue: (value: string) => void }) { return <div className="space-y-1.5"><Label className="text-[10px] font-semibold text-slate-600">{label}</Label><Input type="date" value={value} onChange={event => setValue(event.target.value)} className="h-9 border-slate-300 bg-white" /></div>; }
function Stat({ icon: Icon, label, value, tone }: { icon: typeof BadgeIndianRupee; label: string; value: string; tone: string }) { const colors: Record<string,string> = { emerald:"bg-emerald-50 text-emerald-700", blue:"bg-blue-50 text-blue-700", violet:"bg-violet-50 text-violet-700", amber:"bg-amber-50 text-amber-700" }; return <Card className="border border-slate-200 bg-white py-0 shadow-sm ring-0"><CardContent className="flex items-center gap-3 p-4"><span className={`flex size-10 items-center justify-center rounded-lg ${colors[tone]}`}><Icon className="size-[18px]" /></span><div><p className="text-[10px] font-semibold text-slate-500">{label}</p><p className="mt-0.5 text-lg font-bold text-slate-950">{value}</p></div></CardContent></Card>; }
function Empty({ text }: { text: string }) { return <div className="p-8 text-center"><ReceiptIndianRupee className="mx-auto size-7 text-slate-300" /><p className="mt-2 text-xs text-slate-500">{text}</p></div>; }
*/
