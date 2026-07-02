import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getInterviewGuides,
  getInterviewGuide,
  createInterviewGuide,
  updateInterviewGuide,
  deleteInterviewGuide,
} from '../api/interviewGuide';
import type { InterviewGuideItem } from '../types/api';

export function useInterviewGuides(params?: { session_id?: string }) {
  return useQuery({
    queryKey: ['interviewGuides', params],
    queryFn: () => getInterviewGuides(params),
    staleTime: 30_000,
  });
}

export function useInterviewGuide(id: number | null) {
  return useQuery({
    queryKey: ['interviewGuide', id],
    queryFn: () => getInterviewGuide(id!),
    enabled: id !== null,
  });
}

export function useCreateInterviewGuide() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createInterviewGuide,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['interviewGuides'] }),
  });
}

export function useUpdateInterviewGuide() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...data }: Partial<InterviewGuideItem> & { id: number }) => updateInterviewGuide(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['interviewGuides'] });
      qc.invalidateQueries({ queryKey: ['interviewGuide'] });
    },
  });
}

export function useDeleteInterviewGuide() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => deleteInterviewGuide(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['interviewGuides'] }),
  });
}
