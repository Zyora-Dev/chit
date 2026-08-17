"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowRight, Building2, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApiRequestError, authenticatedApiRequest } from "@/lib/api";

type Company = { name: string; company_code: string };

export function CompanyStatusBanner() {
  const [company, setCompany] = useState<Company | null | undefined>(undefined);

  useEffect(() => {
    authenticatedApiRequest<Company>("/api/v1/companies/me")
      .then(setCompany)
      .catch((error) => {
        if (error instanceof ApiRequestError && error.status === 404) setCompany(null);
        if (error instanceof ApiRequestError && error.status === 401) {
          localStorage.removeItem("zchit_access_token");
          window.location.replace("/login");
        }
      });
  }, []);

  if (company === undefined) return null;
  if (company) {
    return <div className="flex items-center gap-3 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2"><CheckCircle2 className="size-4 text-emerald-700" /><p className="text-xs font-semibold text-emerald-900">{company.name}</p><span className="ml-auto rounded bg-white px-2 py-1 text-[10px] font-bold text-emerald-700">{company.company_code}</span></div>;
  }

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 sm:flex-row sm:items-center">
      <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-amber-100 text-amber-700"><Building2 className="size-[18px]" /></span>
      <div className="flex-1"><p className="text-sm font-bold text-slate-950">Complete company onboarding</p><p className="mt-0.5 text-[11px] text-slate-600">Add your business identity, registered address, GST details, and logo to activate your workspace.</p></div>
      <Button nativeButton={false} className="h-8 bg-amber-600 px-3 text-xs font-semibold text-white hover:bg-amber-700" render={<Link href="/onboarding/company" />}>Complete setup <ArrowRight className="size-3.5" /></Button>
    </div>
  );
}
