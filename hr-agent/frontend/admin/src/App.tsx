import { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom';
import { ConfigProvider, theme } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import MainLayout from './layouts/MainLayout';
import LoginPage from './pages/login/LoginPage';
import AgentPage from './pages/agent/AgentPage';
import ResumePage from './pages/resume/ResumePage';
import KnowledgePage from './pages/knowledge/KnowledgePage';
import JobRadarPage from './pages/jobs/JobRadarPage';
import StatisticsPage from './pages/statistics/StatisticsPage';
import ConfigPage from './pages/config/ConfigPage';
import { PortfolioPage } from './pages/portfolio/PortfolioPage';
import InterviewGuidePage from './pages/interview-guide/InterviewGuidePage';
import RegisterPage from './pages/login/RegisterPage';
import MyConfigPage from './pages/config/MyConfigPage';
import AccessSettingsPage from './pages/config/AccessSettingsPage';
import UsagePage from './pages/usage/UsagePage';
import UserManagePage from './pages/system/UserManagePage';

import { getToken, getStoredRole } from './api';
import {
  getThemeMode, setThemeMode, getResolvedTheme, applyTheme, listenSystemTheme,
} from './api/theme';
import type { ThemeMode } from './api/theme';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  if (!getToken()) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function RootRedirect() {
  const role = getStoredRole();
  if (role === 'super_admin') return <Navigate to="/admin/users" replace />;
  return <Navigate to="/agent" replace />;
}

function SuperAdminRoute() {
  const role = getStoredRole();
  if (!getToken()) return <Navigate to="/login" replace />;
  if (role !== 'super_admin') return <Navigate to="/" replace />;
  return <Outlet />;
}

// ------------------------------------------------
// Dark Theme Tokens
// ------------------------------------------------
const DARK = {
  token: {
    colorPrimary: '#6366f1',
    colorSuccess: '#10b981',
    colorError: '#ef4444',
    colorWarning: '#f59e0b',
    colorInfo: '#6366f1',
    colorBgContainer: '#0f1626',
    colorBgElevated: '#141b2d',
    colorBgLayout: '#060a18',
    colorBorder: '#1e293b',
    colorText: '#e2e8f0',
    colorTextSecondary: '#94a3b8',
    colorTextTertiary: '#64748b',
    colorTextQuaternary: '#475569',
    colorTextPlaceholder: '#64748b',
    colorBgContainerDisabled: '#0a0e1a',
    colorTextDisabled: '#475569',
    borderRadius: 8,
  },
  components: {
    Card: { colorBgContainer: '#0f1626' },
    Menu: {
      colorBgContainer: '#0c1222',
      colorItemBg: '#0c1222',
      colorItemBgHover: 'rgba(99, 102, 241, 0.08)',
      colorItemBgSelected: 'rgba(99, 102, 241, 0.15)',
      colorItemText: '#94a3b8',
      colorItemTextHover: '#e2e8f0',
      colorItemTextSelected: '#818cf8',
    },
    Table: { colorBgContainer: '#0f1626', borderColor: '#1e293b' },
    Modal: { contentBg: '#0f1626', headerBg: '#0f1626' },
    Input: { colorBgContainer: '#111827' },
    InputNumber: { colorBgContainer: '#111827' },
    Select: { colorBgContainer: '#111827' },
    Tabs: { colorBgContainer: '#0f1626' },
    Switch: { colorPrimary: '#6366f1' },
    Radio: { colorPrimary: '#6366f1' },
    Upload: { colorBgContainer: '#111827' },
  },
};

// ------------------------------------------------
// Light Theme Tokens
// ------------------------------------------------
const LIGHT = {
  token: {
    colorPrimary: '#6366f1',
    colorSuccess: '#10b981',
    colorError: '#ef4444',
    colorWarning: '#f59e0b',
    colorInfo: '#6366f1',
    colorBgContainer: '#ffffff',
    colorBgElevated: '#ffffff',
    colorBgLayout: '#f5f7fa',
    colorBorder: '#e2e8f0',
    colorText: '#1e293b',
    colorTextSecondary: '#64748b',
    colorTextTertiary: '#94a3b8',
    colorTextQuaternary: '#cbd5e1',
    colorTextPlaceholder: '#94a3b8',
    colorBgContainerDisabled: '#f1f5f9',
    colorTextDisabled: '#cbd5e1',
    borderRadius: 8,
  },
  components: {
    Card: { colorBgContainer: '#ffffff' },
    Menu: {
      colorBgContainer: '#ffffff',
      colorItemBg: '#ffffff',
      colorItemBgHover: 'rgba(99, 102, 241, 0.04)',
      colorItemBgSelected: 'rgba(99, 102, 241, 0.08)',
      colorItemText: '#64748b',
      colorItemTextHover: '#1e293b',
      colorItemTextSelected: '#6366f1',
    },
    Table: { colorBgContainer: '#ffffff', borderColor: '#e2e8f0' },
    Modal: { contentBg: '#ffffff', headerBg: '#ffffff' },
    Input: { colorBgContainer: '#ffffff' },
    InputNumber: { colorBgContainer: '#ffffff' },
    Select: { colorBgContainer: '#ffffff' },
    Tabs: { colorBgContainer: '#ffffff' },
    Switch: { colorPrimary: '#6366f1' },
    Radio: { colorPrimary: '#6366f1' },
    Upload: { colorBgContainer: '#fafafa' },
  },
};

export default function App() {
  const [mode, setMode] = useState<ThemeMode>(getThemeMode);

  // On mount and mode change: resolve theme + set data-theme
  useEffect(() => {
    const resolved = getResolvedTheme(mode);
    applyTheme(resolved);
  }, [mode]);

  // Listen for system preference changes in system mode
  useEffect(() => {
    if (mode !== 'system') return;
    const cleanup = listenSystemTheme((isDark) => {
      applyTheme(isDark ? 'dark' : 'light');
    });
    return cleanup;
  }, [mode]);

  const resolved = getResolvedTheme(mode);
  const isDark = resolved === 'dark';
  const themeConfig = isDark ? DARK : LIGHT;

  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        algorithm: isDark ? theme.darkAlgorithm : theme.defaultAlgorithm,
        token: themeConfig.token,
        components: themeConfig.components,
      }}
    >
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <MainLayout />
              </ProtectedRoute>
            }
          >
            <Route index element={<RootRedirect />} />
            <Route path="agent" element={<AgentPage />} />
            <Route path="resume" element={<ResumePage />} />
            <Route path="jobs" element={<JobRadarPage />} />
            <Route path="interview-guide" element={<InterviewGuidePage />} />
            <Route path="knowledge" element={<KnowledgePage />} />
            <Route path="statistics" element={<StatisticsPage />} />
            <Route path="my-config" element={<MyConfigPage />} />
            <Route path="access-settings" element={<AccessSettingsPage />} />
            <Route path="portfolio" element={<PortfolioPage />} />

            {/* super_admin only routes */}
            <Route element={<SuperAdminRoute />}>
              <Route path="config" element={<Navigate to="config/service" replace />} />
              <Route path="config/:tab" element={<ConfigPage themeMode={mode} onThemeModeChange={(m: ThemeMode) => { setMode(m); setThemeMode(m); }} />} />
              <Route path="admin/users" element={<UserManagePage />} />
              <Route path="admin/usage" element={<UsagePage />} />
            </Route>
          </Route>
        </Routes>
      </BrowserRouter>
    </ConfigProvider>
  );
}
