import React, { useCallback, useEffect, useState } from 'react';
import { FlatList, RefreshControl, Text, View } from 'react-native';
import { useSettings } from '../context/SettingsContext';
import {
  ApiError,
  ChatDraft,
  approveDraft,
  getChatQueue,
  markDraftSent,
  rejectDraft,
} from '../api/client';
import { Btn, C, Card, Dim, ErrorText, Loading, Screen, Title } from '../components/ui';

export default function ChatQueueScreen() {
  const { settings } = useSettings();
  const [pending, setPending] = useState<ChatDraft[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const res = await getChatQueue(settings);
      setPending(res.pending);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [settings]);

  useEffect(() => { load(); }, [load]);

  const act = async (id: number, fn: (s: typeof settings, i: number) => Promise<unknown>) => {
    setBusyId(id);
    setError(null);
    try {
      await fn(settings, id);
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
      <Title>Approval queue ({pending.length})</Title>
      <ErrorText message={error} />
      <Dim>
        Nothing sends itself. Approve a draft, send the reply yourself in
        the platform's app, then tap "Mark sent".
      </Dim>
      <FlatList
        data={pending}
        keyExtractor={(d) => String(d.id)}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}
        ListEmptyComponent={<Dim>No pending drafts. You're all caught up.</Dim>}
        renderItem={({ item }) => (
          <Card>
            <Text style={{ color: C.dim, fontSize: 12 }}>
              #{item.id} · {item.platform} · from {item.sender} · trigger: {item.trigger}
            </Text>
            {item.escalated && (
              <Text style={{ color: C.warn, fontWeight: '700', marginTop: 4 }}>
                ⚠ Needs your eyes: {item.escalation_categories.join(', ')}
              </Text>
            )}
            <Text style={{ color: C.text, marginTop: 6 }}>In: {item.incoming}</Text>
            <Text style={{ color: C.text, marginTop: 6, fontWeight: '600' }}>
              Draft: {item.reply}
            </Text>
            <View style={{ flexDirection: 'row', gap: 8, marginTop: 8 }}>
              <View style={{ flex: 1 }}>
                <Btn label="Approve" onPress={() => act(item.id, approveDraft)} disabled={busyId === item.id} />
              </View>
              <View style={{ flex: 1 }}>
                <Btn label="Reject" danger onPress={() => act(item.id, rejectDraft)} disabled={busyId === item.id} />
              </View>
            </View>
            <Btn label="Mark sent (after you send it)" onPress={() => act(item.id, markDraftSent)} disabled={busyId === item.id} />
          </Card>
        )}
      />
    </Screen>
  );
}
