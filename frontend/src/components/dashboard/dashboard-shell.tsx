"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Bell, ChevronDown, LogOut, Menu, Search, Settings, UserRound } from "lucide-react";
import { Brand } from "@/components/brand";
import { DashboardNav } from "@/components/dashboard/dashboard-nav";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuGroup, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { API_URL, authenticatedApiRequest, clearSession } from "@/lib/api";

type SearchResult={type:string;id:number;title:string;subtitle:string;href:string};
type Notification={id:number;type:string;title:string;message:string;created_at:string;href:string|null;read_at:string|null};
type NotificationFeed={unread_count:number;items:Notification[]};
type CurrentUser={id:number;email:string;role:string};

export function DashboardShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const[query,setQuery]=useState("");const[results,setResults]=useState<SearchResult[]>([]);const[searching,setSearching]=useState(false);const[feed,setFeed]=useState<NotificationFeed>({unread_count:0,items:[]});const[user,setUser]=useState<CurrentUser|null>(null);
  useEffect(()=>{const timer=setTimeout(()=>{if(query.trim().length<2){setResults([]);return;}setSearching(true);void authenticatedApiRequest<SearchResult[]>(`/api/v1/dashboard/search?q=${encodeURIComponent(query.trim())}`).then(setResults).finally(()=>setSearching(false));},250);return()=>clearTimeout(timer);},[query]);
  useEffect(()=>{let active=true;async function load(){const[nextFeed,nextUser]=await Promise.all([authenticatedApiRequest<NotificationFeed>("/api/v1/communications/notifications"),authenticatedApiRequest<CurrentUser>("/api/v1/auth/me")]);if(active){setFeed(nextFeed);setUser(nextUser);}}void load();const interval=setInterval(()=>void load(),30000);return()=>{active=false;clearInterval(interval);};},[]);
  async function openNotification(item:Notification){if(!item.read_at)await authenticatedApiRequest("/api/v1/communications/notifications/read",{method:"POST",body:JSON.stringify({notification_ids:[item.id]})});setFeed(current=>({unread_count:Math.max(0,current.unread_count-(item.read_at?0:1)),items:current.items.map(row=>row.id===item.id?{...row,read_at:new Date().toISOString()}:row)}));if(item.href)navigate(item.href);}
  async function logout() { const refreshToken=localStorage.getItem("zchit_refresh_token");if(refreshToken)await fetch(`${API_URL}/api/v1/auth/logout`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({refresh_token:refreshToken})}).catch(()=>undefined);clearSession();router.replace("/login"); }
  function navigate(href:string){setQuery("");setResults([]);router.push(href);}

  return (
    <div className="min-h-screen bg-slate-50">
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-60 border-r border-slate-200 bg-white lg:flex lg:flex-col">
        <div className="flex h-16 items-center border-b border-slate-200 px-5"><Brand /></div>
        <div className="flex-1 overflow-y-auto py-3"><DashboardNav /></div>
        <div className="border-t border-slate-200 p-3"><div className="rounded-lg bg-slate-950 p-3"><p className="text-[10px] font-bold uppercase tracking-[0.14em] text-emerald-400">Workspace setup</p><div className="mt-2 h-1 overflow-hidden rounded-full bg-white/15"><div className="h-full w-2/3 rounded-full bg-emerald-400" /></div><p className="mt-2 text-[11px] text-slate-300">Company profile · 67%</p></div></div>
      </aside>

      <div className="lg:pl-60">
        <header className="sticky top-0 z-30 flex h-16 items-center border-b border-slate-200 bg-white/95 px-4 backdrop-blur sm:px-5 lg:px-6">
          <Sheet>
            <SheetTrigger render={<Button variant="ghost" size="icon" className="mr-3 lg:hidden" aria-label="Open navigation" />}><Menu className="size-5" /></SheetTrigger>
            <SheetContent side="left" className="w-72 p-0"><SheetHeader className="border-b border-slate-200 px-6 py-5"><SheetTitle><Brand /></SheetTitle></SheetHeader><div className="py-5"><DashboardNav /></div></SheetContent>
          </Sheet>
          <div className="relative hidden max-w-sm flex-1 md:block"><Search className="absolute left-3 top-1/2 z-10 size-4 -translate-y-1/2 text-slate-500" /><Input value={query} onChange={event=>setQuery(event.target.value)} placeholder="Search members, groups, receipts…" className="h-9 border-slate-200 bg-slate-50 pl-9 text-slate-950" />{query.trim().length>=2&&<div className="absolute left-0 right-0 top-11 z-50 max-h-80 overflow-y-auto rounded-lg border border-slate-200 bg-white p-1.5 shadow-xl">{searching?<p className="p-3 text-xs text-slate-600">Searching…</p>:results.length===0?<p className="p-3 text-xs text-slate-600">No matching records.</p>:results.map(item=><button type="button" key={`${item.type}-${item.id}`} onClick={()=>navigate(item.href)} className="flex w-full items-center gap-3 rounded-md px-3 py-2.5 text-left hover:bg-emerald-50"><span className="flex size-8 items-center justify-center rounded-md bg-emerald-50 text-xs font-bold text-emerald-700">{item.type[0].toUpperCase()}</span><span className="min-w-0"><span className="block truncate text-xs font-bold text-slate-950">{item.title}</span><span className="block truncate text-[10px] text-slate-600">{item.subtitle}</span></span></button>)}</div>}</div>
          <div className="ml-auto flex items-center gap-2 sm:gap-3">
            <DropdownMenu><DropdownMenuTrigger render={<Button variant="ghost" size="icon" className="relative size-9 text-slate-700" aria-label="Open notifications"/>}><Bell className="size-[18px]" />{feed.unread_count>0&&<span className="absolute right-1.5 top-1.5 flex size-2 rounded-full bg-emerald-500 ring-2 ring-white"/>}</DropdownMenuTrigger><DropdownMenuContent align="end" className="w-80"><DropdownMenuGroup><DropdownMenuLabel className="flex items-center justify-between"><span>Notifications</span><span className="text-[10px] font-semibold text-emerald-700">{feed.unread_count} need attention</span></DropdownMenuLabel></DropdownMenuGroup><DropdownMenuSeparator/><DropdownMenuGroup>{feed.items.length===0?<p className="p-4 text-center text-xs text-slate-600">No operational notifications.</p>:feed.items.map(item=><DropdownMenuItem key={item.id} onClick={()=>void openNotification(item)} className="items-start py-2.5"><Bell className="mt-0.5 size-4 text-emerald-700"/><span><span className="block text-xs font-bold text-slate-950">{item.title}</span><span className="mt-0.5 block text-[10px] text-slate-600">{item.message} · {new Date(item.created_at).toLocaleString("en-IN")}</span></span></DropdownMenuItem>)}</DropdownMenuGroup></DropdownMenuContent></DropdownMenu>
            <DropdownMenu>
              <DropdownMenuTrigger className="flex h-10 items-center gap-2 rounded-lg px-2 outline-none transition hover:bg-slate-100 focus-visible:ring-2 focus-visible:ring-emerald-500 data-popup-open:bg-slate-100"><Avatar className="size-8"><AvatarFallback className="bg-emerald-100 text-xs font-bold text-emerald-800">{user?.email?.slice(0,2).toUpperCase()??"OA"}</AvatarFallback></Avatar><span className="hidden max-w-44 text-left sm:block"><span className="block truncate text-xs font-bold text-slate-950">{user?.email??"Owner account"}</span><span className="block text-[10px] font-medium capitalize text-slate-500">{user?.role??"owner"}</span></span><ChevronDown className="hidden size-3.5 text-slate-500 transition-transform data-popup-open:rotate-180 sm:block" /></DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56"><DropdownMenuGroup><DropdownMenuLabel>My account</DropdownMenuLabel><DropdownMenuSeparator /><DropdownMenuItem onClick={()=>router.push("/dashboard/company")}><UserRound />Company profile</DropdownMenuItem><DropdownMenuItem onClick={()=>router.push("/dashboard/settings")}><Settings />Security settings</DropdownMenuItem></DropdownMenuGroup><DropdownMenuSeparator /><DropdownMenuItem onClick={logout} className="text-red-700"><LogOut />Sign out</DropdownMenuItem></DropdownMenuContent>
            </DropdownMenu>
          </div>
        </header>
        <main className="p-4 sm:p-5 lg:p-6">{children}</main>
      </div>
    </div>
  );
}
