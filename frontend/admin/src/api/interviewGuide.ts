import api from './index';
import type { InterviewGuideResponse, InterviewGuideListResponse, TaskStatusResponse, JdParseResponse, GenerateReportResponse, MessageResponse } from '../types/api';

export type InterviewGuide = InterviewGuideResponse;
export type TaskStatus = TaskStatusResponse;

export const listInterviewGuides = (params: { page?: number; size?: number; company?: string; status?: string }) =>
  api.get<InterviewGuideListResponse>('/admin/interview-guide/list', { params }).then(r => r.data);

export const getInterviewGuide = (id: number) =>
  api.get<InterviewGuideResponse>(`/admin/interview-guide/${id}`).then(r => r.data);

export const createInterviewGuide = (data: Partial<InterviewGuideResponse>) =>
  api.post<InterviewGuideResponse>('/admin/interview-guide/create', data).then(r => r.data);

export const updateInterviewGuide = (id: number, data: Partial<InterviewGuideResponse>) =>
  api.put<InterviewGuideResponse>(`/admin/interview-guide/${id}`, data).then(r => r.data);

export const deleteInterviewGuide = (id: number) =>
  api.delete<MessageResponse>(`/admin/interview-guide/${id}`).then(r => r.data);

export const generateReport = (guideId: number) =>
  api.post<GenerateReportResponse>(`/admin/interview-guide/${guideId}/generate-report`).then(r => r.data);

export const cancelReport = (guideId: number) =>
  api.post<MessageResponse>(`/admin/interview-guide/${guideId}/cancel-report`).then(r => r.data);

export const getTaskStatus = (guideId: number) =>
  api.get<TaskStatusResponse>(`/admin/interview-guide/${guideId}/task-status`).then(r => r.data);

export const downloadReport = (guideId: number) =>
  api.get(`/admin/interview-guide/${guideId}/report`, { responseType: 'blob' }).then(r => r.data);

export const previewReport = (guideId: number) =>
  api.get(`/admin/interview-guide/${guideId}/report-preview`, { responseType: 'text' }).then(r => r.data);

export const updateStatus = (guideId: number, status: string) =>
  api.put<MessageResponse>(`/admin/interview-guide/${guideId}/status`, { status }).then(r => r.data);

export const parseJd = (jdText: string) =>
  api.post<JdParseResponse>('/admin/interview-guide/parse-jd', { jd_text: jdText }).then(r => r.data);

export const cloneInterviewGuide = (id: number) =>
  api.post<InterviewGuideResponse>(`/admin/interview-guide/${id}/clone`).then(r => r.data);
