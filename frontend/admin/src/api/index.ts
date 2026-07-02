import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL ? import.meta.env.VITE_API_URL : '';

const api = axios.create({
  baseURL: API_BASE,
  timeout: 180000,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('admin_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('admin_token');
      window.location.href = '/login';
    }
    return Promise.reject(err);
  }
);

export default api;

export const setToken = (token: string) => {
  localStorage.setItem('admin_token', token);
};

export const getToken = () => localStorage.getItem('admin_token');

export const clearToken = () => {
  localStorage.removeItem('admin_token');
};

// Re-export from auth
export { getStoredRole, getStoredUserId } from './auth';
