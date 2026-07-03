import api from './index';
import type { StatsResponse, QuestionStatsResponse, SessionListResponse, ConversationListResponse, StatsClearResponse } from '../types/api';

export const getStats = () =>
  api.get<StatsResponse>('/admin/stats').then(r => r.data);

export const getQuestionStats = () =>
  api.get<QuestionStatsResponse>('/admin/stats/questions').then(r => r.data?.questions || []);

export const getSessions = () =>
  api.get<SessionListResponse>('/admin/sessions').then(r => r.data);

export const getSessionConversations = (sessionId: string) =>
  api.get<ConversationListResponse>(`/admin/sessions/${sessionId}/conversations`).then(r => r.data);

export const clearStats = () =>
  api.post<StatsClearResponse>('/admin/stats/clear').then(r => r.data);
