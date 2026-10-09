import React, { useCallback, useEffect, useState } from 'react';
import { FlatList, RefreshControl, Text, View } from 'react-native';
import { useSettings } from '../context/SettingsContext';
import {
  ApiError,
  TubeMetadata,
  TubeSiteInfo,
  buildTubePacket,
  getTubeSites,
  previewTubeMetadata,
} from '../api/client';
import { Btn, C, Card, Dim, ErrorText, Field, Loading, Screen, Title } from '../components/ui';

const SITES_FALLBACK = ['pornhub', 'xvideos', 'xnxx', 'xhamster', 'redtube', 'youporn'];

export default function TubeScreen() {
  const { settings } = useSettings();
  const [sites, setSites] = useState<TubeSiteInfo[]>([]);
  const [site, setSite] = useState('pornhub');
  const [video, setVideo] = useState('');
  const [name, setName] = useState('');
  const [tags, setTags] = useState('');
  const [meta, setMeta] = useState<TubeMetadata | null>(null);
  const [packet, setPacket] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const res = await getTubeSites(settings);
      setSites(res.sites);
      if (res.sites.length > 0) setSite(res.sites[0].key);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [settings]);

  useEffect(() => { load(); }, [load]);

  const tagList = tags.split(',').map((t) => t.trim()).filter(Boolean);

  const preview = async () => {
    setBusy(true);
    setError(null);
    setPacket(null);
    try {
      const res = await previewTubeMetadata(settings, site, { name: name.trim(), tags: tagList });
      setMeta(res);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const build = async () => {
    if (!video.trim()) {
      setError('Enter the video file path on the computer running the backend.');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await buildTubePacket(settings, video.trim(), site, { name: name.trim(), tags: tagList });
      setPacket(res.packet);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  if (loading) return <Screen><Loading /></Screen>;

  return (
    <Screen>
      <Title>Tube uploads</Title>
      <ErrorText message={error} />
      <Dim>None of these sites offer an upload API — the app builds a ready-to-paste packet (title, description, tags, checklist). You publish on each site yourself.</Dim>
      <Field label="Site" value={site} onChange={setSite} placeholder={SITES_FALLBACK.join(', ')} />
      <Field label="Her display name" value={name} onChange={setName} placeholder="Bella" />
      <Field label="Custom tags (comma-separated)" value={tags} onChange={setTags} placeholder="solo, tease" />
      <View style={{ flexDirection: 'row', marginVertical: 8 }}>
        <Btn label={busy ? 'Working…' : 'Preview'} onPress={preview} disabled={busy} />
        <View style={{ width: 8 }} />
        <Btn label={busy ? 'Working…' : 'Build packet'} onPress={build} disabled={busy} />
      </View>
      <Field label="Video file path (on the backend computer)" value={video} onChange={setVideo} placeholder="/path/to/clip.mp4" />
      {meta && (
        <Card>
          <Text style={{ color: C.text, fontWeight: '600' }}>Title</Text>
          <Text style={{ color: C.text, marginTop: 4 }}>{meta.title}</Text>
          <Text style={{ color: C.text, fontWeight: '600', marginTop: 8 }}>
            Tags ({meta.tags.length}){meta.tags_truncated ? ' — some dropped (site limit)' : ''}
          </Text>
          <Text style={{ color: C.dim, marginTop: 4 }}>{meta.tags.join(', ')}</Text>
          <Text style={{ color: C.text, fontWeight: '600', marginTop: 8 }}>Description</Text>
          <Text style={{ color: C.dim, marginTop: 4 }}>{meta.description}</Text>
        </Card>
      )}
      {packet && (
        <Card>
          <Text style={{ color: C.good, fontWeight: '600' }}>Packet ready</Text>
          <Text style={{ color: C.dim, marginTop: 4 }}>{packet}</Text>
          <Dim>Copy title/description/tags into the site's upload page, then publish there.</Dim>
        </Card>
      )}
      <FlatList
        data={sites}
        keyExtractor={(s) => s.key}
        refreshControl={<RefreshControl refreshing={false} onRefresh={load} />}
        renderItem={({ item }) => (
          <Card>
            <Text style={{ color: C.text, fontWeight: '600' }}>{item.site}</Text>
            <Text style={{ color: C.dim, marginTop: 4 }}>Upload: {item.upload} · Verification: {item.verification}</Text>
            {!!item.monetization && <Text style={{ color: C.dim, marginTop: 2 }}>{item.monetization}</Text>}
          </Card>
        )}
      />
    </Screen>
  );
}
