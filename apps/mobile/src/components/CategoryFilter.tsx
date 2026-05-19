import { ScrollView, TouchableOpacity, Text, StyleSheet, View } from "react-native";
import type { OpportunityType } from "@virtus/types";
import { OPPORTUNITY_TYPE_COLORS } from "@/constants";

const TYPES: Array<{ value: OpportunityType | undefined; label: string }> = [
  { value: undefined, label: "Todos" },
  { value: "VAGA", label: "Vagas" },
  { value: "CONCURSO", label: "Concursos" },
  { value: "BOLSA", label: "Bolsas" },
  { value: "ESTAGIO", label: "Estágios" },
  { value: "FORMACAO", label: "Formação" },
];

interface Props {
  selected: OpportunityType | undefined;
  onSelect: (type: OpportunityType | undefined) => void;
}

export function CategoryFilter({ selected, onSelect }: Props) {
  return (
    <View style={styles.wrapper}>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.row}
      >
        {TYPES.map(({ value, label }) => {
          const active = value === selected || (!value && !selected);
          const color = value ? (OPPORTUNITY_TYPE_COLORS[value] ?? "#1D4ED8") : "#1D4ED8";
          return (
            <TouchableOpacity
              key={label}
              style={[styles.chip, active && { backgroundColor: color, borderColor: color }]}
              onPress={() => onSelect(value)}
              activeOpacity={0.7}
            >
              <Text style={[styles.chipText, active && styles.chipTextActive]}>
                {label}
              </Text>
            </TouchableOpacity>
          );
        })}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: { backgroundColor: "#FFFFFF", borderBottomWidth: 1, borderBottomColor: "#F3F4F6" },
  row: { paddingHorizontal: 12, paddingVertical: 10, gap: 8 },
  chip: {
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: "#E5E7EB",
    backgroundColor: "#FFFFFF",
  },
  chipText: { fontSize: 13, fontWeight: "600", color: "#6B7280" },
  chipTextActive: { color: "#FFFFFF" },
});
