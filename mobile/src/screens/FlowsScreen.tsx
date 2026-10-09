import React, { useCallback, useEffect, useState } from 'react';
import { FlatList, RefreshControl, Text } from 'react-native';
import { useSettings } from '../context/SettingsContext';
import {
  ApiError,
  ComplianceFinding,
  FlowRun,
  checkCompliance,
  draftPpv,
  enrollFlow,
  getFlowPending,
  previewHumanize,
  runFlows,
} from '../api/client';
import { Btn, C, Card, Dim, ErrorText, Field, Loading, Screen, Title } from '../components/ui';

const FLOWS = ['welcome', 'winback', 'nudge'];

export default function FlowsScreen() {
  const { settings } = useSettings();
  const [pending, setPending] = useState<FlowRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [flow, setFlow] = useState('welcome');
  const [platform, setPlatform] = useState('onlyfans');
  const [handle, setHandle] = useState('');
  const [ppvText, setPpvText] = useState('');
  const [ppvSender, setPpvSender] = useState('');
  const [draftText, setDraftText] = useState('');
  const [humanized, setHumanized] = useState<string | null>(null);
  const [findings, setFindings] = useState<ComplianceFinding[] | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setPending((await getFlowPending(settings)).pending);
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
      <Title>Message flows</Title>
      <Dim>Welcome, win-back, and nudge sequences. Due steps are drafted into the approval queue — nothing auto-sends.</Dim>
      <ErrorText message={error} />
      {ok ? <Text style={{ color: C.accent }}>{ok}</Text> : null}

      <Card>
        <Text style={{ color: C.text, fontWeight: '700' }}>Enroll a fan</Text>
        <Field label="Flow (welcome | winback | nudge)" value={flow} onChange={setFlow} />
        <Field label="Platform" value={platform} onChange={setPlatform} />
        <Field label="Fan handle" value={handle} onChange={setHandle} placeholder="fan_handle" />
        <Btn label="Enroll" onPress={() => {
          if (!handle.trim()) { setError('Enter a fan handle.'); return; }
          enrollFlow(settings, flow.trim(), platform.trim(), handle.trim())
            .then(() => { setOk(`${handle} enrolled in ${flow}.`); setHandle(''); load(); })
            .catch((e) => setError(e instanceof ApiError ? e.message : String(e)));
        }} />
        <Btn label="Run due steps now" onPress={() => runFlows(settings)
          .then((r) => { setOk(`Drafted ${r.drafted} step(s) for approval.`); load(); })
          .catch((e) => setError(e instanceof ApiError ? e.message : String(e)))} />
      </Card>

      <FlatList
        data={pending}
        keyExtractor={(r) => String(r.id)}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}
        renderItem={({ item }) => (
          <Card>
            <Text style={{ color: C.text, fontWeight: '700' }}>{item.flow} → {item.handle}</Text>
            <Dim>{item.platform} · step {item.step_idx + 1} · due {item.due_at}</Dim>
          </Card>
        )}
        ListEmptyComponent={<Dim>No active flow runs.</Dim>}
      />

      <Card>
        <Text style={{ color: C.text, fontWeight: '700' }}>PPV upsell draft</Text>
        <Dim>Paste the fan's message — if it shows buying intent, an offer is drafted for approval.</Dim>
        <Field label="Sender" value={ppvSender} onChange={setPpvSender} placeholder="fan_handle" />
        <Field label="Their message" value={ppvText} onChange={setPpvText} placeholder="how much for a custom?" />
        <Btn label="Draft PPV offer" onPress={() => draftPpv(settings, platform.trim(), ppvSender.trim(), ppvText)
          .then((r) => setOk(r.drafted ? `Draft #${r.draft_id} queued: ${r.reply}` : (r.note || 'No buying intent detected.')))
          .catch((e) => setError(e instanceof ApiError ? e.message : String(e)))} />
      </Card>

      <Card>
        <Text style={{ color: C.text, fontWeight: '700' }}>Humanizer + compliance</Text>
        <Field label="Draft text" value={draftText} onChange={setDraftText} placeholder="Hey! Thanks for messaging me" />
        <Btn label="Preview humanizer" onPress={() => previewHumanize(settings, draftText)
          .then((r) => setHumanized(r.humanized))
          .catch((e) => setError(e instanceof ApiError ? e.message : String(e)))} />
        {humanized ? <Text style={{ color: C.text, marginTop: 6 }}>{humanized}</Text> : null}
        <Btn label="Compliance check" onPress={() => checkCompliance(settings, draftText)
          .then((r) => { setFindings(r.findings); setOk(r.clean ? 'Clean — no flags.' : `${r.findings.length} flag(s).`); })
          .catch((e) => setError(e instanceof ApiError ? e.message : String(e)))} />
        {findings?.map((f) => <Dim key={f.match + f.category}>[{f.category}] {f.match}: {f.detail}</Dim>)}
      </Card>
    </Screen>
  );
}
