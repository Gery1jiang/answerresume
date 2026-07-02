import api from './index';
import type { ConfigResponse, PromptResponse, WelcomeConfigResponse, GenerateIntroResponse, MessageResponse } from '../types/api';

export const getConfig = () =>
  api.get<ConfigResponse>('/admin/config').then(r => r.data);

export const updateConfig = (data: Partial<ConfigResponse>) =>
  api.post<MessageResponse>('/admin/config', data).then(r => r.data);

export const testLlm = (provider: string, apiKey: string, model: string, baseUrl: string) =>
  api.post<MessageResponse>('/admin/config/test-llm', { provider, api_key: apiKey, model, base_url: baseUrl }).then(r => r.data);

export const testEmbedding = (apiKey: string, model: string, baseUrl: string) =>
  api.post<MessageResponse>('/admin/config/test-embedding', { api_key: apiKey, model, base_url: baseUrl }).then(r => r.data);

export const getPrompt = () =>
  api.get<PromptResponse>('/admin/prompt').then(r => r.data);

export const savePrompt = (content: string) =>
  api.post<MessageResponse>('/admin/prompt', { content }).then(r => r.data);

export const getResumePrompt = () =>
  api.get<PromptResponse>('/admin/prompt/resume').then(r => r.data);

export const saveResumePrompt = (content: string) =>
  api.post<MessageResponse>('/admin/prompt/resume', { content }).then(r => r.data);

export const getAgentPrompt = () =>
  api.get<PromptResponse>('/admin/prompt/agent').then(r => r.data);

export const saveAgentPrompt = (content: string) =>
  api.post<MessageResponse>('/admin/prompt/agent', { content }).then(r => r.data);

export const getVisitorPrompt = () =>
  api.get<PromptResponse>('/admin/prompt/visitor').then(r => r.data);

export const saveVisitorPrompt = (content: string) =>
  api.post<MessageResponse>('/admin/prompt/visitor', { content }).then(r => r.data);

export const getWelcomeConfig = () =>
  api.get<WelcomeConfigResponse>('/admin/welcome-config').then(r => r.data);

export const updateWelcomeConfig = (data: Partial<WelcomeConfigResponse>) =>
  api.post<MessageResponse>('/admin/welcome-config', data).then(r => r.data);

export const generateWelcomeIntro = () =>
  api.post<GenerateIntroResponse>('/admin/welcome-config/generate-intro').then(r => r.data);

export const changePassword = (oldPassword: string, newPassword: string) =>
  api.post<MessageResponse>('/admin/change-password', { old_password: oldPassword, new_password: newPassword }).then(r => r.data);

export interface MyConfigResponse {
  visitor_enabled: boolean;
  visitor_password: string;
}

export const getMyConfig = () =>
  api.get<MyConfigResponse>('/admin/my-config').then(r => r.data);

export const updateMyConfig = (data: { visitor_enabled?: boolean; visitor_password?: string }) =>
  api.post<MessageResponse>('/admin/my-config', data).then(r => r.data);

export interface UserProfile {
  display_name: string;
  email: string;
}

export const getMyProfile = () =>
  api.get<UserProfile>('/admin/me').then(r => r.data);

export const updateMyProfile = (data: { display_name?: string; email?: string }) =>
  api.post<MessageResponse>('/admin/update-profile', data).then(r => r.data);
