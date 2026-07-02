import api from './index';
import type { ApplicantProfileResponse, ApplicantProfileUpdateResponse } from '../types/api';

export type ApplicantProfile = ApplicantProfileResponse;

export const getApplicantProfile = () =>
  api.get<ApplicantProfileResponse>('/admin/applicant-profile').then((r) => r.data);

export const updateApplicantProfile = (data: Partial<ApplicantProfileResponse>) =>
  api.put<ApplicantProfileUpdateResponse>('/admin/applicant-profile', data).then((r) => r.data);
