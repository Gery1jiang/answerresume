import api, { setToken } from './index';
import type { LoginResponse, AuthResponse, UserInfoResponse } from '../types/api';

export interface LoginParams {
  username: string;
  password: string;
}

export const login = async (params: LoginParams) => {
  const res = await api.post<LoginResponse>('/admin/login', params);
  setToken(res.data.access_token);
  localStorage.setItem('user_role', res.data.role || 'super_admin');
  if (res.data.user_id !== undefined) localStorage.setItem('user_id', String(res.data.user_id));
  if (res.data.username !== undefined) localStorage.setItem('username', String(res.data.username));
  if (res.data.display_name !== undefined) localStorage.setItem('display_name', String(res.data.display_name));
  return res.data;
};

export const register = async (params: { username: string; display_name?: string; email: string; password: string }) => {
  const res = await api.post<LoginResponse>('/admin/register', params);
  setToken(res.data.access_token);
  localStorage.setItem('user_role', res.data.role || 'user');
  if (res.data.user_id !== undefined) localStorage.setItem('user_id', String(res.data.user_id));
  if (res.data.username !== undefined) localStorage.setItem('username', String(res.data.username));
  if (res.data.display_name !== undefined) localStorage.setItem('display_name', String(res.data.display_name));
  return res.data;
};

export const getMe = async () => {
  const res = await api.get<UserInfoResponse>('/api/auth/me');
  return res.data;
};

export const getStoredRole = (): string | null => {
  return localStorage.getItem('user_role');
};

export const getStoredUserId = (): string | null => {
  return localStorage.getItem('user_id');
};
