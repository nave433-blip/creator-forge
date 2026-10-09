import React, { useCallback, useEffect, useState } from 'react';
import { RefreshControl, ScrollView, Text, View } from 'react-native';
import { useSettings } from '../context/SettingsContext';
import {
  ApiError,
  LiveStatus,
  getLiveStatus,
  liveStart,
  liveStop,
} from '../api/client';
import { Btn, C, Card, Dim, ErrorText, Loading, Screen, Title } from '../components/ui';

const PROVIDERS = ['heygen', 'did', 'local-guide'];

export default function LiveScreen() {
  const { settings } = useSettings();
  const [status, setStatus] = useState<LiveStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [provider, setProvider] = useState('heygen');
  const [guide, setGuide] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      setStatus(await getLiveStatus(settings));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [settings]);

  useEffect(() => { load(); }, [load]);

  const start = async () => {
    setBusy(true);
    setError(null);
    setGuide(null);
    try {
      const res = await liveStart(settings, provider);
      if (res.guide) setGuide(res.guide);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const stop = async () => {
    setBusy(true);
    setError(null);
    try {
      await liveStop(settings);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  if (loading) return <Screen><Loading /></Screen>;

  return (
    <Screen>
      <ScrollView refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}>
        <Title>Live avatar</Title>
        <ErrorText message={error} />
        <Card>
          <Text style={{ color: C.text, fontWeight: '600' }}>
            {status && status.active ? `● LIVE via ${status.provider}` : '○ No active session'}
          </Text>
          {status && status.active && status.started_at ? (
            <Text style={{ color: C.dim, fontSize: 12 }}>started {status.started_at}</Text>
          ) : null}
          <Dim>Real provider sessions only (HeyGen / D-ID need your API keys). Local-guide shows the honest OBS setup.</Dim>
          <View style={{ flexDirection: 'row', marginTop: 8, flexWrap: 'wrap' }}>
            {PROVIDERS.map((p) => (
              <View key={p} style={{ marginRight: 8, marginBottom: 8 }}>
                <Btn label={`${provider === p ? '✓ ' : ''}${p}`} onPress={() => setProvider(p)} />
              </View>
            ))}
          </View>
          <View style={{ flexDirection: 'row', marginTop: 4 }}>
            <Btn label="Start" onPress={start} disabled={busy} />
            <View style={{ width: 8 }} />
            <Btn label="Stop" danger onPress={stop} disabled={busy} />
          </View>
        </Card>
        {guide ? (
          <Card>
            <Text style={{ color: C.text, fontSize: 12 }}>{guide}</Text>
          </Card>
        ) : null}
      </ScrollView>
    </Screen>
  );
}
