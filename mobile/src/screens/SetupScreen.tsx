import React, { useState } from 'react';
import { ScrollView, Text } from 'react-native';
import { useSettings } from '../context/SettingsContext';
import { ApiError, getIdentity } from '../api/client';
import { Btn, C, Card, Dim, ErrorText, Field, Screen, Title } from '../components/ui';

export default function SetupScreen() {
  const { settings, save } = useSettings();
  const [baseUrl, setBaseUrl] = useState(settings.baseUrl);
  const [apiToken, setApiToken] = useState(settings.apiToken);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const test = async () => {
    setBusy(true);
    setError(null);
    setStatus(null);
    const s = { baseUrl, apiToken };
    try {
      await save(s);
      await getIdentity(s);
      setStatus('Connected! Backend is reachable.');
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Screen>
      <ScrollView>
        <Title>Backend setup</Title>
        <Card>
          <Text style={{ color: C.text }}>
            Point the app at the machine running{'\n'}
            <Text style={{ fontWeight: '700' }}>forge dashboard</Text>
          </Text>
          <Dim>
            On your home Wi-Fi this looks like http://192.168.1.5:8765.
            Start the backend with: forge dashboard --host 0.0.0.0
          </Dim>
        </Card>
        <Field
          label="Backend URL"
          value={baseUrl}
          onChange={setBaseUrl}
          placeholder="http://192.168.1.5:8765"
        />
        <Field
          label="API token (only if dashboard.api_token is set)"
          value={apiToken}
          onChange={setApiToken}
          placeholder="optional"
          secure
        />
        <Btn label={busy ? 'Testing...' : 'Save & test connection'} onPress={test} disabled={busy} />
        <ErrorText message={error} />
        {status ? <Text style={{ color: C.good, marginTop: 8 }}>{status}</Text> : null}
      </ScrollView>
    </Screen>
  );
}
