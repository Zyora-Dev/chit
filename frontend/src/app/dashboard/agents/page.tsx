"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { Ban, MapPinned, Plus, UserCheck } from "lucide-react";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { authenticatedApiRequest } from "@/lib/api";

type Agent = {
  id: number; employee_id: number; employee_code: string; employee_name: string; email: string; status: string; shift_status: string;
  shift_id: number | null; last_latitude: string | null; last_longitude: string | null; last_location_at: string | null;
  assigned_groups: { id: number; group_code: string; scheme_name: string }[];
  assigned_members: { enrollment_id: number; member_id: number; member_code: string; member_name: string; scheme_name: string }[];
};
type Employee = { id: number; employee_code: string; full_name: string; collection_agent_enabled: boolean; is_active: boolean };
type Group = { id: number; group_code: string; scheme_name: string; members: { enrollment_id: number; member_id: number; full_name: string; status: string }[] };

export default function AgentsPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [groups, setGroups] = useState<Group[]>([]);
  const [selected, setSelected] = useState<Agent | null>(null);
  const [updatingAgentId, setUpdatingAgentId] = useState<number | null>(null);
  const [error, setError] = useState("");

  async function load() {
    const [agentData, employeeData, groupData] = await Promise.all([
      authenticatedApiRequest<Agent[]>("/api/v1/admin/collection-agents"),
      authenticatedApiRequest<{ items: Employee[] }>("/api/v1/employees?page_size=100"),
      authenticatedApiRequest<Group[]>("/api/v1/chits"),
    ]);
    setAgents(agentData);
    setEmployees(employeeData.items.filter((item) => item.collection_agent_enabled && item.is_active));
    setGroups(groupData);
  }

  useEffect(() => {
    const timer = setTimeout(() => void load().catch((reason) => setError(reason instanceof Error ? reason.message : "Unable to load agents.")), 0);
    return () => clearTimeout(timer);
  }, []);

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      await authenticatedApiRequest("/api/v1/admin/collection-agents", { method: "POST", body: JSON.stringify({ employee_id: Number(form.get("employee_id")), email: form.get("email"), password: form.get("password") }) });
      await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to create agent."); }
  }

  async function assign(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected) return;
    const form = new FormData(event.currentTarget);
    try {
      await authenticatedApiRequest(`/api/v1/admin/collection-agents/${selected.id}/assignments`, { method: "PUT", body: JSON.stringify({ group_ids: form.getAll("group_ids").map(Number), enrollment_ids: form.getAll("enrollment_ids").map(Number) }) });
      setSelected(null);
      await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to assign collections."); }
  }

  async function updateStatus(agent: Agent) {
    setError(""); setUpdatingAgentId(agent.id);
    try {
      await authenticatedApiRequest(`/api/v1/admin/collection-agents/${agent.id}/status`, { method: "PUT", body: JSON.stringify({ is_active: agent.status !== "active" }) });
      await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to update agent login access."); }
    finally { setUpdatingAgentId(null); }
  }

  return <div className="mx-auto max-w-[1600px] space-y-4">
    <div className="flex items-end justify-between"><div><p className="text-xs font-bold uppercase tracking-[.14em] text-emerald-700">Field collections</p><h1 className="text-2xl font-bold">Collection agents</h1><p className="text-[13px] text-slate-600">Manage assignments, login access, attendance, and routes.</p></div><CreateAgent employees={employees.filter((employee) => !agents.some((agent) => agent.employee_id === employee.id))} onSubmit={create} /></div>
    {error && <p className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}
    <Card className="border border-slate-200 bg-white py-0 ring-0">
      <CardHeader className="flex flex-row items-center justify-between border-b p-4"><div><CardTitle className="text-sm">Agent list</CardTitle><p className="mt-1 text-[10px] text-slate-500">Login access, check-in status, assignments, and map tracking</p></div><Badge variant="outline">{agents.length} agents</Badge></CardHeader>
      <CardContent className="space-y-2 p-3">{agents.length === 0 ? <p className="p-8 text-center text-xs text-slate-500">No collection agents created.</p> : agents.map((agent) => <div key={agent.id} className="flex flex-wrap items-center gap-3 rounded-lg border border-slate-200 bg-white p-3">
        <span className="flex size-9 items-center justify-center rounded-full bg-emerald-100 font-bold text-emerald-800">{agent.employee_name[0]}</span>
        <div className="min-w-0 flex-1"><p className="text-xs font-bold text-slate-950">{agent.employee_name}</p><p className="text-[9px] text-slate-500">{agent.employee_code} · {agent.email}</p><div className="mt-1 flex flex-wrap gap-1">{agent.assigned_groups.map((group) => <span key={`g-${group.id}`} className="rounded bg-emerald-50 px-1.5 py-0.5 text-[8px] font-semibold text-emerald-800">{group.scheme_name}</span>)}{agent.assigned_members.map((member) => <span key={`m-${member.enrollment_id}`} className="rounded bg-blue-50 px-1.5 py-0.5 text-[8px] font-semibold text-blue-800">{member.member_name} · {member.scheme_name}</span>)}{agent.assigned_groups.length === 0 && agent.assigned_members.length === 0 && <span className="text-[8px] text-slate-500">No assignments</span>}</div></div>
        <Badge className={agent.status === "active" ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"}>{agent.status === "active" ? "Login active" : "Login blocked"}</Badge>
        <Badge className={agent.shift_status === "active" ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-700"}>{agent.shift_status === "active" ? "Checked in" : "Not checked in"}</Badge>
        <Button type="button" variant="outline" size="sm" onClick={() => setSelected(agent)}>Assignment</Button>
        <AgentAccessDialog agent={agent} loading={updatingAgentId === agent.id} onConfirm={() => void updateStatus(agent)} />
        <Button nativeButton={false} variant="outline" size="sm" render={<Link href={`/dashboard/agents/map?agent=${agent.id}`} />}><MapPinned className="size-3.5" />View map</Button>
      </div>)}</CardContent>
    </Card>
    <AssignmentSheet selected={selected} groups={groups} onClose={() => setSelected(null)} onSubmit={assign} />
  </div>;
}

function AgentAccessDialog({ agent, loading, onConfirm }: { agent: Agent; loading: boolean; onConfirm: () => void }) {
  const active = agent.status === "active";
  return <AlertDialog><AlertDialogTrigger render={<Button type="button" variant="outline" size="sm" disabled={loading} className={active ? "text-red-700" : "text-emerald-700"} />}>{active ? <Ban className="size-3.5" /> : <UserCheck className="size-3.5" />}{loading ? "Updating..." : active ? "Block login" : "Unblock login"}</AlertDialogTrigger><AlertDialogContent><AlertDialogHeader><AlertDialogTitle>{active ? `Block ${agent.employee_name}?` : `Unblock ${agent.employee_name}?`}</AlertDialogTitle><AlertDialogDescription>{active ? "The agent will be signed out and cannot log in or access Agent APIs. Assignments, collections, and history will remain preserved." : "The agent will be allowed to log in and access their assigned Agent workflows again."}</AlertDialogDescription></AlertDialogHeader><AlertDialogFooter><AlertDialogCancel>Cancel</AlertDialogCancel><AlertDialogAction variant={active ? "destructive" : "default"} onClick={onConfirm}>{active ? "Block login" : "Unblock login"}</AlertDialogAction></AlertDialogFooter></AlertDialogContent></AlertDialog>;
}

function CreateAgent({ employees, onSubmit }: { employees: Employee[]; onSubmit: (event: FormEvent<HTMLFormElement>) => void }) {
  return <Sheet><SheetTrigger render={<Button className="bg-emerald-600 text-white" />}><Plus className="size-4" />Create agent</SheetTrigger><SheetContent><SheetHeader><SheetTitle>Create collection agent</SheetTitle></SheetHeader><form onSubmit={onSubmit} className="space-y-4 px-4"><div><Label>Employee</Label><select name="employee_id" className="h-9 w-full rounded-md border px-3" required><option value="">Select employee</option>{employees.map((item) => <option key={item.id} value={item.id}>{item.full_name} · {item.employee_code}</option>)}</select></div><div><Label>Login email</Label><Input name="email" type="email" required /></div><div><Label>Temporary password</Label><Input name="password" type="password" minLength={8} required /></div><Button type="submit" className="w-full bg-emerald-600 text-white">Create restricted account</Button></form></SheetContent></Sheet>;
}

function AssignmentSheet({ selected, groups, onClose, onSubmit }: { selected: Agent | null; groups: Group[]; onClose: () => void; onSubmit: (event: FormEvent<HTMLFormElement>) => void }) {
  return <Sheet open={Boolean(selected)} onOpenChange={(open) => !open && onClose()}><SheetContent className="overflow-y-auto"><SheetHeader><SheetTitle>Assign collections · {selected?.employee_name}</SheetTitle></SheetHeader><div className="mx-4 rounded-lg bg-emerald-50 p-3 text-xs text-emerald-900"><p className="font-bold">Current assignments</p><p className="mt-1">{selected?.assigned_groups.map((item) => item.scheme_name).join(", ") || "No whole schemes"}</p><p className="mt-1">{selected?.assigned_members.map((item) => `${item.member_name} · ${item.scheme_name}`).join(", ") || "No individual members"}</p></div><form onSubmit={onSubmit} className="space-y-4 px-4"><div><p className="text-xs font-bold">Whole schemes</p>{groups.map((group) => <label key={group.id} className="mt-2 flex gap-2 text-xs"><input type="checkbox" name="group_ids" value={group.id} defaultChecked={Boolean(selected?.assigned_groups.some((item) => item.id === group.id))} />{group.scheme_name} · {group.group_code}</label>)}</div><div><p className="text-xs font-bold">Specific members</p>{groups.flatMap((group) => group.members.filter((member) => member.status === "active").map((member) => <label key={member.enrollment_id} className="mt-2 flex gap-2 text-xs"><input type="checkbox" name="enrollment_ids" value={member.enrollment_id} defaultChecked={Boolean(selected?.assigned_members.some((item) => item.enrollment_id === member.enrollment_id))} />{member.full_name} · {group.scheme_name}</label>))}</div><Button type="submit" className="w-full bg-emerald-600 text-white">Save assignments</Button></form></SheetContent></Sheet>;
}