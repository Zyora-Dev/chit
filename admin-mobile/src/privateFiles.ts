import * as FileSystem from "expo-file-system/legacy";
import * as Sharing from "expo-sharing";
import * as SecureStore from "expo-secure-store";
import { ACCESS_KEY, API_URL } from "./api";
export async function downloadPrivate(path:string,fileName:string,mimeType?:string){const token=await SecureStore.getItemAsync(ACCESS_KEY);const safe=fileName.replace(/[^A-Za-z0-9._-]/g,"_");const destination=FileSystem.cacheDirectory+safe;const result=await FileSystem.downloadAsync(`${API_URL}${path}`,destination,{headers:{Authorization:`Bearer ${token}`}});if(result.status<200||result.status>=300)throw new Error("Unable to download private file");await Sharing.shareAsync(result.uri,{mimeType:mimeType,dialogTitle:fileName});}
