import React from 'react';
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

export const C = {
  bg: '#111111',
  card: '#1c1c1e',
  border: '#2c2c2e',
  text: '#f5f5f5',
  dim: '#a1a1a6',
  accent: '#7c3aed',
  good: '#34c759',
  bad: '#ff453a',
  warn: '#ffd60a',
};

export function Screen({ children }: { children: React.ReactNode }) {
  return <View style={s.screen}>{children}</View>;
}

export function Title({ children }: { children: React.ReactNode }) {
  return <Text style={s.title}>{children}</Text>;
}

export function Card({ children }: { children: React.ReactNode }) {
  return <View style={s.card}>{children}</View>;
}

export function Dim({ children }: { children: React.ReactNode }) {
  return <Text style={s.dim}>{children}</Text>;
}

export function ErrorText({ message }: { message: string | null }) {
  if (!message) return null;
  return <Text style={s.error}>{message}</Text>;
}

export function Loading() {
  return (
    <View style={s.center}>
      <ActivityIndicator size="large" color={C.accent} />
    </View>
  );
}

export function Btn({
  label,
  onPress,
  danger,
  disabled,
}: {
  label: string;
  onPress: () => void;
  danger?: boolean;
  disabled?: boolean;
}) {
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      style={[s.btn, danger && s.btnDanger, disabled && s.btnDisabled]}>
      <Text style={s.btnText}>{label}</Text>
    </Pressable>
  );
}

export function Field({
  label,
  value,
  onChange,
  placeholder,
  secure,
  autoCap,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  secure?: boolean;
  autoCap?: 'none' | 'sentences';
}) {
  return (
    <View style={s.field}>
      <Text style={s.label}>{label}</Text>
      <TextInput
        style={s.input}
        value={value}
        onChangeText={onChange}
        placeholder={placeholder}
        placeholderTextColor={C.dim}
        secureTextEntry={!!secure}
        autoCapitalize={autoCap ?? 'none'}
        autoCorrect={false}
      />
    </View>
  );
}

const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: C.bg, padding: 16 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  title: { color: C.text, fontSize: 24, fontWeight: '700', marginBottom: 12 },
  card: {
    backgroundColor: C.card,
    borderColor: C.border,
    borderWidth: 1,
    borderRadius: 12,
    padding: 12,
    marginBottom: 10,
  },
  dim: { color: C.dim, fontSize: 13, marginTop: 4 },
  error: { color: C.bad, marginVertical: 8 },
  field: { marginBottom: 12 },
  label: { color: C.dim, marginBottom: 6, fontSize: 13 },
  input: {
    backgroundColor: C.card,
    borderColor: C.border,
    borderWidth: 1,
    borderRadius: 10,
    color: C.text,
    padding: 12,
    fontSize: 15,
  },
  btn: {
    backgroundColor: C.accent,
    borderRadius: 10,
    padding: 12,
    alignItems: 'center',
    marginTop: 8,
  },
  btnDanger: { backgroundColor: '#5c1a1a' },
  btnDisabled: { opacity: 0.5 },
  btnText: { color: '#fff', fontWeight: '600', fontSize: 15 },
});
