"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, ArrowRight, Building2, Check, ImagePlus, Landmark, MapPin, ShieldCheck } from "lucide-react";
import { FormMessage } from "@/components/auth/form-message";
import { Brand } from "@/components/brand";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { API_URL, ApiRequestError, authenticatedApiRequest, getResponseError } from "@/lib/api";

const fieldClass = "h-10 border-slate-300 bg-white text-sm text-slate-950";

export default function CompanyOnboardingPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [logo, setLogo] = useState<File | null>(null);

  useEffect(() => {
    if (!localStorage.getItem("zchit_access_token")) router.replace("/login");
  }, [router]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setLoading(true); setError("");
    const data = new FormData(event.currentTarget);
    const optional = (name: string) => String(data.get(name) ?? "").trim() || null;
    try {
      await authenticatedApiRequest("/api/v1/companies", {
        method: "POST",
        body: JSON.stringify({
          name: data.get("name"), legal_name: optional("legal_name"),
          mobile_number: data.get("mobile_number"), email: data.get("email"),
          gstin: optional("gstin"), pan: optional("pan"), website: optional("website"),
          addresses: [{
            address_type: "registered", is_primary: true,
            address_line_1: data.get("address_line_1"), address_line_2: optional("address_line_2"),
            locality: optional("locality"), city: data.get("city"), state: data.get("state"),
            postal_code: data.get("postal_code"), country: "India", landmark: optional("landmark"),
          }],
        }),
      });

      if (logo) {
        const form = new FormData(); form.append("logo", logo);
        const token = localStorage.getItem("zchit_access_token");
        const response = await fetch(`${API_URL}/api/v1/companies/me/logo`, { method: "POST", headers: { Authorization: `Bearer ${token}` }, body: form });
        if (!response.ok) throw new Error(await getResponseError(response, "Company saved, but logo upload failed."));
      }
      router.push("/dashboard");
    } catch (err) {
      if (err instanceof ApiRequestError && err.status === 401) {
        localStorage.removeItem("zchit_access_token");
        router.replace("/login");
      } else if (err instanceof ApiRequestError && err.status === 409) router.push("/dashboard");
      else setError(err instanceof Error ? err.message : "Unable to complete company onboarding.");
    } finally { setLoading(false); }
  }

  return (
    <main className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white"><div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-5"><Brand /><Link href="/dashboard" className="flex items-center gap-2 text-sm font-semibold text-slate-600 hover:text-emerald-700"><ArrowLeft className="size-4" />Dashboard</Link></div></header>
      <div className="mx-auto grid max-w-6xl gap-6 px-5 py-6 lg:grid-cols-[250px_1fr]">
        <aside className="h-fit rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-emerald-700">Workspace setup</p><h1 className="mt-2 text-lg font-bold text-slate-950">Company onboarding</h1><p className="mt-1 text-xs leading-5 text-slate-600">Complete your business profile before starting operations.</p>
          <Progress value={67} className="mt-4 h-1.5 bg-slate-100 [&_[data-slot=progress-indicator]]:bg-emerald-600" />
          <div className="mt-5 space-y-3 text-xs font-semibold"><div className="flex items-center gap-2 text-emerald-700"><span className="flex size-6 items-center justify-center rounded-full bg-emerald-100"><Check className="size-3.5" /></span>Owner account</div><div className="flex items-center gap-2 text-slate-950"><span className="flex size-6 items-center justify-center rounded-full bg-slate-950 text-[10px] text-white">2</span>Company details</div><div className="flex items-center gap-2 text-slate-500"><span className="flex size-6 items-center justify-center rounded-full bg-slate-100 text-[10px]">3</span>Start operations</div></div>
          <div className="mt-5 rounded-lg bg-emerald-50 p-3"><ShieldCheck className="size-4 text-emerald-700" /><p className="mt-2 text-[11px] leading-4 text-emerald-900">Your company receives a unique zChit code automatically.</p></div>
        </aside>

        <form onSubmit={submit} className="space-y-4">
          {error && <FormMessage type="error">{error}</FormMessage>}
          <Card className="overflow-visible border border-slate-200 bg-white py-0 shadow-sm ring-0"><CardHeader className="border-b border-slate-200 p-4"><div className="flex items-center gap-3"><span className="flex size-9 items-center justify-center rounded-lg bg-emerald-50 text-emerald-700"><Building2 className="size-[18px]" /></span><div><CardTitle className="text-sm font-bold text-slate-950">Company identity</CardTitle><p className="mt-0.5 text-[11px] text-slate-500">Official business and contact information</p></div></div></CardHeader><CardContent className="overflow-visible p-4"><div className="grid gap-4 sm:grid-cols-2"><Field label="Company name" name="name" required placeholder="Zyora Chits" /><Field label="Legal name" name="legal_name" placeholder="Zyora Chits Private Limited" /><Field label="Business email" name="email" type="email" required placeholder="accounts@company.com" /><Field label="Mobile number" name="mobile_number" type="tel" required placeholder="+919876543210" /><Field label="GSTIN" name="gstin" maxLength={15} placeholder="33ABCDE1234F1Z5" /><Field label="PAN" name="pan" maxLength={10} placeholder="ABCDE1234F" /><div className="sm:col-span-2"><Field label="Website" name="website" type="url" placeholder="https://company.com" /></div></div></CardContent></Card>

          <Card className="overflow-visible border border-slate-200 bg-white py-0 shadow-sm ring-0"><CardHeader className="border-b border-slate-200 p-4"><div className="flex items-center gap-3"><span className="flex size-9 items-center justify-center rounded-lg bg-blue-50 text-blue-700"><MapPin className="size-[18px]" /></span><div><CardTitle className="text-sm font-bold text-slate-950">Registered address</CardTitle><p className="mt-0.5 text-[11px] text-slate-500">Primary address for business records</p></div></div></CardHeader><CardContent className="overflow-visible p-4"><div className="grid gap-4 sm:grid-cols-2"><div className="sm:col-span-2"><Field label="Address line 1" name="address_line_1" required placeholder="Door number, street" /></div><div className="sm:col-span-2"><Field label="Address line 2" name="address_line_2" placeholder="Building, floor, area" /></div><Field label="Locality" name="locality" placeholder="Locality" /><Field label="Landmark" name="landmark" placeholder="Nearby landmark" /><Field label="City" name="city" required placeholder="Nagercoil" /><Field label="State" name="state" required placeholder="Tamil Nadu" /><Field label="Postal code" name="postal_code" required placeholder="629001" /><div className="space-y-1.5"><Label className="text-xs font-semibold text-slate-700">Country</Label><Input value="India" readOnly className={`${fieldClass} bg-slate-50`} /></div></div></CardContent></Card>

          <Card className="overflow-visible border border-slate-200 bg-white py-0 shadow-sm ring-0"><CardContent className="overflow-visible p-4"><div className="flex flex-col gap-4 sm:flex-row sm:items-center"><span className="flex size-12 shrink-0 items-center justify-center rounded-xl border border-dashed border-slate-300 bg-slate-50 text-slate-500"><ImagePlus className="size-5" /></span><div className="flex-1"><p className="text-sm font-bold text-slate-950">Company logo <span className="font-medium text-slate-500">(optional)</span></p><p className="mt-1 text-[11px] text-slate-500">PNG, JPEG, or WebP · maximum 5 MB</p></div><label className="cursor-pointer rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"><input type="file" accept="image/png,image/jpeg,image/webp" className="hidden" onChange={(event) => setLogo(event.target.files?.[0] ?? null)} />{logo ? logo.name : "Choose logo"}</label></div></CardContent></Card>

          <div className="flex flex-col-reverse gap-3 sm:flex-row sm:items-center sm:justify-between"><p className="flex items-center gap-2 text-[11px] text-slate-500"><Landmark className="size-3.5" />A unique company code will be generated on completion.</p><Button type="submit" disabled={loading} className="h-10 bg-emerald-600 px-5 font-semibold text-white hover:bg-emerald-700">{loading ? "Creating workspace…" : <>Complete onboarding <ArrowRight className="size-4" /></>}</Button></div>
        </form>
      </div>
    </main>
  );
}

function Field({ label, name, required, type = "text", placeholder, maxLength }: { label: string; name: string; required?: boolean; type?: string; placeholder?: string; maxLength?: number }) {
  return <div className="space-y-1.5"><Label htmlFor={name} className="text-xs font-semibold text-slate-700">{label}{required && <span className="text-red-600"> *</span>}</Label><Input id={name} name={name} type={type} required={required} maxLength={maxLength} placeholder={placeholder} className={fieldClass} /></div>;
}
