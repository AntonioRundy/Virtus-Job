import * as SecureStore from "expo-secure-store";

export interface StorageAdapter {
  getItem(key: string): Promise<string | null>;
  setItem(key: string, value: string): Promise<void>;
  removeItem(key: string): Promise<void>;
}

export const STORAGE_KEYS = {
  ACCESS_TOKEN: "virtus_access_token",
  REFRESH_TOKEN: "virtus_refresh_token",
} as const;

// Tokens stored in Android Keystore / iOS Keychain — never AsyncStorage.
export const secureStorage: StorageAdapter = {
  getItem: (key) => SecureStore.getItemAsync(key),
  setItem: (key, value) => SecureStore.setItemAsync(key, value),
  removeItem: (key) => SecureStore.deleteItemAsync(key),
};
