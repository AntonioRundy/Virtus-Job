import { useState, useCallback } from "react";
import {
  View, Text, TextInput, FlatList, StyleSheet,
  ActivityIndicator, TouchableOpacity, RefreshControl, ScrollView,
} from "react-native";
import { useRouter } from "expo-router";
import Ionicons from "@expo/vector-icons/Ionicons";
import type { OpportunityType } from "@virtus/types";
import { useOpportunities } from "@/hooks/useOpportunities";
import { OpportunityCard } from "@/components/OpportunityCard";
import { ANGOLA_PROVINCES } from "@/constants";

const TYPE_FILTERS: Array<{ label: string; value: OpportunityType | undefined }> = [
  { label: "Todos", value: undefined },
  { label: "Vagas", value: "VAGA" },
  { label: "Concursos", value: "CONCURSO" },
  { label: "Bolsas", value: "BOLSA" },
  { label: "Estágios", value: "ESTAGIO" },
  { label: "Formação", value: "FORMACAO" },
];

const PROVINCE_OPTIONS = ["Todas", ...ANGOLA_PROVINCES] as const;

export default function ExplorarScreen() {
  const router = useRouter();
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [selectedType, setSelectedType] = useState<OpportunityType | undefined>();
  const [selectedProvince, setSelectedProvince] = useState<string | undefined>();
  const [showProvinces, setShowProvinces] = useState(false);
  const [searchTimeout, setSearchTimeout] = useState<ReturnType<typeof setTimeout> | null>(null);

  const { data, fetchNextPage, hasNextPage, isFetchingNextPage, isLoading, refetch } = useOpportunities({
    search: debouncedSearch || undefined,
    type: selectedType,
    province: selectedProvince,
  });

  const items = data?.pages.flatMap((p) => p.items) ?? [];
  const total = data?.pages[0]?.total ?? 0;

  const handleSearchChange = useCallback(
    (text: string) => {
      setSearch(text);
      if (searchTimeout) clearTimeout(searchTimeout);
      const t = setTimeout(() => setDebouncedSearch(text), 400);
      setSearchTimeout(t);
    },
    [searchTimeout]
  );

  const hasActiveFilters = !!selectedType || !!selectedProvince || !!debouncedSearch;

  return (
    <View style={styles.container}>
      {/* Search bar */}
      <View style={styles.searchRow}>
        <Ionicons name="search" size={18} color="#6B7280" style={styles.searchIcon} />
        <TextInput
          style={styles.searchInput}
          placeholder="Pesquisar oportunidades..."
          placeholderTextColor="#9CA3AF"
          value={search}
          onChangeText={handleSearchChange}
          returnKeyType="search"
          autoCorrect={false}
        />
        {search.length > 0 ? (
          <TouchableOpacity onPress={() => { setSearch(""); setDebouncedSearch(""); }}>
            <Ionicons name="close-circle" size={18} color="#9CA3AF" />
          </TouchableOpacity>
        ) : null}
      </View>

      {/* Type filter chips */}
      <FlatList
        horizontal
        data={TYPE_FILTERS}
        keyExtractor={(t) => t.label}
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.chips}
        renderItem={({ item }) => {
          const active = item.value === selectedType || (!item.value && !selectedType);
          return (
            <TouchableOpacity
              style={[styles.chip, active && styles.chipActive]}
              onPress={() => setSelectedType(item.value)}
            >
              <Text style={[styles.chipText, active && styles.chipTextActive]}>
                {item.label}
              </Text>
            </TouchableOpacity>
          );
        }}
        style={styles.chipsRow}
      />

      {/* Province filter + active filter summary */}
      <View style={styles.filterRow}>
        <TouchableOpacity
          style={[styles.provinceBtn, selectedProvince && styles.provinceBtnActive]}
          onPress={() => setShowProvinces(!showProvinces)}
        >
          <Ionicons
            name="location-outline"
            size={14}
            color={selectedProvince ? "#FFFFFF" : "#6B7280"}
          />
          <Text style={[styles.provinceBtnText, selectedProvince && styles.provinceBtnTextActive]}>
            {selectedProvince ?? "Província"}
          </Text>
          <Ionicons
            name={showProvinces ? "chevron-up" : "chevron-down"}
            size={13}
            color={selectedProvince ? "#FFFFFF" : "#9CA3AF"}
          />
        </TouchableOpacity>

        {hasActiveFilters && (
          <TouchableOpacity
            style={styles.clearBtn}
            onPress={() => {
              setSelectedType(undefined);
              setSelectedProvince(undefined);
              setSearch("");
              setDebouncedSearch("");
              setShowProvinces(false);
            }}
          >
            <Text style={styles.clearBtnText}>Limpar</Text>
          </TouchableOpacity>
        )}

        {total > 0 && (
          <Text style={styles.totalText}>{total} resultado{total !== 1 ? "s" : ""}</Text>
        )}
      </View>

      {/* Province dropdown */}
      {showProvinces && (
        <View style={styles.provinceDropdown}>
          <ScrollView style={{ maxHeight: 180 }} showsVerticalScrollIndicator={false}>
            {PROVINCE_OPTIONS.map((p) => {
              const value = p === "Todas" ? undefined : p;
              const active = selectedProvince === value;
              return (
                <TouchableOpacity
                  key={p}
                  style={[styles.provinceOption, active && styles.provinceOptionActive]}
                  onPress={() => { setSelectedProvince(value); setShowProvinces(false); }}
                >
                  <Text style={[styles.provinceOptionText, active && styles.provinceOptionTextActive]}>
                    {p}
                  </Text>
                  {active && <Ionicons name="checkmark" size={14} color="#1D4ED8" />}
                </TouchableOpacity>
              );
            })}
          </ScrollView>
        </View>
      )}

      {/* Results list */}
      <FlatList
        data={items}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => (
          <OpportunityCard
            item={item}
            onPress={() => router.push(`/oportunidade/${item.slug}`)}
          />
        )}
        onEndReached={() => hasNextPage && !isFetchingNextPage && fetchNextPage()}
        onEndReachedThreshold={0.4}
        refreshControl={
          <RefreshControl
            refreshing={isLoading && items.length > 0}
            onRefresh={() => refetch()}
            colors={["#1D4ED8"]}
            tintColor="#1D4ED8"
          />
        }
        ListEmptyComponent={
          isLoading ? (
            <ActivityIndicator style={styles.loader} color="#1D4ED8" />
          ) : (
            <View style={styles.emptyState}>
              <Ionicons name="search-outline" size={40} color="#D1D5DB" />
              <Text style={styles.emptyTitle}>Sem resultados</Text>
              <Text style={styles.emptySubtitle}>
                {hasActiveFilters
                  ? "Tenta ajustar os filtros ou pesquisar por outro termo."
                  : "Ainda não há oportunidades disponíveis."}
              </Text>
            </View>
          )
        }
        ListFooterComponent={isFetchingNextPage ? (
          <ActivityIndicator color="#1D4ED8" style={{ marginVertical: 16 }} />
        ) : null}
        contentContainerStyle={styles.list}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#F9FAFB" },
  searchRow: {
    flexDirection: "row", alignItems: "center", margin: 12,
    paddingHorizontal: 12, backgroundColor: "#FFFFFF",
    borderRadius: 10, borderWidth: 1, borderColor: "#E5E7EB", height: 44,
  },
  searchIcon: { marginRight: 8 },
  searchInput: { flex: 1, fontSize: 15, color: "#111827" },
  chipsRow: { maxHeight: 44 },
  chips: { paddingHorizontal: 12, gap: 8, alignItems: "center" },
  chip: {
    paddingHorizontal: 14, paddingVertical: 6, borderRadius: 20,
    backgroundColor: "#FFFFFF", borderWidth: 1, borderColor: "#E5E7EB",
  },
  chipActive: { backgroundColor: "#1D4ED8", borderColor: "#1D4ED8" },
  chipText: { fontSize: 13, color: "#6B7280", fontWeight: "500" },
  chipTextActive: { color: "#FFFFFF" },
  filterRow: {
    flexDirection: "row", alignItems: "center", gap: 8,
    paddingHorizontal: 12, paddingVertical: 8,
  },
  provinceBtn: {
    flexDirection: "row", alignItems: "center", gap: 5,
    paddingHorizontal: 12, paddingVertical: 7, borderRadius: 8,
    backgroundColor: "#FFFFFF", borderWidth: 1, borderColor: "#E5E7EB",
  },
  provinceBtnActive: { backgroundColor: "#1D4ED8", borderColor: "#1D4ED8" },
  provinceBtnText: { fontSize: 13, color: "#6B7280", fontWeight: "500" },
  provinceBtnTextActive: { color: "#FFFFFF" },
  clearBtn: {
    paddingHorizontal: 10, paddingVertical: 7, borderRadius: 8,
    backgroundColor: "#FEE2E2", borderWidth: 1, borderColor: "#FECACA",
  },
  clearBtnText: { fontSize: 13, color: "#DC2626", fontWeight: "600" },
  totalText: { fontSize: 12, color: "#9CA3AF", flex: 1, textAlign: "right" },
  provinceDropdown: {
    marginHorizontal: 12, backgroundColor: "#FFFFFF",
    borderRadius: 10, borderWidth: 1, borderColor: "#E5E7EB",
    shadowColor: "#000", shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08, shadowRadius: 4, elevation: 3, marginBottom: 4,
  },
  provinceOption: {
    flexDirection: "row", alignItems: "center", justifyContent: "space-between",
    paddingHorizontal: 14, paddingVertical: 10,
    borderBottomWidth: 1, borderBottomColor: "#F3F4F6",
  },
  provinceOptionActive: { backgroundColor: "#EFF6FF" },
  provinceOptionText: { fontSize: 14, color: "#374151" },
  provinceOptionTextActive: { color: "#1D4ED8", fontWeight: "600" },
  list: { paddingBottom: 24 },
  loader: { marginTop: 40 },
  emptyState: { alignItems: "center", marginTop: 60, paddingHorizontal: 32 },
  emptyTitle: { fontSize: 16, fontWeight: "700", color: "#374151", marginTop: 12, marginBottom: 6 },
  emptySubtitle: { fontSize: 14, color: "#9CA3AF", textAlign: "center", lineHeight: 20 },
});
