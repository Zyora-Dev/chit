"use client";

import Link from "next/link";
import { FormEvent, Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { ArrowRight, MailCheck } from "lucide-react";
import { FormMessage } from "@/components/auth/form-message";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiRequest } from "@/lib/api";

function VerifyForm() {
  const params = useSearchParams(); const [loading, setLoading] = useState(false); const [message, setMessage] = useState<{ type: "error" | "success"; text: string } | null>(null); const email = params.get("email") ?? "";
  async function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); setLoading(true); setMessage(null); const data = new FormData(event.currentTarget); try { await apiRequest("/api/v1/auth/verify-email", { method: "POST", body: JSON.stringify({ email: data.get("email"), otp: data.get("otp") }) }); setMessage({ type: "success", text: "Email verified. You can now sign in." }); } catch (err) { setMessage({ type: "error", text: err instanceof Error ? err.message : "Verification failed." }); } finally { setLoading(false); } }
  async function resend() { setMessage(null); try { await apiRequest("/api/v1/auth/resend-verification", { method: "POST", body: JSON.stringify({ email }) }); setMessage({ type: "success", text: "A new verification code has been sent." }); } catch (err) { setMessage({ type: "error", text: err instanceof Error ? err.message : "Unable to resend code." }); } }
  return <><div className="mb-8"><span className="flex size-12 items-center justify-center rounded-xl bg-emerald-50 text-emerald-700"><MailCheck className="size-6" /></span><h1 className="mt-6 text-3xl font-bold tracking-tight text-slate-950">Verify your email</h1><p className="mt-3 text-sm leading-6 text-slate-600">Enter the six-digit code sent to your business email. It expires in 10 minutes.</p></div><form onSubmit={submit} className="space-y-5">{message && <FormMessage type={message.type}>{message.text}</FormMessage>}<div className="space-y-2"><Label htmlFor="email" className="font-semibold text-slate-800">Email address</Label><Input id="email" name="email" type="email" defaultValue={email} required className="h-12 border-slate-300 text-slate-950" /></div><div className="space-y-2"><Label htmlFor="otp" className="font-semibold text-slate-800">Verification code</Label><Input id="otp" name="otp" inputMode="numeric" pattern="[0-9]{6}" maxLength={6} required placeholder="000000" className="h-14 border-slate-300 text-center text-2xl font-bold tracking-[0.45em] text-slate-950" /></div><Button type="submit" disabled={loading} className="h-12 w-full bg-emerald-600 text-base font-semibold text-white hover:bg-emerald-700">{loading ? "Verifying…" : <>Verify email <ArrowRight className="size-4" /></>}</Button></form><div className="mt-7 flex items-center justify-between text-sm"><button type="button" onClick={resend} className="font-bold text-emerald-700">Resend code</button><Link href="/login" className="font-semibold text-slate-700">Back to sign in</Link></div></>;
}

export default function VerifyEmailPage() { return <Suspense fallback={<p className="text-sm text-slate-600">Loading verification…</p>}><VerifyForm /></Suspense>; }
