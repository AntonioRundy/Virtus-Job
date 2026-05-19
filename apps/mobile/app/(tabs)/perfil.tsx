import { View, Text, StyleSheet, TouchableOpacity, Alert, ScrollView } from "react-native";
import { useRouter } from "expo-router";
import Ionicons from "@expo/vector-icons/Ionicons";
import { useAuthStore } from "@/store/auth.store";

export default function PerfilScreen() {
  const router = useRouter();
  const { user, isAuthenticated, logout } = useAuthStore();

  const handleLogout = () => {
    Alert.alert("Terminar Sessão", "Tem a certeza que quer sair?", [
      { text: "Cancelar", style: "cancel" },
      {
        text: "Sair",
        style: "destructive",
        onPress: async () => {
          await logout();
          router.replace("/(auth)/login");
        },
      },
    ]);
  };

  if (!isAuthenticated) {
    return (
      <View style={styles.container}>
        <View style={styles.guestState}>
          <Ionicons name="person-circle-outline" size={72} color="#D1D5DB" />
          <Text style={styles.guestTitle}>Entre na sua conta</Text>
          <Text style={styles.guestBody}>
            Faça login para guardar oportunidades e receber alertas personalizados.
          </Text>
          <TouchableOpacity
            style={styles.loginBtn}
            onPress={() => router.push("/(auth)/login")}
          >
            <Text style={styles.loginBtnText}>Iniciar Sessão</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.registerBtn}
            onPress={() => router.push("/(auth)/register")}
          >
            <Text style={styles.registerBtnText}>Criar Conta</Text>
          </TouchableOpacity>
        </View>
      </View>
    );
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Avatar + name */}
      <View style={styles.header}>
        <View style={styles.avatar}>
          <Text style={styles.avatarText}>
            {user?.full_name?.charAt(0).toUpperCase() ?? "U"}
          </Text>
        </View>
        <Text style={styles.name}>{user?.full_name}</Text>
        <Text style={styles.email}>{user?.email}</Text>
        {user?.province && <Text style={styles.province}>{user.province}</Text>}
      </View>

      {/* Menu items — marcados como "Em breve" até implementação */}
      {[
        { icon: "bookmark-outline" as const, label: "Oportunidades Guardadas" },
        { icon: "notifications-outline" as const, label: "Preferências de Alerta" },
        { icon: "settings-outline" as const, label: "Configurações" },
      ].map((item) => (
        <View key={item.label} style={[styles.menuItem, styles.menuItemDisabled]}>
          <Ionicons name={item.icon} size={20} color="#D1D5DB" />
          <Text style={[styles.menuLabel, styles.menuLabelDisabled]}>{item.label}</Text>
          <View style={styles.emBreveBadge}>
            <Text style={styles.emBreveText}>Em breve</Text>
          </View>
        </View>
      ))}

      <TouchableOpacity style={styles.logoutBtn} onPress={handleLogout}>
        <Ionicons name="log-out-outline" size={20} color="#EF4444" />
        <Text style={styles.logoutText}>Terminar Sessão</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#F9FAFB" },
  content: { padding: 16 },
  guestState: { flex: 1, alignItems: "center", justifyContent: "center", padding: 32 },
  guestTitle: { fontSize: 20, fontWeight: "700", color: "#111827", marginTop: 16 },
  guestBody: { fontSize: 14, color: "#6B7280", textAlign: "center", marginTop: 8, lineHeight: 20 },
  loginBtn: {
    backgroundColor: "#1D4ED8",
    borderRadius: 10,
    paddingVertical: 13,
    paddingHorizontal: 40,
    marginTop: 24,
    width: "100%",
    alignItems: "center",
  },
  loginBtnText: { color: "#FFFFFF", fontWeight: "700", fontSize: 15 },
  registerBtn: {
    borderWidth: 1,
    borderColor: "#1D4ED8",
    borderRadius: 10,
    paddingVertical: 13,
    paddingHorizontal: 40,
    marginTop: 10,
    width: "100%",
    alignItems: "center",
  },
  registerBtnText: { color: "#1D4ED8", fontWeight: "700", fontSize: 15 },
  header: { alignItems: "center", paddingVertical: 24 },
  avatar: {
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: "#1D4ED8",
    alignItems: "center",
    justifyContent: "center",
  },
  avatarText: { color: "#FFFFFF", fontSize: 28, fontWeight: "700" },
  name: { fontSize: 20, fontWeight: "700", color: "#111827", marginTop: 12 },
  email: { fontSize: 14, color: "#6B7280", marginTop: 2 },
  province: { fontSize: 13, color: "#9CA3AF", marginTop: 2 },
  menuItem: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#FFFFFF",
    padding: 14,
    borderRadius: 10,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: "#E5E7EB",
    gap: 12,
  },
  menuLabel: { flex: 1, fontSize: 15, color: "#374151" },
  menuItemDisabled: { opacity: 0.6, backgroundColor: "#F9FAFB" },
  menuLabelDisabled: { color: "#9CA3AF" },
  emBreveBadge: {
    backgroundColor: "#F3F4F6",
    borderRadius: 6,
    paddingHorizontal: 7,
    paddingVertical: 3,
  },
  emBreveText: { fontSize: 11, color: "#6B7280", fontWeight: "600" },
  logoutBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    marginTop: 24,
    paddingVertical: 14,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: "#FEE2E2",
    backgroundColor: "#FFF5F5",
  },
  logoutText: { color: "#EF4444", fontWeight: "600", fontSize: 15 },
});
