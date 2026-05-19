import {
  ScrollView, View, Text, StyleSheet,
  TouchableOpacity, Linking, ActivityIndicator, Alert,
} from "react-native";
import { useLocalSearchParams, useNavigation } from "expo-router";
import { useLayoutEffect } from "react";
import Ionicons from "@expo/vector-icons/Ionicons";
import { useQuery } from "@tanstack/react-query";
import { virtusApi } from "@/lib/api";
import type { Opportunity, TrustLevel, ApplicationType } from "@virtus/types";
import {
  OPPORTUNITY_TYPE_LABELS, OPPORTUNITY_TYPE_COLORS,
  TRUST_LABELS, TRUST_SHORT_LABELS, TRUST_COLORS, TRUST_ICONS,
  APPLICATION_TYPE_LABELS, APPLICATION_TYPE_ICONS,
  isSourceClickable, sourceStatusColor, sourceStatusLabel,
} from "@/constants";
import { TrustBadge, TrustScoreBar } from "@/components/TrustBadge";
import { format, parseISO } from "date-fns";
import { pt } from "date-fns/locale";

// ─── Sub-components ──────────────────────────────────────────────────────────

function SourceStatusRow({ ok }: { ok: boolean | null | undefined }) {
  const color = sourceStatusColor(ok);
  const label = sourceStatusLabel(ok);
  const icon: React.ComponentProps<typeof Ionicons>["name"] =
    ok === true ? "checkmark-circle" :
    ok === false ? "close-circle" :
    "help-circle-outline";

  return (
    <View style={styles.statusRow}>
      <Ionicons name={icon} size={13} color={color} />
      <Text style={[styles.statusLabel, { color }]}>{label}</Text>
    </View>
  );
}

function ApplicationCTA({ opp }: { opp: Opportunity }) {
  const clickable = isSourceClickable(opp.source_url_ok);
  const appType = (opp.application_type ?? "URL") as ApplicationType;
  const url = opp.application_url ?? opp.source_url;
  const iconName = APPLICATION_TYPE_ICONS[appType] as React.ComponentProps<typeof Ionicons>["name"];
  const label = APPLICATION_TYPE_LABELS[appType];

  // Link confirmed broken — never open it
  if (!clickable) {
    return (
      <View style={styles.brokenBox}>
        <Ionicons name="warning-outline" size={16} color="#EF4444" />
        <View style={{ flex: 1 }}>
          <Text style={styles.brokenTitle}>Link indisponível</Text>
          <Text style={styles.brokenBody}>
            O link original está temporariamente indisponível. Tente aceder directamente ao site de {opp.source_name}.
          </Text>
        </View>
      </View>
    );
  }

  // Email application
  if (appType === "EMAIL" && opp.contact_email) {
    return (
      <TouchableOpacity
        style={styles.ctaBtn}
        onPress={() => Linking.openURL(`mailto:${opp.contact_email}`)}
        activeOpacity={0.8}
      >
        <Ionicons name="mail" size={16} color="#FFFFFF" />
        <Text style={styles.ctaBtnText}>{opp.contact_email}</Text>
      </TouchableOpacity>
    );
  }

  // In-person — no digital link
  if (appType === "IN_PERSON") {
    return (
      <View style={styles.inPersonBox}>
        <Ionicons name="walk" size={16} color="#D97706" />
        <Text style={styles.inPersonText}>
          Candidatura presencial — não existe link de candidatura online.
          Dirija-se à instituição ou contacte {opp.source_name}.
        </Text>
      </View>
    );
  }

  // URL / FORM / DOCUMENT
  return (
    <TouchableOpacity
      style={styles.ctaBtn}
      onPress={() => Linking.openURL(url)}
      activeOpacity={0.8}
    >
      <Ionicons name={iconName} size={16} color="#FFFFFF" />
      <Text style={styles.ctaBtnText}>{label}</Text>
    </TouchableOpacity>
  );
}

// ─── Main screen ─────────────────────────────────────────────────────────────

export default function OportunidadeScreen() {
  const { slug } = useLocalSearchParams<{ slug: string }>();
  const navigation = useNavigation();

  const { data: opp, isLoading, error } = useQuery<Opportunity>({
    queryKey: ["opportunity", slug],
    queryFn: () => virtusApi.get<Opportunity>(`/opportunities/${slug}`),
    enabled: !!slug,
  });

  useLayoutEffect(() => {
    if (opp) {
      navigation.setOptions({
        headerTitle: OPPORTUNITY_TYPE_LABELS[opp.type] ?? opp.type,
      });
    }
  }, [opp, navigation]);

  if (isLoading) {
    return <View style={styles.center}><ActivityIndicator size="large" color="#1D4ED8" /></View>;
  }

  if (error || !opp) {
    return (
      <View style={styles.center}>
        <Ionicons name="alert-circle-outline" size={48} color="#EF4444" />
        <Text style={styles.errorText}>Oportunidade não encontrada.</Text>
      </View>
    );
  }

  const typeColor = OPPORTUNITY_TYPE_COLORS[opp.type] ?? "#6B7280";
  const trustLevel = (opp.trust_level ?? "UNVERIFIED") as TrustLevel;
  const deadline = opp.deadline
    ? format(parseISO(opp.deadline), "dd 'de' MMMM 'de' yyyy", { locale: pt })
    : null;

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Type badge */}
      <View style={[styles.typeBadge, { backgroundColor: `${typeColor}18` }]}>
        <Text style={[styles.typeText, { color: typeColor }]}>
          {OPPORTUNITY_TYPE_LABELS[opp.type] ?? opp.type}
        </Text>
      </View>

      {/* Title */}
      <Text style={styles.title}>{opp.title}</Text>

      {opp.organization ? (
        <Text style={styles.org}>{opp.organization.name}</Text>
      ) : null}

      {/* Meta */}
      <View style={styles.metaRow}>
        {opp.province ? (
          <View style={styles.metaItem}>
            <Ionicons name="location-outline" size={14} color="#6B7280" />
            <Text style={styles.metaText}>{opp.province}</Text>
          </View>
        ) : null}
        {opp.modality ? (
          <View style={styles.metaItem}>
            <Ionicons name="laptop-outline" size={14} color="#6B7280" />
            <Text style={styles.metaText}>{opp.modality}</Text>
          </View>
        ) : null}
        {deadline ? (
          <View style={styles.metaItem}>
            <Ionicons name="calendar-outline" size={14} color="#EF4444" />
            <Text style={[styles.metaText, { color: "#EF4444" }]}>Prazo: {deadline}</Text>
          </View>
        ) : null}
      </View>

      {/* Salary */}
      {(opp.salary_min || opp.salary_max) ? (
        <View style={styles.salaryBox}>
          <Text style={styles.salaryLabel}>Remuneração</Text>
          <Text style={styles.salaryValue}>
            {opp.salary_min && opp.salary_max
              ? `${opp.salary_min.toLocaleString()} – ${opp.salary_max.toLocaleString()} ${opp.salary_currency}`
              : opp.salary_min
              ? `A partir de ${opp.salary_min.toLocaleString()} ${opp.salary_currency}`
              : `Até ${opp.salary_max!.toLocaleString()} ${opp.salary_currency}`}
          </Text>
        </View>
      ) : null}

      {/* Description */}
      {opp.description_structured ? (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Descrição</Text>
          <Text style={styles.sectionBody}>{opp.description_structured}</Text>
        </View>
      ) : null}

      {/* Requirements */}
      {opp.requirements && opp.requirements.length > 0 ? (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Requisitos</Text>
          {opp.requirements.map((req, i) => (
            <View key={i} style={styles.bulletRow}>
              <View style={styles.bullet} />
              <Text style={styles.bulletText}>{req}</Text>
            </View>
          ))}
        </View>
      ) : null}

      {/* Benefits */}
      {opp.benefits && opp.benefits.length > 0 ? (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Benefícios</Text>
          {opp.benefits.map((b, i) => (
            <View key={i} style={styles.bulletRow}>
              <Ionicons name="checkmark-circle" size={14} color="#059669" />
              <Text style={styles.bulletText}>{b}</Text>
            </View>
          ))}
        </View>
      ) : null}

      {/* ─── Trust & Source block ─────────────────────────────────── */}
      <View style={styles.trustBlock}>
        <Text style={styles.trustBlockTitle}>Credibilidade e Candidatura</Text>

        {/* Trust badge */}
        <View style={styles.trustRow}>
          <TrustBadge trustLevel={trustLevel} size="md" />
        </View>

        {/* Trust score bar */}
        {opp.trust_score !== undefined ? (
          <View style={styles.trustScoreRow}>
            <Text style={styles.trustScoreLabel}>Score de confiança</Text>
            <TrustScoreBar score={opp.trust_score} />
          </View>
        ) : null}

        {/* Source info */}
        <View style={styles.sourceInfo}>
          <Text style={styles.sourceInfoLabel}>Fonte: {opp.source_name}</Text>
          <SourceStatusRow ok={opp.source_url_ok} />
        </View>

        {/* Application CTA */}
        <ApplicationCTA opp={opp} />
      </View>
    </ScrollView>
  );
}

// ─── Styles ──────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#FFFFFF" },
  content: { padding: 20, paddingBottom: 48 },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  errorText: { color: "#6B7280", marginTop: 12, fontSize: 15 },

  typeBadge: { alignSelf: "flex-start", paddingHorizontal: 10, paddingVertical: 4, borderRadius: 6, marginBottom: 12 },
  typeText: { fontSize: 12, fontWeight: "700" },
  title: { fontSize: 22, fontWeight: "800", color: "#111827", lineHeight: 30, marginBottom: 6 },
  org: { fontSize: 15, color: "#6B7280", marginBottom: 12 },

  metaRow: { flexDirection: "row", flexWrap: "wrap", gap: 12, marginBottom: 16 },
  metaItem: { flexDirection: "row", alignItems: "center", gap: 4 },
  metaText: { fontSize: 13, color: "#6B7280" },

  salaryBox: { backgroundColor: "#F0FDF4", borderRadius: 10, padding: 14, marginBottom: 16 },
  salaryLabel: { fontSize: 11, color: "#059669", fontWeight: "600", marginBottom: 4 },
  salaryValue: { fontSize: 17, fontWeight: "700", color: "#065F46" },

  section: { marginBottom: 20 },
  sectionTitle: { fontSize: 16, fontWeight: "700", color: "#111827", marginBottom: 10 },
  sectionBody: { fontSize: 14, color: "#374151", lineHeight: 22 },
  bulletRow: { flexDirection: "row", alignItems: "flex-start", gap: 8, marginBottom: 6 },
  bullet: { width: 6, height: 6, borderRadius: 3, backgroundColor: "#6B7280", marginTop: 7 },
  bulletText: { flex: 1, fontSize: 14, color: "#374151", lineHeight: 20 },

  // ─── Trust block
  trustBlock: {
    marginTop: 8,
    padding: 16,
    borderRadius: 12,
    backgroundColor: "#F9FAFB",
    borderWidth: 1,
    borderColor: "#E5E7EB",
    gap: 12,
  },
  trustBlockTitle: { fontSize: 14, fontWeight: "700", color: "#111827" },
  trustRow: { flexDirection: "row" },
  trustScoreRow: { gap: 6 },
  trustScoreLabel: { fontSize: 11, color: "#6B7280" },

  sourceInfo: { gap: 4 },
  sourceInfoLabel: { fontSize: 12, color: "#6B7280" },
  statusRow: { flexDirection: "row", alignItems: "center", gap: 4 },
  statusLabel: { fontSize: 12, fontWeight: "600" },

  // ─── CTA variants
  ctaBtn: {
    backgroundColor: "#1D4ED8",
    borderRadius: 10,
    height: 48,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    marginTop: 4,
  },
  ctaBtnText: { color: "#FFFFFF", fontSize: 15, fontWeight: "700" },

  brokenBox: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 10,
    backgroundColor: "#FEF2F2",
    borderRadius: 10,
    padding: 12,
    borderWidth: 1,
    borderColor: "#FECACA",
    marginTop: 4,
  },
  brokenTitle: { fontSize: 13, fontWeight: "700", color: "#991B1B", marginBottom: 2 },
  brokenBody: { fontSize: 12, color: "#B91C1C", lineHeight: 18 },

  inPersonBox: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 10,
    backgroundColor: "#FFFBEB",
    borderRadius: 10,
    padding: 12,
    borderWidth: 1,
    borderColor: "#FDE68A",
    marginTop: 4,
  },
  inPersonText: { flex: 1, fontSize: 13, color: "#92400E", lineHeight: 18 },
});
