import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getKnowledge, addKnowledgeCategory, deleteKnowledgeItem, clearKnowledge, updateKnowledgeItem } from '../api/knowledge';
import type { KnowledgeCategory } from '../types/api';

export function useKnowledge() {
  return useQuery({
    queryKey: ['knowledge'],
    queryFn: () => getKnowledge(),
    staleTime: 30_000,
  });
}

export function useAddCategory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { category: string; content: string }) => addKnowledgeCategory(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['knowledge'] }),
  });
}

export function useDeleteKnowledgeItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ category, item }: { category: string; item: string }) => deleteKnowledgeItem(category, item),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['knowledge'] }),
  });
}

export function useUpdateKnowledgeItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ category, item, content }: { category: string; item: string; content: string }) =>
      updateKnowledgeItem(category, item, content),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['knowledge'] }),
  });
}

export function useClearKnowledge() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => clearKnowledge(),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['knowledge'] }),
  });
}
