import React, { useCallback, useEffect, useState } from 'react';
import { RefreshControl, ScrollView, Text, View } from 'react-native';
import { useSettings } from '../context/SettingsContext';
import {
  ApiError,
  LexiconEntry,
  addLexiconTerm,
  getLexicon,
  removeLexiconTerm,
} from '../api/client';
import { Btn, C, Card, Dim, ErrorText, Field, Loading, Screen, Title } from '../components/ui';

const CATEGORIES = ['slang', 'phrases', 'pet_names', 'emoji', 'openers', 'closers', 'spicy'];

export default function LexiconScreen() {
  const { settings } = useSettings();
  const [bank, setBank] = useState<Record<string, LexiconEntry[]>>({});
  const [category, setCategory] = useState('slang');
  const [term, setTerm] = useState('');
  const [note, setNote] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const res = await getLexicon(settings);
      setBank(res.categories);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [settings]);

  useEffect(() => { load(); }, [load]);

  const add = async () => {
    if (!term.trim()) {
      setError('Type a word or phrase first.');
      return;
    }
    setBusy(true);
    setError(null);
    setOk(null);
    try {
      const res = await addLexiconTerm(settings, category, term.trim(), note.trim());
      setOk(res.added ? `Saved to ${res.category}: ${res.term}` : 'Already in the word bank.');
      setTerm('');
      setNote('');
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const remove = async (cat: string, t: string) => {
    setBusy(true);
    setError(null);
    try {
      await removeLexiconTerm(settings, cat, t);
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
      <Title>Word bank</Title>
      <ErrorText message={error} />
      {ok && <Text style={{ color: C.good, marginBottom: 8 }}>{ok}</Text>}
      <Dim>Her saved dictionary — slang, phrases, pet names, emoji, openers, closers. Chat drafts use her words first.</Dim>
      <Field label="Category" value={category} onChange={setCategory} placeholder={CATEGORIES.join(', ')} />
      <Field label="Word or phrase" value={term} onChange={setTerm} placeholder="e.g. papi" />
      <Field label="Note (optional)" value={note} onChange={setNote} placeholder="" />
      <Btn label={busy ? 'Saving…' : 'Add word'} onPress={add} disabled={busy} />
      <ScrollView refreshControl={<RefreshControl refreshing={false} onRefresh={load} />}>
        {CATEGORIES.map((cat) => {
          const items = bank[cat] || [];
          if (items.length === 0) return null;
          return (
            <Card key={cat}>
              <Text style={{ color: C.text, fontWeight: '600' }}>[{cat}]</Text>
              {items.map((e) => (
                <View key={e.term} style={{ flexDirection: 'row', alignItems: 'center', marginTop: 6 }}>
                  <Text style={{ color: C.text, flex: 1 }}>
                    {e.term}{e.note ? <Text style={{ color: C.dim }}> ({e.note})</Text> : null}
                  </Text>
                  <Btn label="✕" onPress={() => remove(cat, e.term)} disabled={busy} />
                </View>
              ))}
            </Card>
          );
        })}
      </ScrollView>
    </Screen>
  );
}
