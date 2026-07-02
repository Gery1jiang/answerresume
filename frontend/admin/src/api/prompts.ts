import api from './index';
import type { PromptListItem, PromptDetail, MessageResponse } from '../types/api';

export const listPrompts = () =>
  api.get<{ ok: boolean; data: PromptListItem[] }>('/api/admin/prompts').then(r => r.data.data);

export const getPromptDetail = (key: string) =>
  api.get<{ ok: boolean; data: PromptDetail }>(`/api/admin/prompts/${key}`).then(r => r.data.data);

export const updatePrompt = (key: string, content: string, changeLog: string = '管理员后台更新', createdBy: string = 'admin') =>
  api.put<MessageResponse>(`/api/admin/prompts/${key}`, { content, change_log: changeLog, created_by: createdBy }).then(r => r.data);

export const rollbackPrompt = (key: string, version: number, createdBy: string = 'admin') =>
  api.post<MessageResponse>(`/api/admin/prompts/${key}/rollback/${version}`, { created_by: createdBy }).then(r => r.data);
