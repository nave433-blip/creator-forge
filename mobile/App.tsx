import React, { useState } from 'react';
import { Pressable, SafeAreaView, StatusBar, StyleSheet, Text, View } from 'react-native';
import { SettingsProvider, useSettings } from './src/context/SettingsContext';
import { C } from './src/components/ui';
import SetupScreen from './src/screens/SetupScreen';
import CatalogScreen from './src/screens/CatalogScreen';
import IdentityScreen from './src/screens/IdentityScreen';
import ChatQueueScreen from './src/screens/ChatQueueScreen';
import PayScreen from './src/screens/PayScreen';
import PacketsScreen from './src/screens/PacketsScreen';
import ScheduleScreen from './src/screens/ScheduleScreen';
import AnalyticsScreen from './src/screens/AnalyticsScreen';
import TemplatesScreen from './src/screens/TemplatesScreen';
import TriageScreen from './src/screens/TriageScreen';
import SpicyScreen from './src/screens/SpicyScreen';
import OrdersScreen from './src/screens/OrdersScreen';
import LiveScreen from './src/screens/LiveScreen';
import CRMScreen from './src/screens/CRMScreen';
import StreamScreen from './src/screens/StreamScreen';
import FlowsScreen from './src/screens/FlowsScreen';
import IdeasScreen from './src/screens/IdeasScreen';
import TubeScreen from './src/screens/TubeScreen';
import LexiconScreen from './src/screens/LexiconScreen';
import AIScreen from './src/screens/AIScreen';

type Tab = 'catalog' | 'identity' | 'chat' | 'pay' | 'packets' | 'schedule' | 'analytics' | 'templates' | 'triage' | 'spicy' | 'orders' | 'live' | 'crm' | 'stream' | 'flows' | 'ideas' | 'tube' | 'lexicon' | 'ai' | 'setup';

const TABS: { key: Tab; label: string }[] = [
  { key: 'chat', label: 'Chat' },
  { key: 'triage', label: 'Triage' },
  { key: 'spicy', label: 'Spicy' },
  { key: 'orders', label: 'Orders' },
  { key: 'live', label: 'Live' },
  { key: 'crm', label: 'CRM' },
  { key: 'stream', label: 'Stream' },
  { key: 'flows', label: 'Flows' },
  { key: 'ideas', label: 'Ideas' },
  { key: 'tube', label: 'Tube' },
  { key: 'lexicon', label: 'Words' },
  { key: 'ai', label: 'AI' },
  { key: 'schedule', label: 'Schedule' },
  { key: 'templates', label: 'Replies' },
  { key: 'analytics', label: 'Stats' },
  { key: 'catalog', label: 'Catalog' },
  { key: 'packets', label: 'Packets' },
  { key: 'pay', label: 'Pay' },
  { key: 'identity', label: 'Consent' },
  { key: 'setup', label: 'Setup' },
];

function Shell() {
  const { settings, loaded } = useSettings();
  const [tab, setTab] = useState<Tab>('chat');

  if (!loaded) return null;
  const needsSetup = !settings.baseUrl;

  return (
    <SafeAreaView style={s.root}>
      <StatusBar barStyle="light-content" backgroundColor={C.bg} />
      <View style={s.body}>
        {needsSetup ? (
          <SetupScreen />
        ) : tab === 'catalog' ? (
          <CatalogScreen />
        ) : tab === 'identity' ? (
          <IdentityScreen />
        ) : tab === 'chat' ? (
          <ChatQueueScreen />
        ) : tab === 'triage' ? (
          <TriageScreen />
        ) : tab === 'spicy' ? (
          <SpicyScreen />
        ) : tab === 'orders' ? (
          <OrdersScreen />
        ) : tab === 'live' ? (
          <LiveScreen />
        ) : tab === 'crm' ? (
          <CRMScreen />
        ) : tab === 'stream' ? (
          <StreamScreen />
        ) : tab === 'flows' ? (
          <FlowsScreen />
        ) : tab === 'ideas' ? (
          <IdeasScreen />
        ) : tab === 'tube' ? (
          <TubeScreen />
        ) : tab === 'lexicon' ? (
          <LexiconScreen />
        ) : tab === 'ai' ? (
          <AIScreen />
        ) : tab === 'schedule' ? (
          <ScheduleScreen />
        ) : tab === 'templates' ? (
          <TemplatesScreen />
        ) : tab === 'analytics' ? (
          <AnalyticsScreen />
        ) : tab === 'pay' ? (
          <PayScreen />
        ) : tab === 'packets' ? (
          <PacketsScreen />
        ) : (
          <SetupScreen />
        )}
      </View>
      {!needsSetup && (
        <View style={s.tabs}>
          {TABS.map((t) => (
            <Pressable
              key={t.key}
              onPress={() => setTab(t.key)}
              style={[s.tab, tab === t.key && s.tabActive]}>
              <Text style={[s.tabText, tab === t.key && s.tabTextActive]}>
                {t.label}
              </Text>
            </Pressable>
          ))}
        </View>
      )}
    </SafeAreaView>
  );
}

export default function App() {
  return (
    <SettingsProvider>
      <Shell />
    </SettingsProvider>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.bg },
  body: { flex: 1 },
  tabs: {
    flexDirection: 'row',
    borderTopWidth: 1,
    borderTopColor: C.border,
    backgroundColor: C.card,
  },
  tab: { flex: 1, paddingVertical: 14, alignItems: 'center' },
  tabActive: { borderTopWidth: 2, borderTopColor: C.accent },
  tabText: { color: C.dim, fontSize: 12, fontWeight: '600' },
  tabTextActive: { color: C.text },
});
