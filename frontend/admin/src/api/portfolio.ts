import api from './index';
import type { PortfolioConfig, KnowledgeData, StyleOption, PortfolioPreviewResponse, PortfolioStatusResponse, PortfolioToggleResponse, MessageResponse } from '../types/api';

export type { PortfolioConfig, KnowledgeData, StyleOption };

export async function getPortfolioConfig(): Promise<PortfolioConfig> {
  const resp = await api.get<PortfolioConfig>('/admin/portfolio/config');
  return resp.data;
}

export async function savePortfolioConfig(config: Partial<PortfolioConfig>): Promise<PortfolioConfig> {
  const resp = await api.post<PortfolioConfig>('/admin/portfolio/config', config);
  return resp.data;
}

export async function getPortfolioPreview(): Promise<PortfolioPreviewResponse> {
  const resp = await api.get<PortfolioPreviewResponse>('/admin/portfolio/preview');
  return resp.data;
}

export async function exportPortfolioHTML(style: string): Promise<string> {
  const resp = await api.post<string>('/admin/portfolio/export', { style }, { responseType: 'text' });
  return resp.data;
}

export async function getStyles(): Promise<{ styles: StyleOption[] }> {
  const resp = await api.get<{ styles: StyleOption[] }>('/admin/portfolio/styles');
  return resp.data;
}

export async function getPortfolioShowStatus(): Promise<PortfolioStatusResponse> {
  const resp = await api.get<PortfolioStatusResponse>('/admin/portfolio/status');
  return resp.data;
}

export async function togglePortfolioShow(): Promise<PortfolioToggleResponse> {
  const resp = await api.get<PortfolioToggleResponse>('/admin/portfolio/toggle');
  return resp.data;
}

export async function rebuildPortfolio(): Promise<{ status: string; message: string; items: number }> {
  const resp = await api.post<{ status: string; message: string; items: number }>('/admin/portfolio/rebuild');
  return resp.data;
}

export async function getPortfolioBuildStatus(): Promise<{ built: boolean; built_at: string | null }> {
  const resp = await api.get<{ built: boolean; built_at: string | null }>('/admin/portfolio/build-status');
  return resp.data;
}
