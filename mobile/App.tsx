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

type Tab = 'catalog' | 'identity' | 'chat' | 'pay' | 'packets' | 'setup';

const TABS: { key: Tab; label: string }[] = [
  { key: 'catalog', label: 'Catalog' },
  { key: 'identity', label: 'Consent' },
  { key: 'chat', label: 'Chat' },
  { key: 'pay', label: 'Pay' },
  { key: 'packets', label: 'Packets' },
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
