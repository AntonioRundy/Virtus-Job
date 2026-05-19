import { View, Text, StyleSheet } from "react-native";
import Ionicons from "@expo/vector-icons/Ionicons";
import type { TrustLevel } from "@virtus/types";
import { TRUST_COLORS, TRUST_SHORT_LABELS, TRUST_ICONS } from "@/constants";

interface Props {
  trustLevel: TrustLevel;
  size?: "sm" | "md";
}

export function TrustBadge({ trustLevel, size = "sm" }: Props) {
  if (trustLevel === "UNVERIFIED") return null;

  const color = TRUST_COLORS[trustLevel];
  const label = TRUST_SHORT_LABELS[trustLevel];
  const iconName = TRUST_ICONS[trustLevel] as React.ComponentProps<typeof Ionicons>["name"];
  const isLg = size === "md";

  return (
    <View style={[styles.badge, { backgroundColor: color }, isLg && styles.badgeLg]}>
      <Ionicons name={iconName} size={isLg ? 13 : 11} color="#FFFFFF" />
      <Text style={[styles.label, isLg && styles.labelLg]}>{label}</Text>
    </View>
  );
}

export function TrustScoreBar({ score }: { score: number }) {
  const pct = Math.min(100, Math.round(score));
  const color =
    pct >= 85 ? "#1D4ED8" :
    pct >= 75 ? "#059669" :
    pct >= 55 ? "#0D9488" :
    "#9CA3AF";

  return (
    <View style={styles.barRow}>
      <View style={styles.barTrack}>
        <View style={[styles.barFill, { width: `${pct}%` as any, backgroundColor: color }]} />
      </View>
      <Text style={styles.barLabel}>{pct}%</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 20,
    alignSelf: "flex-start",
  },
  badgeLg: {
    paddingHorizontal: 10,
    paddingVertical: 5,
  },
  label: {
    color: "#FFFFFF",
    fontSize: 11,
    fontWeight: "700",
  },
  labelLg: {
    fontSize: 13,
  },
  barRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  barTrack: {
    flex: 1,
    height: 6,
    borderRadius: 3,
    backgroundColor: "#E5E7EB",
    overflow: "hidden",
  },
  barFill: {
    height: "100%",
    borderRadius: 3,
  },
  barLabel: {
    fontSize: 11,
    color: "#6B7280",
    width: 30,
    textAlign: "right",
  },
});
