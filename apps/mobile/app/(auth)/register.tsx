import { useState } from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
  Alert,
} from "react-native";
import { useRouter } from "expo-router";
import { useAuthStore } from "@/store/auth.store";
import { virtusApi } from "@/lib/api";
import type { RegisterRequest } from "@virtus/types";

export default function RegisterScreen() {
  const router = useRouter();
  const { login } = useAuthStore();
  const [isLoading, setIsLoading] = useState(false);
  const [form, setForm] = useState<RegisterRequest>({
    full_name: "",
    email: "",
    password: "",
  });

  const handleRegister = async () => {
    if (!form.full_name.trim() || !form.email.trim() || !form.password) {
      Alert.alert("Campos obrigatórios", "Preencha todos os campos.");
      return;
    }
    if (form.password.length < 8) {
      Alert.alert("Password fraca", "A password deve ter pelo menos 8 caracteres.");
      return;
    }
    setIsLoading(true);
    try {
      await virtusApi.post("/auth/register", form);
      await login(form.email.toLowerCase(), form.password);
      router.replace("/(tabs)");
    } catch (e: any) {
      Alert.alert("Erro no registo", e.message ?? "Não foi possível criar a conta.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <ScrollView contentContainerStyle={styles.inner} keyboardShouldPersistTaps="handled">
        <Text style={styles.logo}>Virtus Job</Text>
        <Text style={styles.title}>Criar Conta</Text>
        <Text style={styles.subtitle}>
          Registe-se gratuitamente e receba alertas de oportunidades.
        </Text>

        <View style={styles.form}>
          {[
            { key: "full_name", label: "Nome completo", placeholder: "João Silva", type: "default" },
            { key: "email", label: "Email", placeholder: "seu@email.com", type: "email-address" },
            { key: "password", label: "Password", placeholder: "Mínimo 8 caracteres", type: "default" },
          ].map(({ key, label, placeholder, type }) => (
            <View key={key}>
              <Text style={styles.label}>{label}</Text>
              <TextInput
                style={styles.input}
                value={(form as any)[key]}
                onChangeText={(v) => setForm((f) => ({ ...f, [key]: v }))}
                placeholder={placeholder}
                placeholderTextColor="#9CA3AF"
                keyboardType={type as any}
                autoCapitalize={key === "email" ? "none" : "words"}
                autoCorrect={false}
                secureTextEntry={key === "password"}
              />
            </View>
          ))}

          <TouchableOpacity
            style={[styles.btn, isLoading && styles.btnDisabled]}
            onPress={handleRegister}
            disabled={isLoading}
          >
            {isLoading ? (
              <ActivityIndicator color="#FFFFFF" />
            ) : (
              <Text style={styles.btnText}>Criar Conta</Text>
            )}
          </TouchableOpacity>
        </View>

        <TouchableOpacity onPress={() => router.back()}>
          <Text style={styles.switchText}>
            Já tem conta?{" "}
            <Text style={styles.switchLink}>Iniciar Sessão</Text>
          </Text>
        </TouchableOpacity>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#FFFFFF" },
  inner: { padding: 24, paddingTop: 60 },
  logo: { fontSize: 28, fontWeight: "900", color: "#1D4ED8", marginBottom: 32, textAlign: "center" },
  title: { fontSize: 26, fontWeight: "800", color: "#111827", marginBottom: 8 },
  subtitle: { fontSize: 14, color: "#6B7280", lineHeight: 20, marginBottom: 32 },
  form: { gap: 4 },
  label: { fontSize: 13, fontWeight: "600", color: "#374151", marginBottom: 6, marginTop: 12 },
  input: {
    height: 48,
    borderWidth: 1,
    borderColor: "#D1D5DB",
    borderRadius: 10,
    paddingHorizontal: 14,
    fontSize: 15,
    color: "#111827",
    backgroundColor: "#F9FAFB",
  },
  btn: {
    backgroundColor: "#1D4ED8",
    borderRadius: 10,
    height: 50,
    alignItems: "center",
    justifyContent: "center",
    marginTop: 24,
  },
  btnDisabled: { opacity: 0.7 },
  btnText: { color: "#FFFFFF", fontSize: 16, fontWeight: "700" },
  switchText: { textAlign: "center", color: "#6B7280", fontSize: 14, marginTop: 24 },
  switchLink: { color: "#1D4ED8", fontWeight: "600" },
});
