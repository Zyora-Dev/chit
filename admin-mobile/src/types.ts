export type Screen = "dashboard" | "members" | "chits" | "collections" | "advances" | "auctions" | "ledger" | "agents" | "tracking" | "employees" | "payroll" | "reports" | "company" | "users" | "audit" | "security";

export type DashboardSummary = {
  today_collections: string;
  month_collections: string;
  active_members: number;
  pending_kyc: number;
  active_groups: number;
  active_scheme_value: string;
  upcoming_auctions: number;
  daily_collections: { date: string; amount: string }[];
  recent_collections: { payment_id: number; receipt_number: string | null; member_name: string; scheme_name: string; group_code: string; amount: string; payment_mode: string; status: string }[];
};

export type OwnerProfile = { id: number; email: string; role: string };
export type LoginResult = { access_token: string | null; refresh_token: string | null; mfa_required: boolean; challenge_token: string | null };
