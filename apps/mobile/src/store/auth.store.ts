import { create } from "zustand";
import type { User } from "@virtus/types";
import { virtusApi } from "@/lib/api";

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  loadUser: () => Promise<void>;
  setUser: (user: User) => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: false,
  isLoading: false,

  login: async (email, password) => {
    set({ isLoading: true });
    try {
      await virtusApi.login(email, password);
      const user = await virtusApi.get<User>("/auth/me");
      set({ user, isAuthenticated: true });
    } finally {
      set({ isLoading: false });
    }
  },

  logout: async () => {
    await virtusApi.logout();
    set({ user: null, isAuthenticated: false });
  },

  loadUser: async () => {
    set({ isLoading: true });
    try {
      const authenticated = await virtusApi.isAuthenticated();
      if (!authenticated) return;
      const user = await virtusApi.get<User>("/auth/me");
      set({ user, isAuthenticated: true });
    } catch {
      // Token invalid or network error — user stays unauthenticated
    } finally {
      set({ isLoading: false });
    }
  },

  setUser: (user) => set({ user }),
}));
