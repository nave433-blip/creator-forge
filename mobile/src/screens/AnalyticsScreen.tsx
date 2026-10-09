import React, { useCallback, useEffect, useState } from 'react';
import { RefreshControl, ScrollView, Text } from 'react-native';
import { useSettings } from '../context/SettingsContext';
import {
  AnalyticsTotals,
  ApiError,
  PlatformMonth,
  getAnalytics,
} from '../api/client';
import { C, Card, Dim, ErrorText, Loading, Screen, Title } from '../components/ui';

function money(n: number): string {
  return `$${(n || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export default function AnalyticsScreen() {
  const { settings } = useSettings();
  const [totals, setTotals] = useState<AnalyticsTotals | null>(null);
  const [rows, setRows] = useState<PlatformMonth[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const res = await getAnalytics(settings);
      setTotals(res.totals);
      setRows(res.by_platform_month);
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
      <ScrollView refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}>
        <Title>Analytics</Title>
        <ErrorText message={error} />
        {totals && (
          <Card>
            <Text style={{ color: C.text, fontSize: 20, fontWeight: '700' }}>
              {money(totals.total_earnings)}
            </Text>
            <Text style={{ color: C.dim, fontSize: 12, marginTop: 4 }}>
              total earnings logged
            </Text>
            <Text style={{ color: C.text, marginTop: 10 }}>
              {totals.posts_tracked} posts · {totals.total_views.toLocaleString()} views ·{' '}
              {totals.total_likes.toLocaleString()} likes · {totals.total_comments.toLocaleString()} comments
            </Text>
          </Card>
        )}
        <Title>By platform & month</Title>
        {rows.length === 0 && (
          <Dim>No earnings logged yet. Log them from your computer with "forge analytics log-earning".</Dim>
        )}
        {rows.map((r, i) => (
          <Card key={`${r.platform}-${r.month}-${i}`}>
            <Text style={{ color: C.text, fontWeight: '600' }}>
              {r.month} · {r.platform}
            </Text>
            <Text style={{ color: C.dim, marginTop: 4 }}>
              {money(r.total)} {r.currency} ({r.entries} entries)
            </Text>
          </Card>
        ))}
        <Dim>
          OnlyFans / Fansly / Snapchat have no stats API — those numbers only
          update when you log them. Reddit stats come live from Reddit.
        </Dim>
      </ScrollView>
    </Screen>
  );
}
