import React, { useCallback, useEffect, useState } from 'react';
import { FlatList, RefreshControl, Text } from 'react-native';
import { useSettings } from '../context/SettingsContext';
import { ApiError, CatalogItem, getCatalog } from '../api/client';
import { Btn, C, Card, Dim, ErrorText, Field, Loading, Screen, Title } from '../components/ui';

const PAGE = 50;

export default function CatalogScreen() {
  const { settings } = useSettings();
  const [items, setItems] = useState<CatalogItem[]>([]);
  const [count, setCount] = useState(0);
  const [total, setTotal] = useState(0);
  const [query, setQuery] = useState('');
  const [kind, setKind] = useState<'all' | 'image' | 'video'>('all');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (append = false) => {
    setError(null);
    if (append) setLoadingMore(true);
    try {
      const res = await getCatalog(
        settings,
        query || undefined,
        kind === 'all' ? undefined : kind,
        append ? items.length : 0,
        PAGE,
      );
      setItems((prev) => (append ? [...prev, ...res.items] : res.items));
      setCount(res.count);
      setTotal(res.total ?? res.items.length);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setLoading(false);
      setRefreshing(false);
      setLoadingMore(false);
    }
  }, [settings, query, kind, items.length]);

  useEffect(() => {
    setLoading(true);
    setItems([]);
    load(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, kind, settings]);

  const hasMore = items.length < total;

  if (loading) return <Screen><Loading /></Screen>;

  return (
    <Screen>
      <Title>Catalog ({count})</Title>
      <Field label="Search" value={query} onChange={setQuery} placeholder="filename, tag, note..." />
      <ErrorText message={error} />
      <Dim>Showing {items.length} of {total}.</Dim>
      <FlatList
        data={items}
        keyExtractor={(i) => String(i.id)}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(false); }} />}
        ListEmptyComponent={<Dim>No items match. Scan a folder with `forge catalog scan`.</Dim>}
        ListFooterComponent={
          hasMore ? (
            <Btn label={loadingMore ? 'Loading…' : `Load more (${total - items.length} left)`} onPress={() => load(true)} disabled={loadingMore} />
          ) : null
        }
        renderItem={({ item }) => (
          <Card>
            <Text style={{ color: C.text, fontWeight: '600' }}>
              [{item.kind}] {item.path.split('/').pop()}
            </Text>
            <Dim>
              {item.width && item.height ? `${item.width}x${item.height}  ` : ''}
              {item.duration ? `${Math.round(item.duration)}s  ` : ''}
              {item.tags.length ? `tags: ${item.tags.join(', ')}` : 'no tags'}
            </Dim>
          </Card>
        )}
      />
    </Screen>
  );
}
