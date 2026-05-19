import { View, Text, StyleSheet } from "react-native";
import Ionicons from "@expo/vector-icons/Ionicons";

export default function AlertasScreen() {
  return (
    <View style={styles.container}>
      {/* Banner de estado real — funcionalidade ainda não implementada */}
      <View style={styles.banner}>
        <Ionicons name="time-outline" size={16} color="#92400E" />
        <Text style={styles.bannerText}>Funcionalidade em desenvolvimento</Text>
      </View>

      <View style={styles.emptyState}>
        <Ionicons name="notifications-off-outline" size={56} color="#D1D5DB" />
        <Text style={styles.emptyTitle}>Alertas não disponíveis</Text>
        <Text style={styles.emptyBody}>
          Esta funcionalidade ainda não está implementada.{"\n"}
          Brevemente poderá configurar notificações por tipo de oportunidade e província.
        </Text>
      </View>

      <View style={styles.roadmapCard}>
        <Text style={styles.roadmapTitle}>Previsto para próxima versão</Text>
        {[
          "Alertas por tipo (Vaga, Bolsa, Concurso…)",
          "Filtro por província",
          "Notificações push",
          "Alerta de prazo a expirar",
        ].map((item) => (
          <View key={item} style={styles.bulletRow}>
            <Ionicons name="ellipse-outline" size={10} color="#9CA3AF" />
            <Text style={styles.bulletText}>{item}</Text>
          </View>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#F9FAFB" },
  banner: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    backgroundColor: "#FEF3C7",
    borderBottomWidth: 1,
    borderBottomColor: "#FDE68A",
    paddingHorizontal: 16,
    paddingVertical: 10,
  },
  bannerText: { fontSize: 13, color: "#92400E", fontWeight: "600" },
  emptyState: { alignItems: "center", paddingVertical: 48, paddingHorizontal: 32 },
  emptyTitle: { fontSize: 18, fontWeight: "700", color: "#374151", marginTop: 16 },
  emptyBody: {
    fontSize: 14,
    color: "#9CA3AF",
    textAlign: "center",
    marginTop: 10,
    lineHeight: 22,
  },
  roadmapCard: {
    marginHorizontal: 16,
    backgroundColor: "#FFFFFF",
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: "#E5E7EB",
    borderStyle: "dashed",
  },
  roadmapTitle: { fontSize: 13, fontWeight: "700", color: "#9CA3AF", marginBottom: 10, textTransform: "uppercase", letterSpacing: 0.5 },
  bulletRow: { flexDirection: "row", alignItems: "center", gap: 10, marginBottom: 8 },
  bulletText: { fontSize: 13, color: "#9CA3AF", flex: 1 },
});
