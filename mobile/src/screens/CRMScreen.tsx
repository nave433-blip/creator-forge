import React, { useCallback, useEffect, useState } from 'react';
import { FlatList, RefreshControl, Text } from 'react-native';
import { useSettings } from '../context/SettingsContext';
import {
  ApiError,
  BuyerIntent,
  Fan,
  crmFanAction,
  getFan,
  getFans,
  getSmartList,
} from '../api/client';
import { Btn, C, Card, Dim, ErrorText, Field, Loading, Screen, Title } from '../components/ui';

const LISTS = ['whales', 'new', 'active', 'expired', 'quiet', 'online'];

export default function CRMScreen() {
  const { settings } = useSettings();
  const [fans, setFans] = useState<Fan[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [list, setList] = useState('whales');
  const [handle, setHandle] = useState('');
  const [platform, setPlatform] = useState('onlyfans');
  const [detail, setDetail] = useState<(Fan & { buyer_intent: BuyerIntent }) | null>(null);
  const [amount, setAmount] = useState('');
  const [note, setNote] = useState('');
  const [tag, setTag] = useState('');

  const load = useCallback(async () => {
    setError(null);
    try {
      const res = await getSmartList(settings, list, platform.trim() || undefined);
      setFans(res.fans);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [settings, list, platform]);

  useEffect(() => { load(); }, [load]);

  const openFan = async (f: Fan) => {
    setError(null);
    try {
      setDetail(await getFan(settings, f.platform, f.handle));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  };

  const act = async (action: string, extra: Record<string, string | number> = {}) => {
    if (!detail) return;
    setError(null);
    try {
      const res = await crmFanAction(settings, {
        action, platform: detail.platform, handle: detail.handle, ...extra,
      });
      setDetail({ ...(await getFan(settings, detail.platform, detail.handle)) });
      setAmount(''); setNote(''); setTag('');
      void res;
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  };

  if (loading) return <Screen><Loading /></Screen>;

  return (
    <Screen>
      <Title>Fan CRM</Title>
      <Dim>Tags, notes, spend tracking, buyer-intent scores. Records come from what you enter or import — the app can't see inside the platforms.</Dim>
      <ErrorText message={error} />
      <Field label="Platform" value={platform} onChange={setPlatform} placeholder="onlyfans" />
      <Text style={{ color: C.dim, marginBottom: 4 }}>Smart list</Text>
      <FlatList
        horizontal
        data={LISTS}
        keyExtractor={(k) => k}
        renderItem={({ item }) => (
          <Btn
            label={item}
            onPress={() => { setList(item); setLoading(true); }}
          />
        )}
      />
      <FlatList
        data={fans}
        keyExtractor={(f) => `${f.platform}:${f.handle}`}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}
        renderItem={({ item }) => (
          <Card>
            <Text style={{ color: C.text, fontWeight: '700' }} onPress={() => openFan(item)}>
              {item.handle} <Text style={{ color: C.dim }}>({item.platform})</Text>
            </Text>
            <Dim>${item.total_spend.toFixed(0)} lifetime · {item.message_count} msgs · [{item.status}]</Dim>
            {item.tags.length ? <Dim>tags: {item.tags.join(', ')}</Dim> : null}
          </Card>
        )}
        ListEmptyComponent={<Dim>No fans in this list yet. Add them with the buttons below or import a CSV.</Dim>}
      />
      {detail ? (
        <Card>
          <Text style={{ color: C.text, fontWeight: '700', fontSize: 16 }}>
            {detail.handle} — intent {detail.buyer_intent.score}/100
          </Text>
          <Dim>{detail.buyer_intent.method}</Dim>
          {detail.buyer_intent.reasons.map((r) => <Dim key={r}>+ {r}</Dim>)}
          {detail.notes ? <Text style={{ color: C.text, marginTop: 6 }}>{detail.notes}</Text> : null}
          <Field label="Record purchase ($)" value={amount} onChange={setAmount} placeholder="25" />
          <Btn label="Log purchase" onPress={() => act('spend', { amount: Number(amount) || 0 })} />
          <Field label="Add tag" value={tag} onChange={setTag} placeholder="whale" />
          <Btn label="Add tag" onPress={() => act('tag', { tag: tag.trim() })} />
          <Field label="Add note" value={note} onChange={setNote} placeholder="likes customs" />
          <Btn label="Save note" onPress={() => act('note', { note: note.trim() })} />
          <Btn label="Close" onPress={() => setDetail(null)} />
        </Card>
      ) : null}
      <Card>
        <Text style={{ color: C.text, fontWeight: '700' }}>Quick add fan</Text>
        <Field label="Handle" value={handle} onChange={setHandle} placeholder="fan_handle" />
        <Btn label="Add fan" onPress={() => {
          if (!handle.trim()) { setError('Enter a handle.'); return; }
          crmFanAction(settings, { action: 'upsert', platform: platform.trim(), handle: handle.trim() })
            .then(() => { setHandle(''); load(); })
            .catch((e) => setError(e instanceof ApiError ? e.message : String(e)));
        }} />
      </Card>
    </Screen>
  );
}
