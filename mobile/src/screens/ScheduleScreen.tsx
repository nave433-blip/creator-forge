import React, { useCallback, useEffect, useState } from 'react';
import { FlatList, RefreshControl, Text, View } from 'react-native';
import { useSettings } from '../context/SettingsContext';
import {
  ApiError,
  ScheduledPost,
  getSchedule,
  markScheduled,
} from '../api/client';
import { Btn, C, Card, Dim, ErrorText, Loading, Screen, Title } from '../components/ui';

export default function ScheduleScreen() {
  const { settings } = useSettings();
  const [items, setItems] = useState<ScheduledPost[]>([]);
  const [dueCount, setDueCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const res = await getSchedule(settings);
      setItems(res.scheduled);
      setDueCount(res.due_count);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [settings]);

  useEffect(() => { load(); }, [load]);

  const mark = async (id: number, status: string) => {
    setBusyId(id);
    setError(null);
    try {
      await markScheduled(settings, id, status);
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
      <Title>Schedule{dueCount > 0 ? ` (${dueCount} due!)` : ''}</Title>
      <ErrorText message={error} />
      <Dim>
        Reminders, not auto-posting. When something is due, post it yourself
        in the app, then tap "Mark done".
      </Dim>
      <FlatList
        data={items}
        keyExtractor={(p) => String(p.id)}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}
        ListEmptyComponent={<Dim>Nothing scheduled. Use "forge post schedule" on your computer.</Dim>}
        renderItem={({ item }) => (
          <Card>
            <Text style={{ color: item.is_due ? C.warn : C.text, fontWeight: '700' }}>
              {item.is_due ? 'DUE NOW — ' : ''}#{item.id} [{item.platform}] {item.title || '(no title)'}
            </Text>
            <Text style={{ color: C.dim, fontSize: 12, marginTop: 4 }}>
              {item.scheduled_for} · {item.status}
            </Text>
            {item.status === 'scheduled' && (
              <View style={{ flexDirection: 'row', gap: 8, marginTop: 8 }}>
                <View style={{ flex: 1 }}>
                  <Btn label="Mark done" onPress={() => mark(item.id, 'done')} disabled={busyId === item.id} />
                </View>
                <View style={{ flex: 1 }}>
                  <Btn label="Skip" danger onPress={() => mark(item.id, 'skipped')} disabled={busyId === item.id} />
                </View>
              </View>
            )}
          </Card>
        )}
      />
    </Screen>
  );
}
