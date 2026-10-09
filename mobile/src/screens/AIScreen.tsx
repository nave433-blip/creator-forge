import React, { useCallback, useEffect, useState } from 'react';
import { RefreshControl, ScrollView, Text, View } from 'react-native';
import { useSettings } from '../context/SettingsContext';
import { AIProviderStatus, ApiError, aiAsk, getAIProviders } from '../api/client';
import { Btn, C, Card, Dim, ErrorText, Field, Loading, Screen, Title } from '../components/ui';

const TASKS: { key: string; label: string; inputLabel: string }[] = [
  { key: 'ask', label: 'Ask anything', inputLabel: 'Prompt' },
  { key: 'caption', label: 'Captions', inputLabel: 'Topic' },
  { key: 'titles', label: 'Video titles', inputLabel: 'Topic' },
  { key: 'hashtags', label: 'Hashtags', inputLabel: 'Topic' },
  { key: 'ideas', label: 'Content ideas', inputLabel: 'Your niche' },
  { key: 'scene-ideas', label: 'Scene ideas', inputLabel: 'Vibe' },
  { key: 'polish', label: 'Polish my draft', inputLabel: 'Your text' },
  { key: 'promo', label: 'Promo lines', inputLabel: 'Item + price (e.g. custom video $50)' },
];

export default function AIScreen() {
  const { settings } = useSettings();
  const [providers, setProviders] = useState<AIProviderStatus[]>([]);
  const [provider, setProvider] = useState('');
  const [task, setTask] = useState('caption');
  const [input, setInput] = useState('');
  const [answer, setAnswer] = useState('');
  const [answerMeta, setAnswerMeta] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const res = await getAIProviders(settings);
      setProviders(res.providers);
      const firstReady = res.providers.find((p) => p.configured);
      if (firstReady && !provider) setProvider(firstReady.provider);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [settings]);

  useEffect(() => { load(); }, [load]);

  const run = async () => {
    if (!input.trim()) {
      setError('Type something first.');
      return;
    }
    setBusy(true);
    setError(null);
    setAnswer('');
    try {
      const body: Record<string, unknown> = { task, provider: provider || undefined };
      if (task === 'ask') body.prompt = input.trim();
      else if (task === 'ideas') body.niche = input.trim();
      else if (task === 'scene-ideas') body.vibe = input.trim();
      else if (task === 'polish') body.text = input.trim();
      else if (task === 'promo') {
        const m = input.trim().match(/^(.*?)\s+(\$\s?\d[\d,]*)$/);
        body.item = m ? m[1] : input.trim();
        body.price = m ? m[2] : '';
      } else body.topic = input.trim();
      const res = await aiAsk(settings, body);
      setAnswer(res.text);
      setAnswerMeta(`${res.provider} / ${res.model} — draft, not sent anywhere`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  if (loading) return <Screen><Loading /></Screen>;
  const active = TASKS.find((t) => t.key === task)!;

  return (
    <Screen>
      <Title>AI helpers</Title>
      <Dim>Grok, Gemini, Claude — your keys, drafts only. Nothing posts itself.</Dim>
      <ErrorText message={error} />
      <Card>
        <Text style={{ color: C.text, fontWeight: '600', marginBottom: 6 }}>Providers</Text>
        {providers.map((p) => (
          <Text key={p.provider} style={{ color: p.configured ? C.good : C.dim, marginBottom: 2 }}>
            {p.configured ? '●' : '○'} {p.provider} ({p.model})
          </Text>
        ))}
        {!providers.some((p) => p.configured) && (
          <Dim>Add a key in forge.yaml (ai:) or via XAI_API_KEY / GEMINI_API_KEY / ANTHROPIC_API_KEY.</Dim>
        )}
      </Card>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginVertical: 8 }}>
        <View style={{ flexDirection: 'row' }}>
          {providers.filter((p) => p.configured).map((p) => (
            <Btn key={p.provider} label={(provider === p.provider ? "● " : "") + p.provider} onPress={() => setProvider(p.provider)}
              disabled={busy} />
          ))}
        </View>
      </ScrollView>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 8 }}>
        <View style={{ flexDirection: 'row' }}>
          {TASKS.map((t) => (
            <Btn key={t.key} label={t.label} onPress={() => setTask(t.key)}
              disabled={busy} />
          ))}
        </View>
      </ScrollView>
      <Field label={active.inputLabel} value={input} onChange={setInput}
        placeholder="Type here…" />
      <Btn label={busy ? 'Thinking…' : 'Run'} onPress={run} disabled={busy} />
      {answer !== '' && (
        <Card>
          <Dim>{answerMeta}</Dim>
          <Text style={{ color: C.text, marginTop: 6 }}>{answer}</Text>
        </Card>
      )}
      <View style={{ height: 40 }} />
    </Screen>
  );
}
