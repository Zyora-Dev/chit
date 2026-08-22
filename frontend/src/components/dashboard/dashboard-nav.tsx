"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BanknoteArrowDown,
  BadgeIndianRupee,
  BarChart3,
  BookOpenText,
  Building2,
  CalendarClock,
  ContactRound,
  LayoutDashboard,
  MapPinned,
  ReceiptIndianRupee,
  Settings,
  WalletMinimal,
  ShieldCheck,
  UserRoundCog,
  UsersRound,
  UserCog,
  WalletCards,
} from "lucide-react";
import { cn } from "@/lib/utils";

export const navigation = [
  { label: "Overview", href: "/dashboard", icon: LayoutDashboard },
  { label: "Members", href: "/dashboard/members", icon: UsersRound },
  { label: "Chit groups", href: "/dashboard/chits", icon: WalletCards },
  { label: "Collections", href: "/dashboard/collections", icon: BadgeIndianRupee },
  { label: "Advance payments", href: "/dashboard/advance-payments", icon: BanknoteArrowDown },
  { label: "Expenses", href: "/dashboard/expenses", icon: ReceiptIndianRupee },
  { label: "Ledger", href: "/dashboard/ledger", icon: BookOpenText },
  { label: "Auctions", href: "/dashboard/auctions", icon: CalendarClock },
  { label: "Agents", href: "/dashboard/agents", icon: ContactRound },
  { label: "Agents Tracking", href: "/dashboard/agents/map", icon: MapPinned },
  { label: "Employees", href: "/dashboard/employees", icon: UserRoundCog },
  { label: "Payroll", href: "/dashboard/payroll", icon: WalletMinimal },
  { label: "Reports", href: "/dashboard/reports", icon: BarChart3 },
  { label: "Audit history", href: "/dashboard/audit-history", icon: ShieldCheck },
  { label: "Users & roles", href: "/dashboard/users", icon: UserCog },
];

export function DashboardNav({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  return (
    <nav className="space-y-0.5 px-2.5">
      {navigation.map(({ label, href, icon: Icon }) => {
        const active = pathname === href || (href !== "/dashboard" && pathname.startsWith(`${href}/`));
        return (
          <Link key={href} href={href} onClick={onNavigate} className={cn("flex h-9 items-center gap-2.5 rounded-md px-2.5 text-[13px] font-semibold transition", active ? "bg-emerald-50 text-emerald-800" : "text-slate-700 hover:bg-slate-100 hover:text-slate-950")}>
            <Icon className={cn("size-4", active ? "text-emerald-700" : "text-slate-500")} />
            {label}
          </Link>
        );
      })}
      <div className="my-2.5 border-t border-slate-200" />
      <Link href="/dashboard/company" className="flex h-9 items-center gap-2.5 rounded-md px-2.5 text-[13px] font-semibold text-slate-700 hover:bg-slate-100"><Building2 className="size-4 text-slate-500" />Company profile</Link>
      <Link href="/dashboard/settings" className="flex h-9 items-center gap-2.5 rounded-md px-2.5 text-[13px] font-semibold text-slate-700 hover:bg-slate-100"><Settings className="size-4 text-slate-500" />Settings</Link>
    </nav>
  );
}
