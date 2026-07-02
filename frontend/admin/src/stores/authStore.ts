import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { login as apiLogin, register as apiRegister } from '../api/auth';
import type { LoginParams } from '../api/auth';

export interface AuthUser {
  access_token: string;
  role: string;
  user_id?: number;
  username?: string;
  display_name?: string;
}

interface AuthState {
  token: string | null;
  role: string | null;
  userId: number | null;
  username: string | null;
  displayName: string | null;
  login: (params: LoginParams) => Promise<AuthUser>;
  register: (params: { username: string; display_name?: string; email: string; password: string }) => Promise<AuthUser>;
  logout: () => void;
  isAuthenticated: () => boolean;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      role: null,
      userId: null,
      username: null,
      displayName: null,

      login: async (params) => {
        const res = await apiLogin(params);
        set({
          token: res.access_token,
          role: res.role || 'super_admin',
          userId: res.user_id ?? null,
          username: res.username ?? null,
          displayName: res.display_name ?? null,
        });
        return res;
      },

      register: async (params) => {
        const res = await apiRegister(params);
        set({
          token: res.access_token,
          role: res.role || 'user',
          userId: res.user_id ?? null,
          username: res.username ?? null,
          displayName: res.display_name ?? null,
        });
        return res;
      },

      logout: () => {
        localStorage.removeItem('admin_token');
        localStorage.removeItem('user_role');
        localStorage.removeItem('user_id');
        localStorage.removeItem('username');
        localStorage.removeItem('display_name');
        set({ token: null, role: null, userId: null, username: null, displayName: null });
      },

      isAuthenticated: () => !!get().token,
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        token: state.token,
        role: state.role,
        userId: state.userId,
        username: state.username,
        displayName: state.displayName,
      }),
    }
  )
);
