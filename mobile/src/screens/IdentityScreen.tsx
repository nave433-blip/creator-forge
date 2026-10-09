import React, { useCallback, useEffect, useState } from 'react';
import { ScrollView, Text } from 'react-native';
import { useSettings } from '../context/SettingsContext';
import { ApiError, IdentityStatus, getIdentity } from '../api/client';
import { Btn, C, Card, Dim, ErrorText, Loading, Screen, Title } from '../components/ui';

function statusColor(s: string): string {
  if (s === 'valid') return C.good;
  if (s === 'invalid') return C.bad;
  return C.warn;
}

export default function IdentityScreen() {
  const { settings } = useSettings();
  const [info, setInfo] = useState<IdentityStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setInfo(await getIdentity(settings));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [settings]);

  useEffect(() => { load(); }, [load]);
  if (loading) return <Screen><Loading /></Screen>;

  return (
    <Screen>
      <ScrollView>
        <Title>Identity / consent</Title>
        <ErrorText message={error} />
        {info ? (
          <Card>
            <Text style={{ color: statusColor(info.status), fontSize: 18, fontWeight: '700' }}>
              {info.status.toUpperCase()}
            </Text>
            {info.name ? <Text style={{ color: C.text, marginTop: 8 }}>Identity: {info.name}</Text> : null}
            {info.signer ? <Text style={{ color: C.text }}>Signed by: {info.signer} on {info.date}</Text> : null}
            {info.scope ? <Dim>Scope: {info.scope}</Dim> : null}
            {info.detail ? <Dim>{info.detail}</Dim> : null}
          </Card>
        ) : null}
        <Card>
          <Dim>
            Video generation is refused unless this shows VALID. The consent
            pack lives on the backend machine -- manage it there with
            `forge identity create` / `forge identity validate`.
          </Dim>
        </Card>
        <Btn label="Refresh" onPress={() => { setLoading(true); load(); }} />
      </ScrollView>
    </Screen>
  );
}
