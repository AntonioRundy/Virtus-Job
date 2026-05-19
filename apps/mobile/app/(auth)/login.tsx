import { useState } from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
  Alert,
} from "react-native";
import { useRouter } from "expo-router";
import { useAuthStore } from "@/store/auth.store";

export default function LoginScreen() {
  const router = useRouter();
  const { login, isLoading } = useAuthStore();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  const handleLogin = async () => {
    if (!email.trim() || !password) {
      Alert.alert("Campos obrigatórios", "Preencha o email e a password.");
      return;
    }
    try {
      await login(email.trim().toLowerCase(), password);
      router.replace("/(tabs)");
    } catch (e: any) {
      Alert.alert("Erro de autenticação", e.message ?? "Email ou password incorrectos.");
    }
  };

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <View style={styles.inner}>
        <Text style={styles.logo}>Virtus Job</Text>
        <Text style={styles.title}>Iniciar Sessão</Text>
        <Text style={styles.subtitle}>
          Entre na sua conta para aceder a todas as funcionalidades.
        </Text>

        <View style={styles.form}>
          <Text style={styles.label}>Email</Text>
          <TextInput
            style={styles.input}
            value={email}
            onChangeText={setEmail}
            placeholder="seu@email.com"
            placeholderTextColor="#9CA3AF"
            keyboardType="email-address"
            autoCapitalize="none"
            autoCorrect={false}
            textContentType="emailAddress"
          />

          <Text style={styles.label}>Password</Text>
          <TextInput
            style={styles.input}
            value={password}
            onChangeText={setPassword}
            placeholder="••••••••"
            placeholderTextColor="#9CA3AF"
            secureTextEntry={!showPassword}
            textContentType="password"
          />

          <TouchableOpacity
            style={[styles.btn, isLoading && styles.btnDisabled]}
            onPress={handleLogin}
            disabled={isLoading}
          >
            {isLoading ? (
              <ActivityIndicator color="#FFFFFF" />
            ) : (
              <Text style={styles.btnText}>Entrar</Text>
            )}
          </TouchableOpacity>
        </View>

        <TouchableOpacity onPress={() => router.push("/(auth)/register")}>
          <Text style={styles.switchText}>
            Não tem conta?{" "}
            <Text style={styles.switchLink}>Criar conta</Text>
          </Text>
        </TouchableOpacity>

        <TouchableOpacity onPress={() => router.replace("/(tabs)")}>
          <Text style={styles.skipText}>Continuar sem conta</Text>
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#FFFFFF" },
  inner: { flex: 1, padding: 24, justifyContent: "center" },
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
  skipText: { textAlign: "center", color: "#9CA3AF", fontSize: 13, marginTop: 12 },
});
