import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getResumes, deleteResume } from '../api/resume';

export function useResumes(params?: { page?: number; page_size?: number }) {
  return useQuery({
    queryKey: ['resumes', params],
    queryFn: () => getResumes(params),
    staleTime: 30_000,
  });
}

export function useDeleteResume() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => deleteResume(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['resumes'] }),
  });
}
