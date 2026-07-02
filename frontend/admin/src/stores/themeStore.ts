import { create } from 'zustand';
import { persist } from 'zustand/middleware';

const STORAGE_KEY = 'admin_theme_mode';

export type ThemeMode = 'light' | 'dark' | 'system';

interface ThemeState {
  mode: ThemeMode;
  setMode: (mode: ThemeMode) => void;
  resolved: () => 'light' | 'dark';
}

function getSystemPref(): 'light' | 'dark' {
  if (typeof window === 'undefined') return 'light';
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function resolveTheme(mode: ThemeMode): 'light' | 'dark' {
  if (mode === 'system') return getSystemPref();
  return mode;
}

function applyTheme(resolved: 'light' | 'dark') {
  document.documentElement.setAttribute('data-theme', resolved);
}

export const useThemeStore = create<ThemeState>()(
  persist(
    (set, get) => ({
      mode: 'light',

      setMode: (mode: ThemeMode) => {
        set({ mode });
        applyTheme(resolveTheme(mode));
      },

      resolved: () => resolveTheme(get().mode),
    }),
    {
      name: STORAGE_KEY,
      partialize: (state) => ({ mode: state.mode }),
    }
  )
);

if (typeof window !== 'undefined') {
  const stored = localStorage.getItem(STORAGE_KEY);
  const initialMode: ThemeMode = stored === 'dark' || stored === 'system' ? stored : 'light';
  useThemeStore.getState().setMode(initialMode);

  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    const state = useThemeStore.getState();
    if (state.mode === 'system') {
      applyTheme(getSystemPref());
    }
  });
}
