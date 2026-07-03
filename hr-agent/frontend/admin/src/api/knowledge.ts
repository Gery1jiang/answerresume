import api from './index';
import type { KnowledgeCategoryResponse, KnowledgeStructuredResponse, AppendixInfoResponse, AppendixRecordsResponse, MessageResponse } from '../types/api';

export const getKnowledge = (category: string) =>
  api.get<KnowledgeCategoryResponse>(`/admin/knowledge/${category}`).then(r => r.data);

export const saveKnowledge = (category: string, content: string) =>
  api.post<MessageResponse>(`/admin/knowledge/${category}`, { content }).then(r => r.data);

export const getKnowledgeStructured = (category: string) =>
  api.get<KnowledgeStructuredResponse>(`/admin/knowledge-structured/${category}`).then(r => r.data);

export const saveKnowledgeStructured = (category: string, data: any) =>
  api.post<MessageResponse>(`/admin/knowledge-structured/${category}`, { data }).then(r => r.data);

export const rebuildVector = () =>
  api.post<MessageResponse>('/admin/kb/rebuild-vector').then(r => r.data);

export const getAppendixInfo = () =>
  api.get<AppendixInfoResponse>('/admin/appendix/info').then(r => r.data);

export const getAppendixRecords = () =>
  api.get<AppendixRecordsResponse>('/admin/appendix/records').then(r => r.data);

export const deleteAppendixRecord = (id: number) =>
  api.delete<MessageResponse>(`/admin/appendix/records/${id}`).then(r => r.data);

export const clearAppendix = () =>
  api.post<MessageResponse>('/admin/appendix/clear').then(r => r.data);

export const uploadAppendix = (file: File) => {
  const form = new FormData();
  form.append('file', file);
  return api.post<MessageResponse>('/admin/appendix/upload', form).then(r => r.data);
};

export const getFaqData = () =>
  api.get<KnowledgeStructuredResponse>('/admin/knowledge-structured/faq').then(r => r.data);

export const saveFaq = (faqList: any[]) =>
  api.post<MessageResponse>('/admin/knowledge-structured/faq', { data: { faq_list: faqList } }).then(r => r.data);

export const clearFaqAnswers = () =>
  api.post<MessageResponse>('/admin/kb/clear-faq-answers').then(r => r.data);
