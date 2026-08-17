import { useEffect, useState } from "react";
import { Pressable, SafeAreaView, StyleSheet, Text } from "react-native";
import { StatusBar } from "expo-status-bar";
import * as SecureStore from "expo-secure-store";
import { NotificationItem, NotificationsModal } from "./src/NotificationsModal";
import { ACCESS_KEY, REFRESH_KEY, authRequest, clearTokens, publicRequest, saveTokens, setSessionExpiredHandler } from "./src/api";
import { ActionModuleScreen } from "./src/ActionModuleScreen";
import { AuditScreen } from "./src/AuditScreen";
import { Drawer, ErrorBox, Header, Loading } from "./src/components";
import { CreateRecordScreen } from "./src/CreateRecordScreen";
import { CompanyScreen } from "./src/CompanyScreen";
import { CollectionsScreen } from "./src/CollectionsScreen";
import { LedgerScreen } from "./src/LedgerScreen";
import { ChitDetailModal } from "./src/ChitDetailModal";
import { DashboardScreen } from "./src/DashboardScreen";
import { LoginScreen } from "./src/LoginScreen";
import { MemberFormModal } from "./src/MemberFormModal";
import { PayrollDetailModal } from "./src/PayrollDetailModal";
import { EmployeeFormModal } from "./src/EmployeeFormModal";
import { modules, moduleTitle } from "./src/modules";
import { ModuleScreen } from "./src/ModuleScreen";
import { ReportsScreen } from "./src/ReportsScreen";
import { RecordDetailModal } from "./src/RecordDetailModal";
import { SecurityScreen } from "./src/SecurityScreen";
import { TrackingScreen } from "./src/TrackingScreen";
import { UsersScreen } from "./src/UsersScreen";
import { colors } from "./src/theme";
import { DashboardSummary, LoginResult, OwnerProfile, Screen } from "./src/types";

type AppState = "loading" | "login" | "app";

export default function App() {
  const [state, setState] = useState<AppState>("loading");
  const [profile, setProfile] = useState<OwnerProfile | null>(null);
  const [screen, setScreen] = useState<Screen>("dashboard");
  const [drawer, setDrawer] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [unread, setUnread] = useState(0);
  const [dashboard, setDashboard] = useState<DashboardSummary | null>(null);
  const [moduleData, setModuleData] = useState<unknown>(null);
  const [securitySessions, setSecuritySessions] = useState<unknown[]>([]);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [createKind, setCreateKind] = useState<"member"|"chit"|"advance"|"payroll"|"agent"|"employee"|"payment"|"auction"|null>(null);
  const [selectedRecord, setSelectedRecord] = useState<Record<string,unknown>|null>(null);
  const [memberForm, setMemberForm] = useState<Record<string,unknown>|"new"|null>(null);
  const [employeeForm, setEmployeeForm] = useState<Record<string,unknown>|"new"|null>(null);

  useEffect(() => { void restore(); }, []);
  useEffect(() => { setSessionExpiredHandler(() => { setProfile(null); setDashboard(null); setModuleData(null); setState("login"); }); return () => setSessionExpiredHandler(null); }, []);
  useEffect(() => { if (state === "app") void loadCurrent(); }, [screen, state]);
  useEffect(() => { if(state!=="app")return;let active=true;async function loadNotifications(){const feed=await authRequest<{unread_count:number;items:NotificationItem[]}>("/api/v1/communications/notifications");if(active){setNotifications(feed.items);setUnread(feed.unread_count);}}void loadNotifications();const interval=setInterval(()=>void loadNotifications(),30000);return()=>{active=false;clearInterval(interval);}; }, [state]);

  async function restore() {
    const token = await SecureStore.getItemAsync(ACCESS_KEY);
    if (!token) { setState("login"); return; }
    try { await bootstrap(token); setState("app"); }
    catch { await clearTokens(); setState("login"); }
  }

  async function bootstrap(access?: string) {
    const me = await authRequest<OwnerProfile>("/api/v1/auth/me", {}, access);
    if (me.role !== "owner") throw new Error("Owner access is required for this app.");
    setProfile(me);
    setDashboard(await authRequest<DashboardSummary>("/api/v1/dashboard", {}, access));
  }

  async function finishLogin(tokens: { access_token: string; refresh_token: string }) {
    await saveTokens(tokens.access_token, tokens.refresh_token);
    await bootstrap(tokens.access_token);
    setState("app");
  }

  async function login(email: string, password: string) {
    const result = await publicRequest<LoginResult>("/api/v1/auth/login", { method: "POST", body: JSON.stringify({ email: email.trim().toLowerCase(), password }) });
    if (result.mfa_required && result.challenge_token) return result.challenge_token;
    if (!result.access_token || !result.refresh_token) throw new Error("Unable to create a secure owner session.");
    await finishLogin({ access_token: result.access_token, refresh_token: result.refresh_token });
    return null;
  }

  async function verifyMfa(challenge: string, code: string) {
    const result = await publicRequest<{ access_token: string; refresh_token: string }>("/api/v1/auth/mfa/verify-login", { method: "POST", body: JSON.stringify({ challenge_token: challenge, code }) });
    await finishLogin(result);
  }

  async function loadCurrent() {
    setLoading(true); setError("");
    try {
      if (screen === "dashboard") { setDashboard(await authRequest<DashboardSummary>("/api/v1/dashboard")); return; }
      setModuleData(await authRequest(modules[screen].endpoint));
      if (screen === "security") setSecuritySessions(await authRequest<unknown[]>("/api/v1/auth/sessions"));
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to load owner data."); }
    finally { setLoading(false); }
  }

  async function openNotification(item:NotificationItem){if(!item.read_at){await authRequest("/api/v1/communications/notifications/read",{method:"POST",body:JSON.stringify({notification_ids:[item.id]})});setUnread(current=>Math.max(0,current-1));setNotifications(current=>current.map(row=>row.id===item.id?{...row,read_at:new Date().toISOString()}:row));}}
  async function refresh() { setRefreshing(true); try { await loadCurrent(); } finally { setRefreshing(false); } }
  async function logout() {
    const refresh = await SecureStore.getItemAsync(REFRESH_KEY);
    if (refresh) await publicRequest("/api/v1/auth/logout", { method: "POST", body: JSON.stringify({ refresh_token: refresh }) }).catch(() => undefined);
    await clearTokens(); setProfile(null); setDashboard(null); setModuleData(null); setDrawer(false); setScreen("dashboard"); setState("login");
  }
  function navigate(next: Screen) { setDrawer(false); setModuleData(null); setScreen(next); }

  if (state === "loading") return <SafeAreaView style={styles.page}><Loading label="Securing owner workspace…" /></SafeAreaView>;
  if (state === "login") return <LoginScreen error={error} onLogin={login} onVerify={verifyMfa} />;
  const actionable = ["advances", "auctions", "payroll", "agents"].includes(screen);
  const createFor = screen==="chits"?"chit":screen==="advances"?"advance":screen==="payroll"?"payroll":screen==="agents"?"agent":screen==="collections"?"payment":screen==="auctions"?"auction":null;
  return <SafeAreaView style={styles.page}><StatusBar style="dark" /><Header title={moduleTitle(screen)} onMenu={() => setDrawer(true)} onNotifications={()=>setNotificationsOpen(true)} unread={unread} />{screen==="members"?<Pressable style={styles.fab} onPress={()=>setMemberForm("new")}><Text style={styles.fabText}>＋</Text></Pressable>:screen==="employees"?<Pressable style={styles.fab} onPress={()=>setEmployeeForm("new")}><Text style={styles.fabText}>＋</Text></Pressable>:createFor?<Pressable style={styles.fab} onPress={()=>setCreateKind(createFor)}><Text style={styles.fabText}>＋</Text></Pressable>:null}{error ? <ErrorBox message={error} /> : null}{screen === "tracking" ? <TrackingScreen /> : loading && !dashboard ? <Loading /> : screen === "dashboard" && dashboard ? <DashboardScreen data={dashboard} refreshing={refreshing} onRefresh={() => void refresh()} /> : screen === "audit" && moduleData !== null ? <AuditScreen initial={moduleData as never} onSelect={setSelectedRecord} /> : screen === "collections" && moduleData !== null ? <CollectionsScreen initial={moduleData as never} onSelect={setSelectedRecord} /> : screen === "ledger" && moduleData !== null ? <LedgerScreen initial={moduleData as never} /> : screen === "reports" && moduleData !== null ? <ReportsScreen initial={moduleData as never} /> : screen === "company" && moduleData !== null ? <CompanyScreen initial={moduleData as never} /> : screen === "users" && moduleData !== null ? <UsersScreen initial={moduleData} onRefresh={loadCurrent} /> : screen === "security" && moduleData !== null ? <SecurityScreen status={moduleData as never} sessions={securitySessions as never} onRefresh={loadCurrent} onSignedOut={() => void logout()} /> : actionable && moduleData !== null ? <ActionModuleScreen screen={screen as "advances"|"auctions"|"payroll"|"users"|"agents"} data={moduleData} refreshing={refreshing} onRefresh={loadCurrent} onSelect={setSelectedRecord} /> : screen !== "dashboard" && moduleData !== null ? <ModuleScreen screen={screen} data={moduleData} refreshing={refreshing} onRefresh={() => void refresh()} onSelect={setSelectedRecord} /> : <Loading label={`Loading ${moduleTitle(screen)}…`} />}<Drawer open={drawer} active={screen} email={profile?.email ?? "Owner"} onClose={() => setDrawer(false)} onNavigate={navigate} onLogout={() => void logout()} />{createKind?<CreateRecordScreen kind={createKind} open onClose={()=>setCreateKind(null)} onCreated={loadCurrent}/>:null}{selectedRecord&&screen==="payroll"?<PayrollDetailModal record={selectedRecord} onClose={()=>setSelectedRecord(null)}/>:selectedRecord&&screen==="chits"?<ChitDetailModal record={selectedRecord} onClose={()=>setSelectedRecord(null)} onChanged={loadCurrent}/>:selectedRecord?<RecordDetailModal screen={screen} record={selectedRecord} onClose={()=>setSelectedRecord(null)} onChanged={loadCurrent} onEditMember={member=>{setSelectedRecord(null);setMemberForm(member);}} onEditEmployee={employee=>{setSelectedRecord(null);setEmployeeForm(employee);}}/>:null}{memberForm?<MemberFormModal open member={memberForm==="new"?null:memberForm} onClose={()=>setMemberForm(null)} onSaved={loadCurrent}/>:null}{employeeForm?<EmployeeFormModal open employee={employeeForm==="new"?null:employeeForm} onClose={()=>setEmployeeForm(null)} onSaved={loadCurrent}/>:null}<NotificationsModal open={notificationsOpen} items={notifications} onClose={()=>setNotificationsOpen(false)} onNavigate={navigate} onOpen={openNotification}/></SafeAreaView>;
}

const styles = StyleSheet.create({ page: { flex: 1, backgroundColor: colors.background }, fab:{position:"absolute",right:18,bottom:22,width:52,height:52,borderRadius:17,backgroundColor:colors.emerald,alignItems:"center",justifyContent:"center",zIndex:40,shadowColor:"#000",shadowOpacity:.2,shadowRadius:8,elevation:7},fabText:{fontSize:28,lineHeight:31,fontWeight:"500",color:colors.white} });
