import "react-native-gesture-handler"; // must be first import
import { useEffect } from "react";
import { Stack, router } from "expo-router";
import { StatusBar } from "expo-status-bar";
import * as SplashScreen from "expo-splash-screen";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useAuthStore } from "@/store/auth.store";
import { setAuthErrorHandler } from "@/lib/api";
import { setupNotifications } from "@/lib/notifications";

SplashScreen.preventAutoHideAsync();

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 2,
      gcTime: 1000 * 60 * 10,
      retry: 2,
      retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 10000),
    },
  },
});

export default function RootLayout() {
  const { loadUser } = useAuthStore();

  useEffect(() => {
    setAuthErrorHandler(() => router.replace("/(auth)/login"));

    async function init() {
      try { await loadUser(); } catch {}
      try { await setupNotifications(); } catch {}
      try { await SplashScreen.hideAsync(); } catch {}
    }
    init();
  }, []);

  // Expo Router v4 already wraps with GestureHandlerRootView + SafeAreaProvider.
  // Do NOT add a second GestureHandlerRootView here — it causes a runtime crash.
  return (
    <QueryClientProvider client={queryClient}>
      <StatusBar style="auto" />
      <Stack screenOptions={{ headerShown: false }}>
        <Stack.Screen name="(tabs)" />
        <Stack.Screen name="(auth)" />
        <Stack.Screen
          name="oportunidade/[slug]"
          options={{
            headerShown: true,
            headerTitle: "",
            headerBackTitle: "Voltar",
            presentation: "card",
          }}
        />
      </Stack>
    </QueryClientProvider>
  );
}
