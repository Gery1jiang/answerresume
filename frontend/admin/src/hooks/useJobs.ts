import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getJobs, addJob, updateJob, deleteJob } from '../api/jobs';
import type { JobListResponse, JobItem } from '../types/api';

export function useJobs(params?: { status?: string; min_score?: number; keyword?: string }) {
  return useQuery<JobListResponse>({
    queryKey: ['jobs', params],
    queryFn: () => getJobs(params),
  });
}

export function useCreateJob() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: addJob,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['jobs'] }),
  });
}

export function useUpdateJob() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...data }: Partial<JobItem> & { id: number }) => updateJob(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['jobs'] }),
  });
}

export function useDeleteJob() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => deleteJob(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['jobs'] }),
  });
}
