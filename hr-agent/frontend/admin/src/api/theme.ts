const THEME_KEY = 'admin_theme_mode';

export type ThemeMode = 'system' | 'light' | 'dark';

const DARK_VARS: Record<string, string> = {
  '--admin-bg': '#060a18',
  '--admin-bg-secondary': '#0c1222',
  '--admin-bg-tertiary': '#111827',
  '--admin-bg-card': '#0f1626',
  '--admin-accent': '#6366f1',
  '--admin-accent-hover': '#818cf8',
  '--admin-accent-light': 'rgba(99, 102, 241, 0.15)',
  '--admin-text': '#e2e8f0',
  '--admin-text-secondary': '#94a3b8',
  '--admin-text-muted': '#64748b',
  '--admin-border': '#1e293b',
  '--admin-success': '#10b981',
  '--admin-error': '#ef4444',
  '--admin-shadow': '0 4px 20px rgba(0,0,0,0.3)',
  '--admin-card-shadow': '0 8px 30px rgba(0,0,0,0.4)',
  '--admin-bg-gradient-1': '#0f1626',
  '--admin-bg-gradient-2': '#060a18',
  '--admin-noise-accent': 'rgba(99, 102, 241, 0.03)',
  '--admin-chat-user-bg': '#6366f1',
  '--admin-chat-assistant-bg': '#0f1626',
  '--admin-input-bg': '#111827',
  '--admin-sidebar-bg': '#0c1222',
  '--admin-sidebar-text': '#94a3b8',
  '--admin-sidebar-selected-text': '#818cf8',
  '--admin-sidebar-selected-bg': 'rgba(99, 102, 241, 0.15)',
};

const LIGHT_VARS: Record<string, string> = {
  '--admin-bg': '#f5f7fa',
  '--admin-bg-secondary': '#ffffff',
  '--admin-bg-tertiary': '#eef1f6',
  '--admin-bg-card': '#ffffff',
  '--admin-accent': '#6366f1',
  '--admin-accent-hover': '#818cf8',
  '--admin-accent-light': 'rgba(99, 102, 241, 0.08)',
  '--admin-text': '#1e293b',
  '--admin-text-secondary': '#64748b',
  '--admin-text-muted': '#94a3b8',
  '--admin-border': '#e2e8f0',
  '--admin-success': '#10b981',
  '--admin-error': '#ef4444',
  '--admin-shadow': '0 1px 3px rgba(0,0,0,0.06)',
  '--admin-card-shadow': '0 4px 16px rgba(0,0,0,0.06)',
  '--admin-bg-gradient-1': '#f5f7fa',
  '--admin-bg-gradient-2': '#e8ecf2',
  '--admin-noise-accent': 'rgba(99, 102, 241, 0.04)',
  '--admin-chat-user-bg': '#6366f1',
  '--admin-chat-assistant-bg': '#ffffff',
  '--admin-input-bg': '#ffffff',
  '--admin-sidebar-bg': '#ffffff',
  '--admin-sidebar-text': '#64748b',
  '--admin-sidebar-selected-text': '#6366f1',
  '--admin-sidebar-selected-bg': 'rgba(99, 102, 241, 0.08)',
};

export function getThemeMode(): ThemeMode {
  const saved = localStorage.getItem(THEME_KEY);
  if (saved === 'system' || saved === 'light' || saved === 'dark') return saved;
  return 'system';
}

export function setThemeMode(mode: ThemeMode) {
  localStorage.setItem(THEME_KEY, mode);
}

export function getResolvedTheme(mode: ThemeMode): 'light' | 'dark' {
  if (mode === 'system') {
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  return mode;
}

export function applyTheme(resolved: 'light' | 'dark') {
  const root = document.documentElement;
  // 1. Set data-theme attribute for CSS cascade
  root.setAttribute('data-theme', resolved);
  // 2. Directly set CSS variables on :root (highest specificity, overrides everything)
  const vars = resolved === 'dark' ? DARK_VARS : LIGHT_VARS;
  for (const [key, val] of Object.entries(vars)) {
    root.style.setProperty(key, val);
  }
  // 3. Also set body background directly for instant update
  document.body.style.background =
    resolved === 'dark'
      ? 'radial-gradient(ellipse at 50% 0%, #0f1626 0%, #060a18 100%)'
      : 'radial-gradient(ellipse at 50% 0%, #f5f7fa 0%, #e8ecf2 100%)';
}

export function listenSystemTheme(callback: (isDark: boolean) => void) {
  const mq = window.matchMedia('(prefers-color-scheme: dark)');
  const handler = (e: MediaQueryListEvent) => callback(e.matches);
  mq.addEventListener('change', handler);
  return () => mq.removeEventListener('change', handler);
}

// Set theme BEFORE first React render (module-level execution)
const initialMode = getThemeMode();
applyTheme(getResolvedTheme(initialMode));
