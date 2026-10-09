import React, { useCallback, useEffect, useState } from 'react';
import { FlatList, RefreshControl, Text } from 'react-native';
import { useSettings } from '../context/SettingsContext';
import {
  ApiError,
  ContentIdea,
  LtvReport,
  PeakSlot,
  getIdeas,
  getLtv,
  getPeakTimes,
} from '../api/client';
import { Btn, C, Card, Dim, ErrorText, Loading, Screen, Title } from '../components/ui';

export default function IdeasScreen() {
  const { settings } = useSettings();
  const [ideas, setIdeas] = useState<ContentIdea[]>([]);
  const [ltv, setLtv] = useState<LtvReport | null>(null);
  const [summary, setSummary] = useState('');
  const [peaks, setPeaks] = useState<PeakSlot[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (seed = 'forge') => {
    setError(null);
    try {
      const [i, l, p] = await Promise.all([
        getIdeas(settings, 10),
        getLtv(settings),
        getPeakTimes(settings),
      ]);
      setIdeas(i.ideas);
      setLtv(l.ltv);
      setSummary(l.summary);
      setPeaks(p.peak_times);
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
      <Title>Ideas & insights</Title>
      <Dim>Post ideas are template remixes of her own tags — not generative AI. Stats reflect only what she logged.</Dim>
      <ErrorText message={error} />
      {ltv ? (
        <Card>
          <Text style={{ color: C.text, fontWeight: '700' }}>
            ARPU ${ltv.arpu.toFixed(2)} · avg LTV ${ltv.avg_ltv.toFixed(2)} · {ltv.fan_count} fans
          </Text>
          <Dim>{summary}</Dim>
        </Card>
      ) : null}
      {peaks.length ? (
        <Card>
          <Text style={{ color: C.text, fontWeight: '700' }}>Best posting slots</Text>
          {peaks.slice(0, 3).map((p) => (
            <Dim key={`${p.weekday}-${p.hour}`}>{p.weekday} {String(p.hour).padStart(2, '0')}:00 — avg engagement {p.avg_engagement}</Dim>
          ))}
        </Card>
      ) : null}
      <Btn label="Fresh batch of ideas" onPress={() => { setRefreshing(true); load(String(Date.now())); }} />
      <FlatList
        data={ideas}
        keyExtractor={(_, i) => String(i)}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}
        renderItem={({ item, index }) => (
          <Card>
            <Text style={{ color: C.text, fontWeight: '700' }}>{index + 1}. [{item.angle}]</Text>
            <Text style={{ color: C.text }}>{item.caption}</Text>
            <Dim>{item.hashtags}</Dim>
          </Card>
        )}
      />
    </Screen>
  );
}
