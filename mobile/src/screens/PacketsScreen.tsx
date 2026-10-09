import React, { useCallback, useEffect, useState } from 'react';
import { FlatList, RefreshControl, Text } from 'react-native';
import { useSettings } from '../context/SettingsContext';
import { ApiError, PostingPacket, getPackets } from '../api/client';
import { C, Card, Dim, ErrorText, Loading, Screen, Title } from '../components/ui';

export default function PacketsScreen() {
  const { settings } = useSettings();
  const [packets, setPackets] = useState<PostingPacket[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const res = await getPackets(settings);
      setPackets(res.packets);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [settings]);

  useEffect(() => { load(); }, [load]);
  if (loading) return <Screen><Loading /></Screen>;

  return (
    <Screen>
      <Title>Posting packets ({packets.length})</Title>
      <ErrorText message={error} />
      <Dim>
        Manual-assist packets for platforms with no posting API (Snapchat,
        OnlyFans...). Open the packet's checklist and post in the app.
      </Dim>
      <FlatList
        data={packets}
        keyExtractor={(p) => p.dir}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}
        ListEmptyComponent={<Dim>No packets yet. Create one with `forge post packet`.</Dim>}
        renderItem={({ item }) => (
          <Card>
            <Text style={{ color: C.text, fontWeight: '700' }}>
              {item.platform} · {item.title || item.dir}
            </Text>
            <Dim>
              status: {item.status}
              {item.scheduled_for ? ` · scheduled: ${item.scheduled_for}` : ''}
              {item.created ? ` · created: ${item.created}` : ''}
            </Dim>
          </Card>
        )}
      />
    </Screen>
  );
}
