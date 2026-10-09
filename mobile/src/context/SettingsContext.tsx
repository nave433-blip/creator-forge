import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import type { BackendSettings } from '../api/client';

const STORAGE_KEY = '@creatorforge:backend-settings';

interface SettingsContextValue {
  settings: BackendSettings;
  loaded: boolean;
  save: (s: BackendSettings) => Promise<void>;
  clear: () => Promise<void>;
}

const SettingsContext = createContext<SettingsContextValue>({
  settings: { baseUrl: '', apiToken: '' },
  loaded: false,
  save: async () => {},
  clear: async () => {},
});

export function SettingsProvider({ children }: { children: React.ReactNode }) {
  const [settings, setSettings] = useState<BackendSettings>({
    baseUrl: '',
    apiToken: '',
  });
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const raw = await AsyncStorage.getItem(STORAGE_KEY);
        if (raw) setSettings(JSON.parse(raw) as BackendSettings);
      } catch {
        /* corrupted storage -> start fresh */
      } finally {
        setLoaded(true);
      }
    })();
  }, []);

  const save = useCallback(async (s: BackendSettings) => {
    setSettings(s);
    await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(s));
  }, []);

  const clear = useCallback(async () => {
    setSettings({ baseUrl: '', apiToken: '' });
    await AsyncStorage.removeItem(STORAGE_KEY);
  }, []);

  return (
    <SettingsContext.Provider value={{ settings, loaded, save, clear }}>
      {children}
    </SettingsContext.Provider>
  );
}

export const useSettings = () => useContext(SettingsContext);
