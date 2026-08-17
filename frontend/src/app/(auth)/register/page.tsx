"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Check, Eye, EyeOff, LockKeyhole, Mail } from "lucide-react";
import { FormMessage } from "@/components/auth/form-message";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiRequest } from "@/lib/api";

export default function RegisterPage() {
  const router = useRouter();
  const [showPassword, setShowPassword] = useState(false); const [loading, setLoading] = useState(false); const [error, setError] = useState("");
  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setLoading(true); setError(""); const data = new FormData(event.currentTarget);
    if (data.get("password") !== data.get("confirmPassword")) { setError("Passwords do not match."); setLoading(false); return; }
    try { await apiRequest("/api/v1/auth/register", { method: "POST", body: JSON.stringify({ email: data.get("email"), password: data.get("password") }) }); router.push(`/verify-email?email=${encodeURIComponent(String(data.get("email")))}`); }
    catch (err) { setError(err instanceof Error ? err.message : "Unable to create account."); } finally { setLoading(false); }
  }
  return <>
    <div className="mb-8"><p className="text-sm font-bold uppercase tracking-[0.16em] text-emerald-700">Owner registration</p><h1 className="mt-3 text-3xl font-bold tracking-tight text-slate-950">Create your zChit workspace</h1><p className="mt-3 text-sm leading-6 text-slate-600">Start with a secure owner account. Company onboarding follows after verification.</p></div>
    <form onSubmit={handleSubmit} className="space-y-5">
      {error && <FormMessage type="error">{error}</FormMessage>}
      <div className="space-y-2"><Label htmlFor="email" className="text-sm font-semibold text-slate-800">Business email</Label><div className="relative"><Mail className="absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-slate-500" /><Input id="email" name="email" type="email" required autoComplete="email" placeholder="owner@company.com" className="h-12 border-slate-300 bg-white pl-10 text-slate-950" /></div></div>
      <div className="space-y-2"><Label htmlFor="password" className="text-sm font-semibold text-slate-800">Create password</Label><div className="relative"><LockKeyhole className="absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-slate-500" /><Input id="password" name="password" type={showPassword ? "text" : "password"} required minLength={8} maxLength={128} placeholder="Minimum 8 characters" className="h-12 border-slate-300 bg-white px-10 text-slate-950" /><button type="button" onClick={() => setShowPassword(!showPassword)} className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-500">{showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}</button></div></div>
      <div className="space-y-2"><Label htmlFor="confirmPassword" className="text-sm font-semibold text-slate-800">Confirm password</Label><Input id="confirmPassword" name="confirmPassword" type={showPassword ? "text" : "password"} required minLength={8} placeholder="Re-enter your password" className="h-12 border-slate-300 bg-white text-slate-950" /></div>
      <div className="grid grid-cols-2 gap-2 rounded-xl border border-slate-200 bg-slate-50 p-4 text-xs font-medium text-slate-700"><span className="flex items-center gap-2"><Check className="size-3.5 text-emerald-600" />8+ characters</span><span className="flex items-center gap-2"><Check className="size-3.5 text-emerald-600" />Securely hashed</span></div>
      <label className="flex items-start gap-3 text-sm leading-5 text-slate-700"><Checkbox required className="mt-0.5" />I agree to the terms of service and privacy policy.</label>
      <Button type="submit" disabled={loading} className="h-12 w-full bg-emerald-600 text-base font-semibold text-white hover:bg-emerald-700">{loading ? "Creating account…" : <>Create owner account <ArrowRight className="size-4" /></>}</Button>
    </form>
    <p className="mt-7 text-center text-sm text-slate-600">Already have an account? <Link href="/login" className="font-bold text-emerald-700">Sign in</Link></p>
  </>;
}
