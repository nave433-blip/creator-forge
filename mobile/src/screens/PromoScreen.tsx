import React, { useCallback, useEffect, useState } from 'react';
import { FlatList, RefreshControl, Text } from 'react-native';
import { useSettings } from '../context/SettingsContext';
import { ApiError, PromoCampaign, PromoLink, getPromoClicks, getPromoLinks, getPromoReport } from '../api/client';
import { C, Card, Dim, ErrorText, Loading, Screen, Title } from '../components/ui';

export default function PromoScreen() {
  const { settings } = useSettings();
  const [campaigns, setCampaigns] = useState<PromoCampaign[]>([]);
  const [links, setLinks] = useState<PromoLink[]>([]);
  const [clicks, setClicks] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [rep, ls] = await Promise.all([
        getPromoReport(settings),
        getPromoLinks(settings),
      ]);
      setCampaigns(rep.campaigns);
      setLinks(ls.links);
      const counts: Record<string, number> = {};
      await Promise.all(
        ls.links.map(async (l) => {
          try {
            const c = await getPromoClicks(settings, l.code);
            counts[l.code] = c.clicks;
          } catch {
            /* clicks endpoint optional on older backends */
          }
        }),
      );
      setClicks(counts);
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
      <Title>Promo links</Title>
      <ErrorText message={error} />
      <Dim>Which shoutouts paid off. Create links with `forge promo link-create`.</Dim>
      <Text style={{ color: C.text, fontWeight: '700', fontSize: 16, marginTop: 12, marginBottom: 4 }}>
        Campaigns
      </Text>
      <FlatList
        data={campaigns}
        keyExtractor={(c) => c.campaign}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}
        ListEmptyComponent={<Dim>No campaigns yet.</Dim>}
        renderItem={({ item }) => (
          <Card>
            <Text style={{ color: C.text, fontWeight: '700', fontSize: 16 }}>{item.campaign}</Text>
            <Dim>{item.links} link(s) · {item.clicks ?? 0} click(s) · ${item.earnings.toFixed(2)} attributed</Dim>
          </Card>
        )}
      />
      <Text style={{ color: C.text, fontWeight: '700', fontSize: 16, marginTop: 12, marginBottom: 4 }}>
        Links
      </Text>
      <FlatList
        data={links}
        keyExtractor={(l) => l.code}
        ListEmptyComponent={<Dim>No promo links yet.</Dim>}
        renderItem={({ item }) => (
          <Card>
            <Text style={{ color: C.text, fontWeight: '700', fontSize: 16 }}>[{item.code}] {item.campaign}</Text>
            <Dim>
              {clicks[item.code] !== undefined ? `${clicks[item.code]} click(s) · ` : ''}short: /promo/go/{item.code}
            </Dim>
            <Dim>{item.full_url}</Dim>
          </Card>
        )}
      />
    </Screen>
  );
}
