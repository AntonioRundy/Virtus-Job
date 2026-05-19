export interface StorageAdapter {
  getItem(key: string): Promise<string | null>;
  setItem(key: string, value: string): Promise<void>;
  removeItem(key: string): Promise<void>;
}

// Web adapter — wraps localStorage
export const webStorage: StorageAdapter = {
  getItem: (key) => Promise.resolve(
    typeof window !== "undefined" ? localStorage.getItem(key) : null
  ),
  setItem: (key, value) => {
    if (typeof window !== "undefined") localStorage.setItem(key, value);
    return Promise.resolve();
  },
  removeItem: (key) => {
    if (typeof window !== "undefined") localStorage.removeItem(key);
    return Promise.resolve();
  },
};

export const STORAGE_KEYS = {
  ACCESS_TOKEN: "virtus_access_token",
  REFRESH_TOKEN: "virtus_refresh_token",
} as const;
