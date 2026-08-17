import { Screen } from "./types";

export type ModuleConfig = { label: string; icon: string; endpoint: string; collectionKey?: string; subtitle: string };

export const modules: Record<Exclude<Screen,"dashboard">,ModuleConfig> = {
  members:{label:"Members",icon:"◉",endpoint:"/api/v1/members?page_size=100",collectionKey:"items",subtitle:"Member register and KYC"},
  chits:{label:"Chit groups",icon:"◫",endpoint:"/api/v1/chits",subtitle:"Schemes, schedules and status"},
  collections:{label:"Collections",icon:"₹",endpoint:"/api/v1/chits/collections/report",collectionKey:"rows",subtitle:"Receipts and payment records"},
  advances:{label:"Advance payments",icon:"↗",endpoint:"/api/v1/advance-payments",subtitle:"Advance receipts and allocations"},
  auctions:{label:"Auctions",icon:"◆",endpoint:"/api/v1/chits/auctions/all",subtitle:"Bids, winners and payouts"},
  ledger:{label:"Ledger",icon:"▤",endpoint:"/api/v1/chits/ledger/entries",subtitle:"Immutable debit and credit entries"},
  agents:{label:"Agents",icon:"●",endpoint:"/api/v1/admin/collection-agents",subtitle:"Accounts, shifts and status"},
  tracking:{label:"Agents Tracking",icon:"⌖",endpoint:"/api/v1/admin/collection-agents",subtitle:"Live field locations"},
  employees:{label:"Employees",icon:"♟",endpoint:"/api/v1/employees?page_size=100",collectionKey:"items",subtitle:"Employee master and KYC"},
  payroll:{label:"Payroll",icon:"▣",endpoint:"/api/v1/payroll/runs",subtitle:"Monthly payroll processing"},
  reports:{label:"Reports",icon:"▥",endpoint:"/api/v1/dashboard/overall-report",collectionKey:"rows",subtitle:"Consolidated financial timeline"},
  company:{label:"Company",icon:"▦",endpoint:"/api/v1/companies/me",subtitle:"Company identity and compliance"},
  users:{label:"Users & roles",icon:"♙",endpoint:"/api/v1/admin/users",subtitle:"Application access and roles"},
  audit:{label:"Audit history",icon:"✓",endpoint:"/api/v1/audit-logs",subtitle:"Immutable activity history"},
  security:{label:"Security",icon:"⌾",endpoint:"/api/v1/auth/security",subtitle:"MFA, sessions and account protection"},
};

export const menuSections: {title:string;items:Screen[]}[] = [
  {title:"OVERVIEW",items:["dashboard"]},
  {title:"OPERATIONS",items:["members","chits","collections","advances","auctions","ledger"]},
  {title:"FIELD TEAM",items:["agents","tracking"]},
  {title:"WORKFORCE",items:["employees","payroll"]},
  {title:"MANAGEMENT",items:["reports","company","users","audit","security"]},
];

export function moduleTitle(screen:Screen){return screen==="dashboard"?"Dashboard":modules[screen].label;}
export function moduleIcon(screen:Screen){return screen==="dashboard"?"⌂":modules[screen].icon;}
