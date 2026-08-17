import { AlertCircle, CheckCircle2 } from "lucide-react";

export function FormMessage({ type, children }: { type: "error" | "success"; children: React.ReactNode }) {
  const Icon = type === "error" ? AlertCircle : CheckCircle2;
  return (
    <div className={`flex gap-3 rounded-xl border px-4 py-3 text-sm font-medium ${type === "error" ? "border-red-200 bg-red-50 text-red-800" : "border-emerald-200 bg-emerald-50 text-emerald-800"}`}>
      <Icon className="mt-0.5 size-4 shrink-0" />
      <span>{children}</span>
    </div>
  );
}
