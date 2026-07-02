import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getStats, getQuestionStats, getSessionConversations, clearStats } from '../api/stats';
import { getFaqData, saveFaq } from '../api/knowledge';

export function useStats() {
  return useQuery({
    queryKey: ['stats'],
    queryFn: () => getStats(),
    retry: false,
    staleTime: 30_000,
  });
}

export function useQuestionStats() {
  return useQuery({
    queryKey: ['questionStats'],
    queryFn: () => getQuestionStats().catch(() => []),
    retry: false,
    staleTime: 30_000,
  });
}

export function useSessionConversations(sessionId: string | null) {
  return useQuery({
    queryKey: ['sessionConversations', sessionId],
    queryFn: () => getSessionConversations(sessionId!),
    enabled: !!sessionId,
  });
}

export function useClearStats() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: clearStats,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['stats'] });
      qc.invalidateQueries({ queryKey: ['questionStats'] });
    },
  });
}

export function useFaqData() {
  return useQuery({
    queryKey: ['faq'],
    queryFn: () => getFaqData(),
    staleTime: 60_000,
  });
}

export function useSaveFaq() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (list: { question: string; answer: string }[]) => saveFaq(list),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['faq'] }),
  });
}
