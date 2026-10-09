import React, { useCallback, useEffect, useState } from 'react';
import { FlatList, RefreshControl, Text } from 'react-native';
import { useSettings } from '../context/SettingsContext';
import {
  ApiError,
  StreamPlatform,
  StreamStatus,
  getStreamPlatforms,
  getStreamStatus,
  streamGoLive,
  streamStop,
} from '../api/client';
import { Btn, C, Card, Dim, ErrorText, Field, Loading, Screen, Title } from '../components/ui';

export default function StreamScreen() {
  const { settings } = useSettings();
  const [platforms, setPlatforms] = useState<StreamPlatform[]>([]);
  const [status, setStatus] = useState<StreamStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [platform, setPlatform] = useState('chaturbate');
  const [avatar, setAvatar] = useState('loop');
  const [avatarSource, setAvatarSource] = useState('');
  const [riskOk, setRiskOk] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [p, s] = await Promise.all([getStreamPlatforms(settings), getStreamStatus(settings)]);
      setPlatforms(p.platforms);
      setStatus(s);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [settings]);

  useEffect(() => { load(); }, [load]);

  const goLive = async () => {
    setError(null); setOk(null);
    if (!riskOk) { setError('Confirm you read the ToS risk note first.'); return; }
    try {
      await streamGoLive(settings, {
        platform: platform.trim(), avatar, avatar_source: avatarSource.trim(), i_understand_the_risk: true,
      });
      setOk('Session started. Follow the OBS checklist on the backend — CreatorForge does not stream to the platform itself.');
      load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  };

  if (loading) return <Screen><Loading /></Screen>;

  return (
    <Screen>
      <Title>AFK Streaming</Title>
      <Dim>Her AI avatar plays through OBS → RTMP while she's away. Most cam sites expect a live verified performer — AFK avatar streaming can get the account banned. Read each platform's risk note.</Dim>
      <ErrorText message={error} />
      {ok ? <Text style={{ color: C.accent }}>{ok}</Text> : null}
      <Card>
        <Text style={{ color: C.text, fontWeight: '700' }}>
          Status: {status?.active ? `LIVE on ${status.platform_label}` : 'not streaming'}
        </Text>
        {status?.active && status.checklist ? status.checklist.map((c) => <Dim key={c}>• {c}</Dim>) : null}
        {status?.active ? <Btn label="Stop stream" onPress={() => streamStop(settings).then(load).catch((e) => setError(e instanceof ApiError ? e.message : String(e)))} /> : null}
      </Card>
      {!status?.active ? (
        <Card>
          <Field label="Platform key" value={platform} onChange={setPlatform} placeholder="chaturbate" />
          <Field label="Avatar mode (loop | sadtalker | heygen | did)" value={avatar} onChange={setAvatar} />
          <Field label="Avatar source file (loop mode)" value={avatarSource} onChange={setAvatarSource} placeholder="/path/persona-loop.mp4" />
          <Btn label={riskOk ? '✓ I understand the ToS risk' : 'I understand the ToS risk'} onPress={() => setRiskOk(!riskOk)} />
          <Btn label="Go live" onPress={goLive} />
        </Card>
      ) : null}
      <FlatList
        data={platforms}
        keyExtractor={(p) => p.key}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}
        renderItem={({ item }) => (
          <Card>
            <Text style={{ color: C.text, fontWeight: '700' }}>{item.label}</Text>
            <Dim>RTMP: {item.rtmp_ingest ? 'yes' : 'no'} · Chat API: {item.chat_api}</Dim>
            <Dim>Risk: {item.tos_risk}</Dim>
            <Dim>{item.payout_notes}</Dim>
          </Card>
        )}
      />
    </Screen>
  );
}
