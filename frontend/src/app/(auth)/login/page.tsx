"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, ArrowRight, Eye, EyeOff, KeyRound, LockKeyhole, Mail } from "lucide-react";
import { FormMessage } from "@/components/auth/form-message";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiRequestError, apiRequest, authenticatedApiRequest, saveSession } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [challengeToken, setChallengeToken] = useState<string | null>(null);
  const [mfaCode, setMfaCode] = useState("");

  async function completeLogin(result: { access_token: string; refresh_token: string }) {
    saveSession(result);
    try {
      await authenticatedApiRequest("/api/v1/companies/me");
      router.push("/dashboard");
    } catch (companyError) {
      if (companyError instanceof ApiRequestError && companyError.status === 404) router.push("/onboarding/company");
      else throw companyError;
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setLoading(true); setError("");
    const data = new FormData(event.currentTarget);
    try {
      const result = await apiRequest<{ access_token: string | null; refresh_token: string | null; mfa_required: boolean; challenge_token: string | null }>("/api/v1/auth/login", { method: "POST", body: JSON.stringify({ email: data.get("email"), password: data.get("password") }) });
      if (result.mfa_required && result.challenge_token) { setChallengeToken(result.challenge_token); return; }
      if (!result.access_token || !result.refresh_token) throw new Error("Unable to create a secure session.");
      await completeLogin({ access_token: result.access_token, refresh_token: result.refresh_token });
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to sign in."); } finally { setLoading(false); }
  }

  async function verifyMfa(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!challengeToken) return; setLoading(true); setError("");
    try { const result=await apiRequest<{access_token:string;refresh_token:string}>("/api/v1/auth/mfa/verify-login",{method:"POST",body:JSON.stringify({challenge_token:challengeToken,code:mfaCode})});await completeLogin(result); }
    catch(err){setError(err instanceof Error?err.message:"Unable to verify two-factor authentication.");}finally{setLoading(false);}
  }

  return <>
    <div className="mb-9"><p className="text-sm font-bold uppercase tracking-[0.16em] text-emerald-700">Welcome back</p><h1 className="mt-3 text-3xl font-bold tracking-tight text-slate-950">Sign in to your workspace</h1><p className="mt-3 text-sm leading-6 text-slate-600">Access collections, members, field operations, and reports securely.</p></div>
    {challengeToken ? <form onSubmit={verifyMfa} className="space-y-5">
      {error && <FormMessage type="error">{error}</FormMessage>}
      <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4"><div className="flex items-center gap-3"><KeyRound className="size-5 text-emerald-700"/><div><p className="font-bold text-slate-950">Two-factor authentication</p><p className="mt-1 text-xs text-slate-600">Enter your 6-digit authenticator code or one recovery code.</p></div></div></div>
      <div className="space-y-2"><Label htmlFor="mfa-code" className="text-sm font-semibold text-slate-800">Security code</Label><Input id="mfa-code" value={mfaCode} onChange={event=>setMfaCode(event.target.value)} required autoFocus autoComplete="one-time-code" placeholder="000000 or recovery code" className="h-12 text-center font-mono text-lg tracking-widest"/></div>
      <Button type="submit" disabled={loading} className="h-12 w-full bg-emerald-600 text-white hover:bg-emerald-700">{loading?"Verifying…":"Verify and sign in"}<ArrowRight className="size-4"/></Button>
      <Button type="button" variant="ghost" className="w-full" onClick={()=>{setChallengeToken(null);setMfaCode("");setError("");}}><ArrowLeft className="size-4"/>Back to password</Button>
    </form> : <form onSubmit={handleSubmit} className="space-y-5">
      {error && <FormMessage type="error">{error}</FormMessage>}
      <div className="space-y-2"><Label htmlFor="email" className="text-sm font-semibold text-slate-800">Work email</Label><div className="relative"><Mail className="absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-slate-500" /><Input id="email" name="email" type="email" required autoComplete="email" placeholder="you@company.com" className="h-12 border-slate-300 bg-white pl-10 text-slate-950" /></div></div>
      <div className="space-y-2"><div className="flex items-center justify-between"><Label htmlFor="password" className="text-sm font-semibold text-slate-800">Password</Label><Link href="/forgot-password" className="text-sm font-semibold text-emerald-700 hover:text-emerald-800">Forgot password?</Link></div><div className="relative"><LockKeyhole className="absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-slate-500" /><Input id="password" name="password" type={showPassword ? "text" : "password"} required minLength={8} autoComplete="current-password" placeholder="Enter your password" className="h-12 border-slate-300 bg-white px-10 text-slate-950" /><button type="button" onClick={() => setShowPassword(!showPassword)} className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-500" aria-label="Toggle password visibility">{showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}</button></div></div>
      <label className="flex items-center gap-3 text-sm font-medium text-slate-700"><Checkbox id="remember" />Keep me signed in on this device</label>
      <Button type="submit" disabled={loading} className="h-12 w-full bg-emerald-600 text-base font-semibold text-white hover:bg-emerald-700">{loading ? "Signing in…" : <>Sign in securely <ArrowRight className="size-4" /></>}</Button>
    </form>}
    <p className="mt-8 text-center text-sm text-slate-600">New to zChit? <Link href="/register" className="font-bold text-emerald-700 hover:text-emerald-800">Create your owner account</Link></p>
  </>;
}
