"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, KeyRound, Mail } from "lucide-react";
import { FormMessage } from "@/components/auth/form-message";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiRequest } from "@/lib/api";

export default function ForgotPasswordPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false); const [message, setMessage] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); setLoading(true); const data = new FormData(event.currentTarget); try { await apiRequest("/api/v1/auth/forgot-password", { method: "POST", body: JSON.stringify({ email: data.get("email") }) }); router.push(`/reset-password?email=${encodeURIComponent(String(data.get("email")))}`); } catch (err) { setMessage(err instanceof Error ? err.message : "Unable to continue."); } finally { setLoading(false); } }
  return <><div className="mb-8"><span className="flex size-12 items-center justify-center rounded-xl bg-emerald-50 text-emerald-700"><KeyRound className="size-6" /></span><h1 className="mt-6 text-3xl font-bold tracking-tight text-slate-950">Reset your password</h1><p className="mt-3 text-sm leading-6 text-slate-600">Enter your registered email. If an account exists, we will send a secure reset code.</p></div><form onSubmit={submit} className="space-y-5">{message && <FormMessage type="error">{message}</FormMessage>}<div className="space-y-2"><Label htmlFor="email" className="font-semibold text-slate-800">Registered email</Label><div className="relative"><Mail className="absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-slate-500" /><Input id="email" name="email" type="email" required placeholder="owner@company.com" className="h-12 border-slate-300 pl-10 text-slate-950" /></div></div><Button type="submit" disabled={loading} className="h-12 w-full bg-emerald-600 text-base font-semibold text-white hover:bg-emerald-700">{loading ? "Sending code…" : <>Send reset code <ArrowRight className="size-4" /></>}</Button></form><p className="mt-7 text-center text-sm"><Link href="/login" className="font-bold text-emerald-700">Return to sign in</Link></p></>;
}
