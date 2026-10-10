import React, { useCallback, useEffect, useState } from 'react';
import { RefreshControl, ScrollView, Text } from 'react-native';
import { useSettings } from '../context/SettingsContext';
import { ApiError, TelegramStatus, getTelegramStatus, sendTelegram } from '../api/client';
import { Btn, C, Card, Dim, ErrorText, Field, Loading, Screen, Title } from '../components/ui';

export default function TelegramScreen() {
  const { settings } = useSettings();
  const [status, setStatus] = useState<TelegramStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [chat, setChat] = useState('');
  const [text, setText] = useState('');
  const [mediaPath, setMediaPath] = useState('');
  const [stars, setStars] = useState('');
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setStatus(await getTelegramStatus(settings));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [settings]);

  useEffect(() => { load(); }, [load]);

  const doSend = async () => {
    setError(null);
    setSent(null);
    setSending(true);
    try {
      const paid = stars.trim() ? parseInt(stars.trim(), 10) : 0;
      const res = await sendTelegram(settings, {
        chat: chat.trim() || undefined,
        text: text.trim() || undefined,
        photo: mediaPath.trim() || undefined,
        paid_stars: paid > 0 ? paid : undefined,
      });
      setSent(
        `Sent (message ${res.message_id})` +
          (res.paid_stars ? ` behind a ${res.paid_stars}-Star paywall` : '') +
          '.',
      );
      setText('');
      setMediaPath('');
      setStars('');
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setSending(false);
    }
  };

  if (loading) return <Screen><Loading /></Screen>;

  return (
    <Screen>
      <ScrollView
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}>
        <Title>Telegram</Title>
        <ErrorText message={error} />
        {status && !status.configured ? (
          <Card>
            <Text style={{ color: C.text, fontWeight: '700' }}>Bot not configured</Text>
            <Dim>
              Message @BotFather on Telegram, create a bot, and set telegram.bot_token in forge.yaml
              (or TELEGRAM_BOT_TOKEN). Add the bot as admin to your channel.
            </Dim>
          </Card>
        ) : (
          <>
            {status?.username ? (
              <Dim>Connected as @{status.username}.</Dim>
            ) : status?.error ? (
              <Dim>Token set, but Telegram said: {status.error}</Dim>
            ) : null}
            <Card>
              <Text style={{ color: C.text, fontWeight: '700', fontSize: 16, marginBottom: 8 }}>
                Send announcement
              </Text>
              <Field label="Chat (blank = default)" value={chat} onChange={setChat}
                placeholder="@channel or chat id" />
              <Field label="Text" value={text} onChange={setText}
                placeholder="Drop announcement..." autoCap="sentences" />
              <Field label="Photo path (server file, optional)" value={mediaPath}
                onChange={setMediaPath} placeholder="/path/to/drop.jpg" />
              <Field label="Stars paywall (optional, PPV)" value={stars} onChange={setStars}
                placeholder="e.g. 50" />
              <Dim>
                Media paths are files on the computer running the dashboard. A Stars
                price puts the media behind a paywall; Stars revenue lives inside Telegram.
              </Dim>
              <Btn label={sending ? 'Sending...' : 'Send'} onPress={doSend}
                disabled={sending || (!text.trim() && !mediaPath.trim())} />
              {sent ? <Dim>{sent}</Dim> : null}
            </Card>
          </>
        )}
      </ScrollView>
    </Screen>
  );
}
