"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { BadgeIndianRupee, CheckCircle2, Filter, Gavel, ListOrdered, ReceiptIndianRupee, WalletCards, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { API_URL, authenticatedApiRequest, getResponseError } from "@/lib/api";

type Scheme = { id: number; group_code: string; scheme_name: string };
type Member = { id: number; member_code: string; full_name: string };
type AuctionStatus = "pending" | "approved" | "paid" | "cancelled" | "reversed";
type Auction = {
  id: number;
  group_id: number;
  group_code: string;
  scheme_name: string;
  installment_number: number;
  due_date: string;
  winner_member_id: number;
  winner_name: string;
  auction_date: string;
  bid_amount: string;
  discount_amount: string;
  commission_percent: string;
  commission_amount: string;
  payout_amount: string;
  settled_installment_amount: string;
  net_payout_amount: string;
  status: AuctionStatus;
  voucher_number: string | null;
  winner_acknowledged_at: string | null;
  approved_at: string | null;
  payout_date: string | null;
  payout_mode: string | null;
  payout_reference_number: string | null;
  payout_verified_at: string | null;
  settlement_proof_file_name: string | null;
};
type SelectOption = { value: string; label: string };

const statusOptions: SelectOption[] = ["pending", "approved", "paid", "cancelled", "reversed"].map((value) => ({
  value,
  label: title(value),
}));
const payoutModes: SelectOption[] = [
  { value: "cash", label: "Cash" },
  { value: "upi", label: "UPI" },
  { value: "bank", label: "Bank transfer" },
  { value: "cheque", label: "Cheque" },
];

export default function AuctionsPage() {
  const [items, setItems] = useState<Auction[]>([]);
  const [schemes, setSchemes] = useState<Scheme[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [scheme, setScheme] = useState<string | null>(null);
  const [member, setMember] = useState<string | null>(null);
  const [auctionStatus, setAuctionStatus] = useState<string | null>(null);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<number | null>(null);
  const [payingAuction, setPayingAuction] = useState<Auction | null>(null);
  const [bidAuction,setBidAuction]=useState<Auction|null>(null); const [bidder,setBidder]=useState<string|null>(null); const [bids,setBids]=useState<{id:number;sequence_number:number;member_id:number;member_name:string;bid_amount:string;discount_amount:string;is_winning_bid:boolean;status:string}[]>([]);
  const [error, setError] = useState("");

  async function loadAuctions(filtered = true) {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams();
      if (filtered && scheme) params.set("scheme_id", scheme);
      if (filtered && member) params.set("member_id", member);
      if (filtered && auctionStatus) params.set("status", auctionStatus);
      if (filtered && dateFrom) params.set("date_from", dateFrom);
      if (filtered && dateTo) params.set("date_to", dateTo);
      const query = params.size ? `?${params.toString()}` : "";
      setItems(await authenticatedApiRequest<Auction[]>(`/api/v1/chits/auctions/all${query}`));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load auctions.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let active = true;
    async function loadInitialData() {
      try {
        const [schemeData, memberData, auctionData] = await Promise.all([
          authenticatedApiRequest<Scheme[]>("/api/v1/chits"),
          authenticatedApiRequest<{ items: Member[] }>("/api/v1/members?page_size=100"),
          authenticatedApiRequest<Auction[]>("/api/v1/chits/auctions/all"),
        ]);
        if (!active) return;
        setSchemes(schemeData);
        setMembers(memberData.items);
        setItems(auctionData);
      } catch (err) {
        if (active) setError(err instanceof Error ? err.message : "Unable to load auction filters.");
      } finally {
        if (active) setLoading(false);
      }
    }
    void loadInitialData();
    return () => { active = false; };
  }, []);

  function submitFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void loadAuctions(true);
  }

  function clearFilters() {
    setScheme(null);
    setMember(null);
    setAuctionStatus(null);
    setDateFrom("");
    setDateTo("");
    setTimeout(() => void loadAuctions(false), 0);
  }

  async function approveAuction(item: Auction) {
    if (!window.confirm(`Confirm that ${item.winner_name} acknowledged the auction result?`)) return;
    setActionLoading(item.id);
    setError("");
    try {
      await authenticatedApiRequest(`/api/v1/chits/${item.group_id}/auctions/${item.id}/approve`, {
        method: "POST",
        body: JSON.stringify({ winner_acknowledged: true }),
      });
      await loadAuctions(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to approve auction.");
    } finally {
      setActionLoading(null);
    }
  }

  async function recordPayout(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!payingAuction) return;
    const form = new FormData(event.currentTarget);
    form.set("payout_verified", "true");
    setActionLoading(payingAuction.id);
    setError("");
    try {
      const token = localStorage.getItem("zchit_access_token");
      const response = await fetch(`${API_URL}/api/v1/chits/${payingAuction.group_id}/auctions/${payingAuction.id}/pay`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: form,
      });
      if (!response.ok) throw new Error(await getResponseError(response, "Unable to record auction payout."));
      setPayingAuction(null);
      await loadAuctions(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to record auction payout.");
    } finally {
      setActionLoading(null);
    }
  }

  async function openProof(item: Auction) {
    try {
      const token = localStorage.getItem("zchit_access_token");
      const response = await fetch(`${API_URL}/api/v1/chits/${item.group_id}/auctions/${item.id}/settlement-proof`, { headers: { Authorization: `Bearer ${token}` } });
      if (!response.ok) throw new Error(await getResponseError(response, "Unable to open settlement proof."));
      const url = URL.createObjectURL(await response.blob());
      window.open(url, "_blank", "noopener,noreferrer");
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to open settlement proof."); }
  }
  async function openBids(item:Auction){try{setBids(await authenticatedApiRequest(`/api/v1/chits/${item.group_id}/auctions/${item.id}/bids`));setBidAuction(item);}catch(err){setError(err instanceof Error?err.message:"Unable to load bids.");}}
  async function addBid(event:FormEvent<HTMLFormElement>){event.preventDefault();if(!bidAuction)return;const data=new FormData(event.currentTarget);try{await authenticatedApiRequest(`/api/v1/chits/${bidAuction.group_id}/auctions/${bidAuction.id}/bids`,{method:"POST",body:JSON.stringify({bidder_member_id:Number(data.get("bidder_member_id")),bid_amount:Number(data.get("bid_amount")),discount_amount:Number(data.get("discount_amount"))})});setBids(await authenticatedApiRequest(`/api/v1/chits/${bidAuction.group_id}/auctions/${bidAuction.id}/bids`));}catch(err){setError(err instanceof Error?err.message:"Unable to record bid.");}}
  async function cancelAuction(item:Auction){const reason=window.prompt("Cancellation reason");if(!reason)return;try{await authenticatedApiRequest(`/api/v1/chits/${item.group_id}/auctions/${item.id}/cancel`,{method:"POST",body:JSON.stringify({reason})});await loadAuctions(true);}catch(err){setError(err instanceof Error?err.message:"Unable to cancel auction.");}}

  const gross = items.reduce((sum, item) => sum + Number(item.payout_amount), 0);
  const net = items.reduce((sum, item) => sum + Number(item.net_payout_amount), 0);
  const commission = items.reduce((sum, item) => sum + Number(item.commission_amount), 0);

  return (
    <div className="mx-auto max-w-[1600px] space-y-4">
      <div>
        <p className="text-xs font-bold uppercase tracking-[0.14em] text-emerald-700">Auction reports</p>
        <h1 className="mt-1.5 text-2xl font-bold text-slate-950">Auctions</h1>
        <p className="mt-1 text-[13px] text-slate-600">Review approvals, verified payouts, commissions, and settlement proof.</p>
      </div>

      <Card className="overflow-visible border border-slate-200 bg-white py-0 shadow-sm ring-0">
        <CardContent className="overflow-visible p-4">
          <div className="mb-3 flex items-center gap-2">
            <span className="flex size-7 items-center justify-center rounded-md bg-emerald-50 text-emerald-700"><Filter className="size-3.5" /></span>
            <div>
              <CardTitle className="text-xs font-bold text-slate-950">Auction filters</CardTitle>
              <p className="text-[10px] text-slate-500">Filter by scheme, winning member, lifecycle status, or auction date</p>
            </div>
          </div>
          <form onSubmit={submitFilters} className="grid items-end gap-3 md:grid-cols-2 xl:grid-cols-[minmax(190px,1.2fr)_minmax(190px,1.2fr)_minmax(130px,.7fr)_150px_150px_auto]">
            <ReadableSelect label="Scheme" value={scheme} setValue={setScheme} placeholder="All schemes" items={schemes.map((item) => ({ value: String(item.id), label: `${item.scheme_name} · ${item.group_code}` }))} />
            <ReadableSelect label="Winning member" value={member} setValue={setMember} placeholder="All members" items={members.map((item) => ({ value: String(item.id), label: `${item.full_name} · ${item.member_code}` }))} />
            <ReadableSelect label="Status" value={auctionStatus} setValue={setAuctionStatus} placeholder="All statuses" items={statusOptions} />
            <DateFilter label="From date" value={dateFrom} setValue={setDateFrom} />
            <DateFilter label="To date" value={dateTo} setValue={setDateTo} />
            <div className="flex h-9 gap-2">
              <Button type="submit" disabled={loading} className="h-9 bg-emerald-600 px-4 font-semibold text-white hover:bg-emerald-700">Apply filters</Button>
              <Button type="button" variant="outline" size="icon" className="size-9" onClick={clearFilters} aria-label="Clear filters"><X className="size-4" /></Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {error && <p className="rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-700">{error}</p>}

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Stat icon={Gavel} label="Auctions" value={String(items.length)} tone="emerald" />
        <Stat icon={BadgeIndianRupee} label="Gross payout" value={money(gross)} tone="blue" />
        <Stat icon={ReceiptIndianRupee} label="Commission" value={money(commission)} tone="violet" />
        <Stat icon={WalletCards} label="Net payout" value={money(net)} tone="amber" />
      </div>

      <Card className="overflow-hidden border border-slate-200 bg-white py-0 shadow-sm ring-0">
        <CardHeader className="flex flex-row items-center justify-between border-b border-slate-200 bg-gradient-to-r from-slate-50 to-white p-4">
          <div><CardTitle className="text-sm">Auction records</CardTitle><p className="mt-0.5 text-[10px] text-slate-500">Approval, commission, payout, and proof lifecycle</p></div>
          <Badge variant="outline" className="border-emerald-200 bg-emerald-50 text-emerald-700">{items.length} records</Badge>
        </CardHeader>
        <CardContent className="overflow-x-auto p-0">
          {loading ? <p className="p-10 text-center text-xs text-slate-500">Loading auctions…</p> : items.length === 0 ? (
            <div className="p-10 text-center"><Gavel className="mx-auto size-8 text-slate-300" /><p className="mt-2 text-xs font-bold text-slate-700">No auction records match these filters</p></div>
          ) : (
            <table className="w-full min-w-[1740px] text-xs">
              <thead className="border-b border-slate-200 bg-slate-50"><tr>
                {["Auction date", "Voucher", "Scheme", "Installment", "Winning member", "Bid", "Discount", "Commission", "Gross payout", "Settled", "Net payout", "Approval", "Payout", "Proof", "Status", "Actions"].map((label) => <th key={label} className="px-3 py-3 text-left text-[10px] font-bold text-slate-600">{label}</th>)}
              </tr></thead>
              <tbody>{items.map((item, index) => (
                <tr key={item.id} className={`border-b border-slate-100 transition hover:bg-emerald-50 ${index % 2 ? "bg-slate-50/60" : "bg-white"}`}>
                  <td className="px-3 py-3 font-semibold">{formatDate(item.auction_date)}</td>
                  <td className="px-3 py-3">{item.voucher_number ? <Link href={`/dashboard/vouchers/auctions/${item.id}`} className="font-bold text-emerald-700 hover:underline">{item.voucher_number}</Link> : <span className="text-slate-500">—</span>}</td>
                  <td className="px-3 py-3"><Link href={`/dashboard/chits/${item.group_id}`} className="font-bold text-slate-950 hover:text-emerald-700">{item.scheme_name}</Link><p className="text-[9px] text-slate-500">{item.group_code}</p></td>
                  <td className="px-3 py-3"><span className="rounded bg-slate-100 px-2 py-1 font-bold text-slate-700">#{item.installment_number}</span><p className="mt-1 text-[9px] text-slate-500">Due {formatDate(item.due_date)}</p></td>
                  <td className="px-3 py-3"><Link href={`/dashboard/members/${item.winner_member_id}`} className="font-bold text-emerald-700 hover:underline">{item.winner_name}</Link></td>
                  <MoneyCell value={item.bid_amount} />
                  <MoneyCell value={item.discount_amount} />
                  <td className="px-3 py-3 font-semibold text-slate-700">{Number(item.commission_percent).toLocaleString("en-IN")}%<p className="mt-1 text-[9px] text-slate-500">{money(item.commission_amount)}</p></td>
                  <MoneyCell value={item.payout_amount} />
                  <MoneyCell value={item.settled_installment_amount} />
                  <MoneyCell value={item.net_payout_amount} />
                  <td className="px-3 py-3"><LifecycleBadge value={item.approved_at ? "approved" : "pending"} /><p className="mt-1 text-[9px] text-slate-500">{item.winner_acknowledged_at ? "Winner acknowledged" : "Awaiting acknowledgement"}</p></td>
                  <td className="px-3 py-3 font-semibold text-slate-700">{item.payout_date ? formatDate(item.payout_date) : "—"}{item.payout_mode && <p className="mt-1 text-[9px] uppercase text-slate-500">{item.payout_mode}{item.payout_reference_number ? ` · ${item.payout_reference_number}` : ""}</p>}{item.payout_verified_at && <p className="mt-1 text-[9px] text-emerald-700">Verified</p>}</td>
                  <td className="px-3 py-3">{item.settlement_proof_file_name ? <Button type="button" variant="outline" size="sm" className="h-7 text-[10px]" onClick={() => void openProof(item)}>View proof</Button> : <Badge variant="outline" className="text-slate-600">Pending</Badge>}<p className="mt-1 max-w-28 truncate text-[9px] text-slate-500">{item.settlement_proof_file_name ?? "No proof"}</p></td>
                  <td className="px-3 py-3"><LifecycleBadge value={item.status} /></td>
                  <td className="px-3 py-3"><div className="flex gap-1">{item.status === "pending" ? (<>
                    <Button type="button" size="sm" disabled={actionLoading === item.id} onClick={() => void approveAuction(item)} className="h-8 bg-emerald-600 text-white hover:bg-emerald-700"><CheckCircle2 className="size-3.5" />{actionLoading === item.id ? "Approving…" : "Approve"}</Button><Button type="button" variant="outline" size="sm" onClick={()=>void openBids(item)}><ListOrdered className="size-3.5"/>Bids</Button><Button type="button" variant="destructive" size="sm" onClick={()=>void cancelAuction(item)}>Cancel</Button></>
                  ) : item.status === "approved" ? (
                    <><Button type="button" size="sm" disabled={actionLoading === item.id} onClick={() => setPayingAuction(item)} className="h-8 bg-emerald-600 text-white hover:bg-emerald-700">Record payout</Button><Button type="button" variant="destructive" size="sm" onClick={()=>void cancelAuction(item)}>Cancel</Button></>
                  ) : <span className="text-slate-500">—</span>}</div></td>
                </tr>
              ))}</tbody>
            </table>
          )}
        </CardContent>
      </Card>

      <Sheet open={Boolean(payingAuction)} onOpenChange={(open) => !open && setPayingAuction(null)}>
        <SheetContent className="overflow-y-auto">
          <SheetHeader className="border-b border-slate-200"><SheetTitle>Record auction payout</SheetTitle><p className="text-xs text-slate-600">{payingAuction?.winner_name} · {payingAuction?.scheme_name} · {payingAuction ? money(payingAuction.net_payout_amount) : ""}</p></SheetHeader>
          {payingAuction && <PayoutForm auction={payingAuction} submitting={actionLoading === payingAuction.id} onSubmit={recordPayout} />}
        </SheetContent>
      </Sheet>
      <Sheet open={Boolean(bidAuction)} onOpenChange={open=>{if(!open){setBidAuction(null);setBidder(null);}}}><SheetContent className="overflow-y-auto"><SheetHeader><SheetTitle>Auction bid register</SheetTitle></SheetHeader>{bidAuction&&<div className="space-y-4 px-4"><form onSubmit={addBid} className="space-y-3"><ReadableSelect label="Bidder" name="bidder_member_id" value={bidder} setValue={setBidder} placeholder="Select bidder" items={members.map(item=>({value:String(item.id),label:`${item.full_name} · ${item.member_code}`}))}/><Input name="bid_amount" type="number" placeholder="Bid amount" required/><Input name="discount_amount" type="number" placeholder="Discount amount" required/><Button type="submit" disabled={!bidder} className="w-full bg-emerald-600 text-white">Record bid</Button></form><div className="space-y-2">{bids.map(item=><div key={item.id} className="rounded-lg border border-slate-200 p-3"><div className="flex justify-between"><p className="text-xs font-bold">#{item.sequence_number} · {item.member_name}</p>{item.is_winning_bid&&<Badge>Winning</Badge>}</div><p className="mt-1 text-xs text-slate-700">Bid {money(item.bid_amount)} · Discount {money(item.discount_amount)}</p></div>)}</div></div>}</SheetContent></Sheet>
    </div>
  );
}

function PayoutForm({ auction, submitting, onSubmit }: { auction: Auction; submitting: boolean; onSubmit: (event: FormEvent<HTMLFormElement>) => void }) {
  const [mode, setMode] = useState<string | null>(null);
  const today = new Date().toISOString().slice(0, 10);
  return (
    <form onSubmit={onSubmit} encType="multipart/form-data" className="space-y-4 px-4 pb-4">
      <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3"><p className="text-[10px] font-semibold text-emerald-800">Verified net payout</p><p className="mt-1 text-lg font-bold text-emerald-900">{money(auction.net_payout_amount)}</p></div>
      <div className="space-y-1.5"><Label htmlFor="payout_date" className="text-xs font-semibold text-slate-700">Payout date</Label><Input id="payout_date" name="payout_date" type="date" defaultValue={today} required className="h-9 border-slate-300 bg-white" /></div>
      <ReadableSelect label="Payout mode" name="payout_mode" value={mode} setValue={setMode} placeholder="Select payout mode" items={payoutModes} required />
      <div className="space-y-1.5"><Label htmlFor="payout_reference_number" className="text-xs font-semibold text-slate-700">Reference number{mode !== "cash" && " *"}</Label><Input id="payout_reference_number" name="payout_reference_number" required={Boolean(mode && mode !== "cash")} placeholder={mode === "cash" ? "Optional for cash" : "Transaction or cheque reference"} className="h-9" /></div>
      <div className="space-y-1.5"><Label htmlFor="settlement_proof" className="text-xs font-semibold text-slate-700">Settlement proof *</Label><Input id="settlement_proof" name="settlement_proof" type="file" accept="application/pdf,image/jpeg,image/png" required className="h-9 file:mr-3" /><p className="text-[10px] text-slate-500">Upload the signed receipt, bank confirmation, or cheque proof.</p></div>
      <Button type="submit" disabled={submitting || !mode} className="w-full bg-emerald-600 text-white hover:bg-emerald-700">{submitting ? "Recording payout…" : "Verify and record payout"}</Button>
    </form>
  );
}

function ReadableSelect({ label, name, value, setValue, placeholder, items, required = false }: { label: string; name?: string; value: string | null; setValue: (value: string | null) => void; placeholder: string; items: SelectOption[]; required?: boolean }) {
  const selectedLabel = items.find((item) => item.value === value)?.label;
  return <div className="space-y-1.5"><Label className="text-[10px] font-semibold text-slate-600">{label}</Label>{name && <input type="hidden" name={name} value={value ?? ""} required={required} />}<Select value={value} onValueChange={setValue}><SelectTrigger className="h-9 w-full border-slate-300 bg-white"><SelectValue>{selectedLabel ?? placeholder}</SelectValue></SelectTrigger><SelectContent>{items.map((item) => <SelectItem key={item.value} value={item.value}>{item.label}</SelectItem>)}</SelectContent></Select></div>;
}

function DateFilter({ label, value, setValue }: { label: string; value: string; setValue: (value: string) => void }) {
  return <div className="space-y-1.5"><Label className="text-[10px] font-semibold text-slate-600">{label}</Label><Input type="date" value={value} onChange={(event) => setValue(event.target.value)} className="h-9 border-slate-300 bg-white" /></div>;
}

function Stat({ icon: Icon, label, value, tone }: { icon: typeof Gavel; label: string; value: string; tone: "emerald" | "blue" | "violet" | "amber" }) {
  const colors = { emerald: "bg-emerald-50 text-emerald-700", blue: "bg-blue-50 text-blue-700", violet: "bg-violet-50 text-violet-700", amber: "bg-amber-50 text-amber-700" };
  return <Card className="border border-slate-200 bg-white py-0 shadow-sm ring-0"><CardContent className="flex items-center gap-3 p-4"><span className={`flex size-10 items-center justify-center rounded-lg ${colors[tone]}`}><Icon className="size-[18px]" /></span><div><p className="text-[10px] font-semibold text-slate-500">{label}</p><p className="mt-0.5 text-lg font-bold text-slate-950">{value}</p></div></CardContent></Card>;
}

function LifecycleBadge({ value }: { value: string }) {
  const styles: Record<string, string> = { pending: "border-amber-200 bg-amber-50 text-amber-700", approved: "border-blue-200 bg-blue-50 text-blue-700", paid: "border-emerald-200 bg-emerald-50 text-emerald-700", cancelled: "border-slate-300 bg-slate-100 text-slate-700", reversed: "border-red-200 bg-red-50 text-red-700" };
  return <Badge variant="outline" className={styles[value] ?? "border-slate-300 bg-slate-50 text-slate-700"}>{title(value)}</Badge>;
}

function MoneyCell({ value }: { value: string }) { return <td className="px-3 py-3 font-semibold text-slate-700">{money(value)}</td>; }
function money(value: string | number) { return `₹${Number(value).toLocaleString("en-IN")}`; }
function formatDate(value: string) { return new Date(`${value.slice(0, 10)}T00:00:00`).toLocaleDateString("en-IN"); }
function title(value: string) { return value.charAt(0).toUpperCase() + value.slice(1); }
