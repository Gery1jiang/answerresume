import api from './index';
import type { ResumeDetailResponse, ResumeListResponse, ResumeStatusResponse, ResumeToggleResponse, TemplatesResponse, ResumeGenerateResponse, MessageResponse } from '../types/api';

export type Resume = ResumeDetailResponse;

export interface ResumeTemplate {
  key: string;
  name: string;
  desc: string;
}

export const getTemplates = () =>
  api.get<TemplatesResponse>('/admin/resume/templates').then(r => r.data.templates.map(t => ({ key: t, name: t, desc: '' })));

export const getResumes = () =>
  api.get<ResumeListResponse>('/admin/resumes').then(r => r.data);

export const getResume = (id: number) =>
  api.get<ResumeDetailResponse>(`/admin/resumes/${id}`).then(r => r.data);

export const generateResume = (jd: string, targetJob: string, template: string) =>
  api.post<ResumeGenerateResponse>('/admin/resume/generate-with-template', { jd, target_job: targetJob, template }).then(r => r.data);

export const deleteResume = (id: number) =>
  api.delete<MessageResponse>(`/admin/resumes/${id}`).then(r => r.data);

export const setDefaultResume = (id: number) =>
  api.post<MessageResponse>(`/admin/resumes/${id}/set-default`).then(r => r.data);

export const updateTemplate = (id: number, template: string) =>
  api.post<MessageResponse>(`/admin/resumes/${id}/template`, { template }).then(r => r.data);

export const toggleResumeShow = () =>
  api.get<ResumeToggleResponse>('/admin/resume/toggle').then(r => r.data);

export const getResumeStatus = () =>
  api.get<ResumeStatusResponse>('/admin/resume/status').then(r => r.data);

const getToken = () => localStorage.getItem('admin_token') || '';

export const getResumeViewUrl = (id: number, template: string) =>
  `/admin/resumes/${id}/view?template=${template}&token=${getToken()}`;

export const getResumeDownloadUrl = (id: number, template: string) =>
  `/admin/resumes/${id}/download?template=${template}&token=${getToken()}`;
