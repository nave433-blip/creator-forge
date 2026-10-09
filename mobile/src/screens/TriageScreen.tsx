import React, { useCallback, useEffect, useState } from 'react';
import { FlatList, RefreshControl, Text, View } from 'react-native';
import { useSettings } from '../context/SettingsContext';
import {
  ApiError,
  TriageItem,
  getTriage,
  triageDecide,
} from '../api/client';
import { Btn, C, Card, Dim, ErrorText, Loading, Screen, Title } from '../components/ui';

export default function TriageScreen() {
  const { settings } = useSettings();
  const [items, setItems] = useState<TriageItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const res = await getTriage(settings);
      setItems(res.pending);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [settings]);

  useEffect(() => { load(); }, [load]);

  const act = async (id: number, action: 'approve' | 'skip') => {
    setBusyId(id);
    setError(null);
    try {
      await triageDecide(settings, action, id);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusyId(null);
    }
  };

  if (loading) return <Screen><Loading /></Screen>;

  return (
    <Screen>
      <Title>Pic triage ({items.length})</Title>
      <ErrorText message={error} />
      <Dim>
        Fan-sent pics, pre-screened with blurred thumbnails. One tap to
        approve or skip — you never have to open what you don't want to see.
        Full blurred previews live in the web dashboard.
      </Dim>
      <FlatList
        data={items}
        keyExtractor={(i) => String(i.id)}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}
        ListEmptyComponent={<Dim>No pics waiting. Nothing to screen.</Dim>}
        renderItem={({ item }) => (
          <Card>
            <Text style={{ color: C.text, fontWeight: '600' }}>
              #{item.id} · {item.platform} · from {item.sender}
            </Text>
            <Text style={{ color: C.dim, fontSize: 12, marginTop: 4 }}>
              classifier: {item.nsfw_label} ({Math.round(item.nsfw_score * 100)}%)
              {item.note ? ` · ${item.note}` : ''}
            </Text>
            <View style={{ flexDirection: 'row', marginTop: 8 }}>
              <Btn label="Approve" onPress={() => act(item.id, 'approve')} disabled={busyId === item.id} />
              <View style={{ width: 8 }} />
              <Btn label="Skip" danger onPress={() => act(item.id, 'skip')} disabled={busyId === item.id} />
            </View>
          </Card>
        )}
      />
    </Screen>
  );
}
