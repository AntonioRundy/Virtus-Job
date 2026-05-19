import { VirtusApiClient } from "./apiClient";
import { secureStorage } from "./storage";
import { Platform } from "react-native";

function resolveApiUrl(): string {
  if (process.env.EXPO_PUBLIC_API_URL) {
    return process.env.EXPO_PUBLIC_API_URL;
  }
  if (Platform.OS === "android") {
    return "http://10.0.2.2:8000";
  }
  return "http://localhost:8000";
}

let _onAuthError: (() => void) | undefined;

export function setAuthErrorHandler(fn: () => void) {
  _onAuthError = fn;
}

export const virtusApi = new VirtusApiClient({
  baseURL: resolveApiUrl(),
  apiPrefix: "/api/v1",
  storage: secureStorage,
  platform: Platform.OS === "android" ? "android" : Platform.OS === "ios" ? "ios" : "web",
  onAuthError: () => _onAuthError?.(),
});
