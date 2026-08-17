"use client";

import Link from "next/link";
import { FormEvent, Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { ArrowRight, LockKeyhole } from "lucide-react";
import { FormMessage } from "@/components/auth/form-message";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiRequest } from "@/lib/api";

function ResetForm() {
  const params = useSearchParams(); const [loading, setLoading] = useState(false); const [message, setMessage] = useState<{ type: "error" | "success"; text: string } | null>(null);
  async function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); setLoading(true); setMessage(null); const data = new FormData(event.currentTarget); if (data.get("new_password") !== data.get("confirm_password")) { setMessage({ type: "error", text: "Passwords do not match." }); setLoading(false); return; } try { await apiRequest("/api/v1/auth/reset-password", { method: "POST", body: JSON.stringify({ email: data.get("email"), otp: data.get("otp"), new_password: data.get("new_password") }) }); setMessage({ type: "success", text: "Password updated successfully. You can now sign in." }); } catch (err) { setMessage({ type: "error", text: err instanceof Error ? err.message : "Unable to reset password." }); } finally { setLoading(false); } }
  return <><div className="mb-8"><span className="flex size-12 items-center justify-center rounded-xl bg-emerald-50 text-emerald-700"><LockKeyhole className="size-6" /></span><h1 className="mt-6 text-3xl font-bold tracking-tight text-slate-950">Choose a new password</h1><p className="mt-3 text-sm leading-6 text-slate-600">Use the reset code from your email and set a strong new password.</p></div><form onSubmit={submit} className="space-y-4">{message && <FormMessage type={message.type}>{message.text}</FormMessage>}<div className="space-y-2"><Label htmlFor="email" className="font-semibold text-slate-800">Email</Label><Input id="email" name="email" type="email" defaultValue={params.get("email") ?? ""} required className="h-11 border-slate-300 text-slate-950" /></div><div className="space-y-2"><Label htmlFor="otp" className="font-semibold text-slate-800">Six-digit reset code</Label><Input id="otp" name="otp" pattern="[0-9]{6}" maxLength={6} required className="h-11 border-slate-300 tracking-[0.3em] text-slate-950" /></div><div className="space-y-2"><Label htmlFor="new_password" className="font-semibold text-slate-800">New password</Label><Input id="new_password" name="new_password" type="password" minLength={8} required className="h-11 border-slate-300 text-slate-950" /></div><div className="space-y-2"><Label htmlFor="confirm_password" className="font-semibold text-slate-800">Confirm new password</Label><Input id="confirm_password" name="confirm_password" type="password" minLength={8} required className="h-11 border-slate-300 text-slate-950" /></div><Button type="submit" disabled={loading} className="h-12 w-full bg-emerald-600 text-base font-semibold text-white hover:bg-emerald-700">{loading ? "Updating…" : <>Update password <ArrowRight className="size-4" /></>}</Button></form><p className="mt-7 text-center text-sm"><Link href="/login" className="font-bold text-emerald-700">Return to sign in</Link></p></>;
}

export default function ResetPasswordPage() { return <Suspense fallback={<p className="text-sm text-slate-600">Loading…</p>}><ResetForm /></Suspense>; }
