"use client";

import { useEffect, useSyncExternalStore } from "react";
import { useRouter } from "next/navigation";

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const ready = useSyncExternalStore(
    () => () => undefined,
    () => Boolean(localStorage.getItem("zchit_access_token")),
    () => false,
  );

  useEffect(() => {
    const token = localStorage.getItem("zchit_access_token");
    if (!token) {
      router.replace("/login");
      return;
    }
  }, [router]);

  if (!ready) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-50">
        <div className="flex flex-col items-center gap-4">
          <span className="size-8 animate-spin rounded-full border-2 border-emerald-600 border-t-transparent" />
          <p className="text-sm font-semibold text-slate-700">Securing your workspace…</p>
        </div>
      </main>
    );
  }

  return children;
}
