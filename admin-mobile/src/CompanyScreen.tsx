import { useEffect, useState } from "react";
import { Alert, Pressable, RefreshControl, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import * as DocumentPicker from "expo-document-picker";
import * as SecureStore from "expo-secure-store";
import { ACCESS_KEY, API_URL, authRequest } from "./api";
import { colors } from "./theme";

type R = Record<string, unknown>;
const profileKeys = ["name", "legal_name", "mobile_number", "email", "gstin", "pan", "website"] as const;
const addressKeys = ["address_line_1", "address_line_2", "locality", "landmark", "city", "state", "postal_code", "country"] as const;
const branchKeys = ["name", "mobile_number", "email", "manager_name", ...addressKeys] as const;
const stringValues = (keys: readonly string[], source: R) => Object.fromEntries(keys.map(key => [key, String(source[key] ?? (key === "country" ? "India" : ""))]));

export function CompanyScreen({ initial }: { initial: R }) {
  const [data, setData] = useState(initial);
  const [branches, setBranches] = useState<R[]>([]);
  const [editing, setEditing] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [form, setForm] = useState<Record<string, string>>({});
  const [address, setAddress] = useState<Record<string, string>>({ country: "India" });
  const [branch, setBranch] = useState<Record<string, string>>({ country: "India" });
  const [editBranch, setEditBranch] = useState<R | null>(null);

  useEffect(() => { void load(); }, []);
  async function load() {
    setRefreshing(true);
    try {
      const [company, list] = await Promise.all([authRequest<R>("/api/v1/companies/me"), authRequest<R[]>("/api/v1/branches")]);
      setData(company); setBranches(list);
    } finally { setRefreshing(false); }
  }
  function startCompanyEdit() {
    setForm(stringValues(profileKeys, data));
    const addresses = (data.addresses as R[] | undefined) ?? [];
    setAddress(stringValues(addressKeys, addresses.find(item => item.is_primary) ?? addresses[0] ?? {}));
    setEditing(true);
  }
  async function saveCompany() {
    try {
      await authRequest("/api/v1/companies/me", { method: "PUT", body: JSON.stringify({ ...form, addresses: [{ address_type: "registered", is_primary: true, ...address }] }) });
      setEditing(false); await load(); Alert.alert("Saved", "Company and registered address updated.");
    } catch (error) { Alert.alert("Unable to save", error instanceof Error ? error.message : "Request failed"); }
  }
  async function uploadLogo() {
    try {
      const result = await DocumentPicker.getDocumentAsync({ type: ["image/png", "image/jpeg", "image/webp"], copyToCacheDirectory: true });
      if (result.canceled) return;
      const asset = result.assets[0]; const body = new FormData();
      body.append("logo", { uri: asset.uri, name: asset.name, mimeType: asset.mimeType ?? "image/png" } as never);
      const token = await SecureStore.getItemAsync(ACCESS_KEY);
      const response = await fetch(`${API_URL}/api/v1/companies/me/logo`, { method: "POST", headers: { Authorization: `Bearer ${token}` }, body });
      if (!response.ok) throw new Error("Logo upload failed");
      await load(); Alert.alert("Uploaded", "Company logo updated.");
    } catch (error) { Alert.alert("Unable to upload logo", error instanceof Error ? error.message : "Request failed"); }
  }
  function startBranchEdit(item: R) { setEditBranch(item); setBranch(stringValues(branchKeys, item)); }
  async function saveBranch() {
    try {
      await authRequest(editBranch ? `/api/v1/branches/${editBranch.id}` : "/api/v1/branches", { method: editBranch ? "PUT" : "POST", body: JSON.stringify({ ...branch, is_active: editBranch ? Boolean(editBranch.is_active) : true }) });
      setBranch({ country: "India" }); setEditBranch(null); await load(); Alert.alert("Saved", "Branch saved.");
    } catch (error) { Alert.alert("Unable to save branch", error instanceof Error ? error.message : "Request failed"); }
  }
  function deleteBranch(item: R) {
    Alert.alert("Delete branch", `Delete ${item.name}?`, [{ text: "Cancel", style: "cancel" }, { text: "Delete", style: "destructive", onPress: async () => { try { await authRequest(`/api/v1/branches/${item.id}`, { method: "DELETE" }); await load(); } catch (error) { Alert.alert("Unable to delete", error instanceof Error ? error.message : "Request failed"); } } }]);
  }
  const addresses = (data.addresses as R[] | undefined) ?? [];
  return <ScrollView contentContainerStyle={styles.scroll} refreshControl={<RefreshControl refreshing={refreshing} onRefresh={load} colors={[colors.emerald]} />}>
    <Text style={styles.eyebrow}>COMPANY ADMINISTRATION</Text><Text style={styles.title}>Company profile</Text><Text style={styles.subtitle}>{String(data.company_code ?? "")}</Text>
    <View style={styles.card}>
      {editing ? <>
        {profileKeys.map(key => <Input key={key} label={key} value={form[key] ?? ""} setValue={value => setForm(current => ({ ...current, [key]: value }))} />)}
        <Text style={styles.sectionTitle}>Registered address</Text>
        {addressKeys.map(key => <Input key={key} label={key} value={address[key] ?? ""} setValue={value => setAddress(current => ({ ...current, [key]: value }))} />)}
      </> : <>
        {profileKeys.map(key => <Line key={key} label={key} value={data[key]} />)}
        <Line label="logo" value={data.logo_url} />
        <Text style={styles.sectionTitle}>Registered address</Text>
        {addresses.map((item, index) => <View key={index}>{addressKeys.map(key => <Line key={key} label={key} value={item[key]} />)}</View>)}
      </>}
      <View style={styles.buttons}><Action label={editing ? "Save profile" : "Edit company"} onPress={editing ? () => void saveCompany() : startCompanyEdit} /><Action label="Replace logo" secondary onPress={() => void uploadLogo()} /></View>
    </View>
    <Text style={styles.section}>BRANCHES</Text>
    {branches.map(item => <View key={String(item.id)} style={styles.branchCard}><View style={{ flex: 1 }}><Text style={styles.branchName}>{String(item.name)} · {String(item.branch_code)}</Text><Text style={styles.meta}>{String(item.manager_name ?? "No manager")} · {String(item.mobile_number ?? "No phone")}</Text><Text style={styles.meta}>{String(item.address_line_1)}, {String(item.locality ?? "")} {String(item.city)}, {String(item.state)} {String(item.postal_code)}</Text><Text style={[styles.meta, { color: item.is_active ? colors.emeraldDark : colors.red }]}>{item.is_active ? "ACTIVE" : "INACTIVE"}</Text></View><View style={{ gap: 7 }}><Pressable onPress={() => startBranchEdit(item)}><Text style={styles.edit}>Edit</Text></Pressable><Pressable onPress={() => deleteBranch(item)}><Text style={styles.delete}>Delete</Text></Pressable></View></View>)}
    <View style={styles.card}><Text style={styles.cardTitle}>{editBranch ? "Edit branch" : "Create branch"}</Text>{branchKeys.map(key => <Input key={key} label={key} value={branch[key] ?? ""} setValue={value => setBranch(current => ({ ...current, [key]: value }))} />)}{editBranch ? <Pressable onPress={() => setEditBranch({ ...editBranch, is_active: !editBranch.is_active })} style={styles.toggle}><Text style={styles.toggleText}>{editBranch.is_active ? "Set inactive" : "Set active"}</Text></Pressable> : null}<Action label={editBranch ? "Save branch" : "Create branch"} onPress={() => void saveBranch()} /></View>
  </ScrollView>;
}
function Input({ label, value, setValue }: { label: string; value: string; setValue: (value: string) => void }) { return <View style={styles.field}><Text style={styles.label}>{label.replaceAll("_", " ")}</Text><TextInput value={value} onChangeText={setValue} style={styles.input} /></View>; }
function Line({ label, value }: { label: string; value: unknown }) { return <View style={styles.line}><Text style={styles.label}>{label.replaceAll("_", " ")}</Text><Text style={styles.value}>{String(value ?? "—")}</Text></View>; }
function Action({ label, onPress, secondary = false }: { label: string; onPress: () => void; secondary?: boolean }) { return <Pressable style={[styles.action, secondary && styles.secondary]} onPress={onPress}><Text style={[styles.actionText, secondary && styles.secondaryText]}>{label}</Text></Pressable>; }
const styles = StyleSheet.create({scroll:{padding:15,paddingBottom:40},eyebrow:{fontSize:8.5,fontWeight:"900",letterSpacing:1.1,color:colors.emeraldDark},title:{fontSize:23,fontWeight:"900",color:colors.slate950,marginTop:4},subtitle:{fontSize:10,color:colors.emeraldDark,marginTop:3},card:{backgroundColor:colors.white,borderWidth:1,borderColor:colors.border,borderRadius:14,padding:13,marginTop:12},cardTitle:{fontSize:13,fontWeight:"900",color:colors.slate950,marginBottom:9},sectionTitle:{fontSize:9,fontWeight:"900",textTransform:"uppercase",color:colors.emeraldDark,marginTop:12,marginBottom:7},field:{marginBottom:8},label:{fontSize:8.5,fontWeight:"900",textTransform:"uppercase",color:colors.slate500,marginBottom:4},input:{height:39,borderWidth:1,borderColor:"#cbd5e1",borderRadius:8,paddingHorizontal:9,fontSize:11.5},line:{paddingVertical:7,borderBottomWidth:1,borderBottomColor:"#f1f5f9"},value:{fontSize:11,fontWeight:"700",color:colors.slate950},buttons:{flexDirection:"row",gap:7,marginTop:10},action:{height:40,flex:1,borderRadius:9,backgroundColor:colors.emerald,alignItems:"center",justifyContent:"center"},actionText:{fontSize:10.5,fontWeight:"900",color:colors.white},secondary:{backgroundColor:"#ecfdf5",borderWidth:1,borderColor:"#6ee7b7"},secondaryText:{color:colors.emeraldDark},section:{fontSize:9,fontWeight:"900",letterSpacing:1,color:colors.slate500,marginTop:19,marginBottom:8},branchCard:{flexDirection:"row",gap:10,backgroundColor:colors.white,borderWidth:1,borderColor:colors.border,borderRadius:12,padding:12,marginBottom:8},branchName:{fontSize:11.5,fontWeight:"900",color:colors.slate950},meta:{fontSize:9,lineHeight:14,color:colors.slate500,marginTop:3},edit:{fontSize:10,fontWeight:"900",color:colors.emeraldDark},delete:{fontSize:10,fontWeight:"900",color:colors.red},toggle:{height:36,borderWidth:1,borderColor:"#f59e0b",borderRadius:8,alignItems:"center",justifyContent:"center",marginBottom:8},toggleText:{fontSize:10,fontWeight:"900",color:"#b45309"}});
