import React, { useCallback, useEffect, useState } from 'react';
import { FlatList, Linking, Pressable, RefreshControl, Text } from 'react-native';
import { useSettings } from '../context/SettingsContext';
import { ApiError, getPayLinks } from '../api/client';
import { C, Card, Dim, ErrorText, Loading, Screen, Title } from '../components/ui';

export default function PayScreen() {
  const { settings } = useSettings();
  const [links, setLinks] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const res = await getPayLinks(settings);
      setLinks(res.links);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [settings]);

  useEffect(() => { load(); }, [load]);
  if (loading) return <Screen><Loading /></Screen>;

  const entries = Object.entries(links);

  return (
    <Screen>
      <Title>Payment links</Title>
      <ErrorText message={error} />
      <Dim>Tap a link to open it. Configure handles in forge.yaml under `pay`.</Dim>
      <FlatList
        data={entries}
        keyExtractor={([label]) => label}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}
        ListEmptyComponent={<Dim>No payment links configured yet.</Dim>}
        renderItem={({ item: [label, url] }) => (
          <Pressable onPress={() => Linking.openURL(url).catch(() => setError(`Could not open ${url}`))}>
            <Card>
              <Text style={{ color: C.text, fontWeight: '700', fontSize: 16 }}>{label}</Text>
              <Dim>{url}</Dim>
            </Card>
          </Pressable>
        )}
      />
    </Screen>
  );
}
