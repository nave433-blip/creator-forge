import React, { useCallback, useEffect, useState } from 'react';
import { FlatList, RefreshControl, Text, View } from 'react-native';
import { useSettings } from '../context/SettingsContext';
import {
  ApiError,
  SpicyTier,
  getSpicyTemplates,
  setSpicyTier,
  spicyDraft,
} from '../api/client';
import { Btn, C, Card, Dim, ErrorText, Field, Loading, Screen, Title } from '../components/ui';

const TIER_ORDER = ['playful', 'teasing', 'explicit'];

export default function SpicyScreen() {
  const { settings } = useSettings();
  const [tiers, setTiers] = useState<SpicyTier[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [platform, setPlatform] = useState('');
  const [sender, setSender] = useState('');
  const [text, setText] = useState('');
  const [tier, setTierChoice] = useState('playful');
  const [result, setResult] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      const res = await getSpicyTemplates(settings);
      setTiers(res.tiers);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [settings]);

  useEffect(() => { load(); }, [load]);

  const doDraft = async () => {
    setError(null);
    setResult(null);
    setBusy(true);
    try {
      const res = await spicyDraft(settings, platform.trim(), sender.trim(), text.trim());
      setResult(`Draft #${res.draft_id} [${res.trigger}] → approval queue:\n${res.reply}`);
      setText('');
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const doSetTier = async () => {
    setError(null);
    setBusy(true);
    try {
      await setSpicyTier(settings, platform.trim(), sender.trim(), tier);
      setResult(`Tier for ${sender.trim()} set to ${tier}.`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const cycleTier = () => {
    const i = TIER_ORDER.indexOf(tier);
    setTierChoice(TIER_ORDER[(i + 1) % TIER_ORDER.length]);
  };

  if (loading) return <Screen><Loading /></Screen>;

  return (
    <Screen>
      <Title>Spicy mode</Title>
      <ErrorText message={error} />
      <Dim>
        Consent-gated: needs spicy scope in her identity pack. Tiers only
        change when you set them — the bot never escalates alone. Drafts
        always land in the approval queue.
      </Dim>

      <Card>
        <Text style={{ color: C.text, fontWeight: '600', marginBottom: 6 }}>Draft a spicy reply</Text>
        <Field label="Platform" value={platform} onChange={setPlatform} placeholder="onlyfans" />
        <Field label="Sender" value={sender} onChange={setSender} placeholder="fan handle" />
        <Field label="Their message" value={text} onChange={setText} placeholder="what they said…" />
        <View style={{ flexDirection: 'row', flexWrap: 'wrap' }}>
          <Btn label="Draft reply" onPress={doDraft} disabled={busy || !platform || !sender || !text} />
          <View style={{ width: 8 }} />
          <Btn label={`Tier: ${tier} (tap to change)`} onPress={cycleTier} />
          <View style={{ width: 8 }} />
          <Btn label="Apply tier" onPress={doSetTier} disabled={busy || !platform || !sender} />
        </View>
        {result ? <Text style={{ color: C.text, marginTop: 8 }}>{result}</Text> : null}
      </Card>

      <FlatList
        data={tiers}
        keyExtractor={(t) => t.tier}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}
        renderItem={({ item }) => (
          <Card>
            <Text style={{ color: C.text, fontWeight: '700' }}>{item.tier}</Text>
            {item.templates.map((tpl) => (
              <Text key={tpl.name} style={{ color: C.dim, fontSize: 12, marginTop: 4 }}>
                [{tpl.name}] {tpl.text.slice(0, 100)}
              </Text>
            ))}
          </Card>
        )}
      />
    </Screen>
  );
}
