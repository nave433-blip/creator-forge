import React, { useCallback, useEffect, useState } from 'react';
import { FlatList, RefreshControl, Text } from 'react-native';
import { useSettings } from '../context/SettingsContext';
import { ApiError, CatalogItem, getCatalog } from '../api/client';
import { C, Card, Dim, ErrorText, Field, Loading, Screen, Title } from '../components/ui';

export default function CatalogScreen() {
  const { settings } = useSettings();
  const [items, setItems] = useState<CatalogItem[]>([]);
  const [count, setCount] = useState(0);
  const [query, setQuery] = useState('');
  const [kind, setKind] = useState<'all' | 'image' | 'video'>('all');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const res = await getCatalog(
        settings,
        query || undefined,
        kind === 'all' ? undefined : kind,
      );
      setItems(res.items);
      setCount(res.count);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [settings, query, kind]);

  useEffect(() => {
    setLoading(true);
    load();
  }, [load]);

  if (loading) return <Screen><Loading /></Screen>;

  return (
    <Screen>
      <Title>Catalog ({count})</Title>
      <Field label="Search" value={query} onChange={setQuery} placeholder="filename, tag, note..." />
      <ErrorText message={error} />
      <FlatList
        data={items}
        keyExtractor={(i) => String(i.id)}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}
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
