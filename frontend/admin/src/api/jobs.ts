import api from './index';
import type { JobListItem, JobListResponse, JobDetailResponse, JobAddResponse, JobMatchResponse, CrawlJobsResponse, CrawlSubmitResponse, JobBatchMatchResponse, MessageResponse } from '../types/api';

export type CrawledJob = JobListItem;

export interface Dimension {
  score: number;
  max: number;
  detail: string;
  matched?: string[];
  missing?: string[];
}

export interface JdParsed {
  education: string;
  experience_years: number;
  skills: string[];
  responsibilities: string[];
  industry: string;
  salary_min: number;
  salary_max: number;
  location: string;
}

export interface MatchDetail {
  score: number;
  dimensions?: {
    education: Dimension;
    experience: Dimension;
    skills: Dimension;
    location: Dimension;
    salary: Dimension;
    responsibility: Dimension;
    industry: Dimension;
    complexity: Dimension;
  };
  summary: string;
  matched_skills: string[];
  missing_skills: string[];
  jd_parsed?: JdParsed;
}

export const getJobs = (params?: { status?: string; min_score?: number; keyword?: string }) =>
  api.get<JobListResponse>('/admin/jobs', { params }).then((r) => r.data);

export const getJob = (id: number) =>
  api.get<JobDetailResponse>(`/admin/jobs/${id}`).then((r) => r.data);

export const addJob = (data: {
  title: string;
  company?: string;
  city?: string;
  salary?: string;
  jd_text?: string;
  jd_url?: string;
  platform?: string;
}) => api.post<JobAddResponse>('/admin/jobs', data).then((r) => r.data);

export const matchJob = (id: number) =>
  api.post<JobMatchResponse>(`/admin/jobs/${id}/match`).then((r) => r.data);

export const batchMatchJobs = (ids?: number[]) =>
  api.post<JobBatchMatchResponse>('/admin/jobs/batch-match', ids ? { ids } : undefined).then((r) => r.data);

export const deleteJob = (id: number) =>
  api.delete<MessageResponse>(`/admin/jobs/${id}`).then((r) => r.data);

export const batchDeleteJobs = (ids: number[]) =>
  api.post<MessageResponse>('/admin/jobs/batch-delete', { ids }).then((r) => r.data);

export const crawlJobs = (keywords: string, city: string = '', platform: string = '51job', max_count: number = 5, sort: string = 'time', threshold: number = 0, auto_match: boolean = true) =>
  api.post<CrawlJobsResponse>('/admin/jobs/crawl', { keywords, city, platform, max_count, sort, auto_match }).then((r) => r.data);
