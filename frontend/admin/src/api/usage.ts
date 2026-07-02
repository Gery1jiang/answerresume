import api from './index';

export interface UsageStats {
  total_input_tokens: number;
  total_output_tokens: number;
  total_tokens: number;
  total_search_calls: number;
  total_api_calls: number;
}

export interface UserUsageItem extends UsageStats {
  user_id: string;
  username?: string;
}

export interface AllUsageResponse {
  users: UserUsageItem[];
  summary: UsageStats & { total_user_count: number };
}

export interface DailyUsageItem {
  date: string;
  input_tokens: number;
  output_tokens: number;
  search_calls: number;
}

export async function fetchMyUsage(period: string = 'all'): Promise<UsageStats> {
  const res = await api.get(`/api/usage/my?period=${period}`);
  return res.data;
}

export async function fetchAllUsage(period: string = 'all'): Promise<AllUsageResponse> {
  const res = await api.get(`/api/usage/all?period=${period}`);
  return res.data;
}

export async function fetchMyDailyUsage(days: number = 30): Promise<DailyUsageItem[]> {
  const res = await api.get(`/api/usage/my/daily?days=${days}`);
  return res.data;
}

export async function fetchAllDailyUsage(days: number = 30): Promise<DailyUsageItem[]> {
  const res = await api.get(`/api/usage/all/daily?days=${days}`);
  return res.data;
}
