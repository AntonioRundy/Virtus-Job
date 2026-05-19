import { Platform } from "react-native";
import * as Notifications from "expo-notifications";
import * as Device from "expo-device";

export async function setupNotifications(): Promise<void> {
  try {
    // setNotificationHandler must be inside a function, not at module level
    Notifications.setNotificationHandler({
      handleNotification: async () => ({
        shouldShowAlert: true,
        shouldPlaySound: true,
        shouldSetBadge: true,
      }),
    });

    if (!Device.isDevice) return; // skip emulator/simulator/web

    if (Platform.OS === "android") {
      await Notifications.setNotificationChannelAsync("opportunities", {
        name: "Novas Oportunidades",
        importance: Notifications.AndroidImportance.MAX,
        vibrationPattern: [0, 250, 250, 250],
        lightColor: "#1D4ED8",
      });
    }

    const { status: existing } = await Notifications.getPermissionsAsync();
    if (existing !== "granted") {
      await Notifications.requestPermissionsAsync();
    }

    // Push token registration only works in standalone builds, not Expo Go.
    if (__DEV__) return;

    const { virtusApi } = await import("./api");
    const tokenData = await Notifications.getExpoPushTokenAsync();
    await virtusApi.post("/devices", {
      push_token: tokenData.data,
      platform: Platform.OS as "android" | "ios",
    });
  } catch {
    // Non-fatal: notification setup must never crash the app
  }
}
