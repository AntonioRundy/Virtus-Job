import { useCallback, useState } from "react";
import {
  View,
  Text,
  FlatList,
  StyleSheet,
  RefreshControl,
  ActivityIndicator,
  TouchableOpacity,
} from "react-native";
import { useRouter } from "expo-router";
import { useOpportunities } from "@/hooks/useOpportunities";
import { OpportunityCard } from "@/components/OpportunityCard";
import { CategoryFilter } from "@/components/CategoryFilter";
import type { OpportunityType } from "@virtus/types";

export default function HomeScreen() {
  const router = useRouter();
  const [selectedType, setSelectedType] = useState<OpportunityType | undefined>();

  const { data, fetchNextPage, hasNextPage, isFetchingNextPage, isLoading, refetch, isRefetching } =
    useOpportunities({ type: selectedType });

  const items = data?.pages.flatMap((p) => p.items) ?? [];

  const handleEndReached = useCallback(() => {
    if (hasNextPage && !isFetchingNextPage) fetchNextPage();
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

  return (
    <View style={styles.container}>
      <CategoryFilter selected={selectedType} onSelect={setSelectedType} />
      <FlatList
        data={items}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => (
          <OpportunityCard
            item={item}
            onPress={() => router.push(`/oportunidade/${item.slug}`)}
          />
        )}
        onEndReached={handleEndReached}
        onEndReachedThreshold={0.4}
        refreshControl={
          <RefreshControl refreshing={isRefetching} onRefresh={refetch} tintColor="#1D4ED8" />
        }
        ListEmptyComponent={
          isLoading ? (
            <ActivityIndicator style={styles.loader} color="#1D4ED8" size="large" />
          ) : (
            <Text style={styles.empty}>Nenhuma oportunidade encontrada.</Text>
          )
        }
        ListFooterComponent={
          isFetchingNextPage ? (
            <ActivityIndicator style={styles.footer} color="#1D4ED8" />
          ) : null
        }
        contentContainerStyle={styles.list}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#F9FAFB" },
  list: { paddingBottom: 24 },
  loader: { marginTop: 60 },
  footer: { paddingVertical: 16 },
  empty: {
    textAlign: "center",
    color: "#6B7280",
    marginTop: 60,
    fontSize: 15,
  },
});
