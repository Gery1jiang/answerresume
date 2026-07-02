import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
}

interface AgentState {
  messages: ChatMessage[];
  isStreaming: boolean;
  sessionId: string;
  addMessage: (msg: ChatMessage) => void;
  appendToLast: (chunk: string) => void;
  setStreaming: (v: boolean) => void;
  setSessionId: (id: string) => void;
  clearMessages: () => void;
}

export const useAgentStore = create<AgentState>()(
  persist(
    (set, get) => ({
      messages: [],
      isStreaming: false,
      sessionId: 'admin_streamlit',

      addMessage: (msg) => set({ messages: [...get().messages, msg] }),

      appendToLast: (chunk) => {
        const msgs = [...get().messages];
        const last = msgs[msgs.length - 1];
        if (last && last.role === 'assistant') {
          msgs[msgs.length - 1] = { ...last, content: last.content + chunk };
          set({ messages: msgs });
        }
      },

      setStreaming: (v) => set({ isStreaming: v }),

      setSessionId: (id) => set({ sessionId: id }),

      clearMessages: () => set({ messages: [] }),
    }),
    {
      name: 'agent-messages',
      partialize: (state) => ({ messages: state.messages, sessionId: state.sessionId }),
    }
  )
);
