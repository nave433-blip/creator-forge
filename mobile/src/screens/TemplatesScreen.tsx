import React, { useCallback, useEffect, useState } from 'react';
import { FlatList, RefreshControl, Text } from 'react-native';
import { useSettings } from '../context/SettingsContext';
import {
  ApiError,
  ChatTemplate,
  getTemplates,
  useTemplate,
} from '../api/client';
import { Btn, C, Card, Dim, ErrorText, Field, Loading, Screen, Title } from '../components/ui';

export default function TemplatesScreen() {
  const { settings } = useSettings();
  const [templates, setTemplates] = useState<ChatTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [platform, setPlatform] = useState('onlyfans');
  const [sender, setSender] = useState('');
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const res = await getTemplates(settings);
      setTemplates(res.templates);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [settings]);

  useEffect(() => { load(); }, [load]);

  const draft = async (name: string) => {
    if (!sender.trim()) {
      setError('Enter who the message is for first.');
      return;
    }
    setBusy(name);
    setError(null);
    setOk(null);
    try {
      const res = await useTemplate(settings, name, platform.trim(), sender.trim());
      setOk(`Draft #${res.draft_id} queued from "${name}". Approve it in the Chat tab.`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  };

  if (loading) return <Screen><Loading /></Screen>;

  return (
    <Screen>
      <Title>Canned templates</Title>
      <ErrorText message={error} />
      {ok && <Text style={{ color: C.good, marginBottom: 8 }}>{ok}</Text>}
      <Field label="Platform" value={platform} onChange={setPlatform} placeholder="onlyfans" />
      <Field label="Sending to (their name/handle)" value={sender} onChange={setSender} placeholder="e.g. mike92" />
      <Dim>Tap a template to draft it into the approval queue — nothing sends itself.</Dim>
      <FlatList
        data={templates}
        keyExtractor={(t) => t.name}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}
        ListEmptyComponent={<Dim>No templates yet.</Dim>}
        renderItem={({ item }) => (
          <Card>
            <Text style={{ color: C.text, fontWeight: '600' }}>
              {item.name} <Text style={{ color: C.dim, fontWeight: '400' }}>· {item.category}</Text>
            </Text>
            <Text style={{ color: C.dim, marginTop: 4 }}>{item.text}</Text>
            <Btn
              label={busy === item.name ? 'Drafting…' : 'Draft this reply'}
              onPress={() => draft(item.name)}
              disabled={busy !== null}
            />
          </Card>
        )}
      />
    </Screen>
  );
}
