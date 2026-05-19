import { View, Text, StyleSheet, TouchableOpacity } from "react-native";
import Ionicons from "@expo/vector-icons/Ionicons";
import { formatDistanceToNow, parseISO, isPast, addDays } from "date-fns";
import { pt } from "date-fns/locale";
import type { OpportunityListItem, TrustLevel } from "@virtus/types";
import {
  OPPORTUNITY_TYPE_LABELS, OPPORTUNITY_TYPE_COLORS,
  sourceStatusColor,
} from "@/constants";
import { TrustBadge } from "@/components/TrustBadge";

interface Props {
  item: OpportunityListItem;
  onPress: () => void;
}

export function OpportunityCard({ item, onPress }: Props) {
  const typeColor = OPPORTUNITY_TYPE_COLORS[item.type] ?? "#6B7280";
  const deadlineDate = item.deadline ? parseISO(item.deadline) : null;
  const isExpiringSoon = deadlineDate
    ? !isPast(deadlineDate) && isPast(addDays(deadlineDate, -7))
    : false;
  const isExpired = deadlineDate ? isPast(deadlineDate) : false;

  const timeAgo = formatDistanceToNow(parseISO(item.created_at), {
    addSuffix: true,
    locale: pt,
  });

  const trustLevel = (item.trust_level ?? "UNVERIFIED") as TrustLevel;
  const srcColor = sourceStatusColor(item.source_url_ok);

  return (
    <TouchableOpacity style={styles.card} onPress={onPress} activeOpacity={0.7}>
      <View style={styles.topRow}>
        <View style={{ flexDirection: "row", gap: 6, alignItems: "center", flexWrap: "wrap", flex: 1 }}>
          <View style={[styles.badge, { backgroundColor: `${typeColor}18` }]}>
            <Text style={[styles.badgeText, { color: typeColor }]}>
              {OPPORTUNITY_TYPE_LABELS[item.type] ?? item.type}
            </Text>
          </View>
          <TrustBadge trustLevel={trustLevel} size="sm" />
        </View>
        <Text style={styles.time}>{timeAgo}</Text>
      </View>

      <Text style={styles.title} numberOfLines={2}>
        {item.title}
      </Text>

      <Text style={styles.org} numberOfLines={1}>
        {item.organization?.name ?? item.source_name}
      </Text>

      <View style={styles.metaRow}>
        {item.province ? (
          <View style={styles.meta}>
            <Ionicons name="location-outline" size={12} color="#9CA3AF" />
            <Text style={styles.metaText}>{item.province}</Text>
          </View>
        ) : null}
        {item.modality ? (
          <View style={styles.meta}>
            <Ionicons name="laptop-outline" size={12} color="#9CA3AF" />
            <Text style={styles.metaText}>{item.modality}</Text>
          </View>
        ) : null}
        {item.salary_min ? (
          <View style={styles.meta}>
            <Ionicons name="cash-outline" size={12} color="#9CA3AF" />
            <Text style={styles.metaText}>
              {item.salary_min.toLocaleString()} {item.salary_currency}
            </Text>
          </View>
        ) : null}
      </View>

      {/* Source footer with status indicator */}
      <View style={styles.sourceRow}>
        <Ionicons name="newspaper-outline" size={11} color="#9CA3AF" />
        <Text style={styles.sourceName} numberOfLines={1}>
          {item.organization?.name ?? item.source_name}
        </Text>
        {item.source_url_ok === true && (
          <Ionicons name="checkmark-circle" size={12} color="#059669" />
        )}
        {item.source_url_ok === false && (
          <Ionicons name="warning" size={12} color="#EF4444" />
        )}
      </View>

      {deadlineDate ? (
        <View style={styles.deadline}>
          <Ionicons
            name="calendar-outline"
            size={11}
            color={isExpired ? "#EF4444" : isExpiringSoon ? "#D97706" : "#6B7280"}
          />
          <Text
            style={[
              styles.deadlineText,
              isExpired && { color: "#EF4444" },
              isExpiringSoon && { color: "#D97706" },
            ]}
          >
            {isExpired
              ? "Prazo expirado"
              : `Prazo: ${deadlineDate.toLocaleDateString("pt-AO", { day: "2-digit", month: "short" })}`}
          </Text>
        </View>
      ) : null}
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: "#FFFFFF",
    marginHorizontal: 12,
    marginTop: 10,
    borderRadius: 12,
    padding: 14,
    borderWidth: 1,
    borderColor: "#E5E7EB",
    elevation: 2,
  },
  topRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 8 },
  badge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 5 },
  badgeText: { fontSize: 11, fontWeight: "700" },
  time: { fontSize: 11, color: "#9CA3AF" },
  sourceRow: { flexDirection: "row", alignItems: "center", gap: 4, marginBottom: 4 },
  sourceName: { flex: 1, fontSize: 11, color: "#9CA3AF" },
  title: { fontSize: 15, fontWeight: "700", color: "#111827", lineHeight: 21, marginBottom: 4 },
  org: { fontSize: 13, color: "#6B7280", marginBottom: 8 },
  metaRow: { flexDirection: "row", flexWrap: "wrap", gap: 10, marginBottom: 6 },
  meta: { flexDirection: "row", alignItems: "center", gap: 3 },
  metaText: { fontSize: 12, color: "#9CA3AF" },
  deadline: { flexDirection: "row", alignItems: "center", gap: 4, marginTop: 4 },
  deadlineText: { fontSize: 11, color: "#6B7280" },
});
