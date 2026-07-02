import api, { getToken } from './index';
import type { AgentStep, AgentChatResponse } from '../types/api';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:51666';

export interface UploadResult {
  file_id: string;
  file_name: string;
  file_type: string;
  file_size: number;
}

export const agentUpload = async (file: File): Promise<UploadResult> => {
  const token = getToken();
  const formData = new FormData();
  formData.append('file', file);
  const res = await fetch(`${API_BASE}/admin/agent/upload`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: formData,
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || `Upload failed: ${res.status}`);
  }
  return res.json();
};

export const agentChat = async (message: string, sessionId = 'admin_streamlit', fileIds: string[] = []) => {
  const res = await api.post<AgentChatResponse>('/admin/agent/chat', {
    message,
    session_id: sessionId,
    file_ids: fileIds,
  });
  return res.data;
};

/**
 * SSE streaming agent chat.
 * POST /admin/agent/chat/stream, parse SSE events, invoke callbacks.
 * Returns an AbortController so the caller can cancel mid-stream.
 */
export interface FsmEvent {
  state: string;
  step: number;
  max_steps: number;
  tool?: string;
}

export function agentChatStream(
  message: string,
  callbacks: {
    onToolCall?: (tool: string, args: Record<string, any>, sensitive?: boolean, confirmId?: string) => void;
    onToolResult?: (tool: string, preview: string) => void;
    onText?: (text: string) => void;
    onStatus?: (msg: string) => void;
    onFsm?: (fsm: FsmEvent) => void;
    onDone?: (response: string, resumeId?: number | null, guideId?: number | null) => void;
    onError?: (err: string) => void;
    onDisconnect?: (msg: string) => void;
    onDagPlan?: (plan: { task_id: string; goal: string; layers: string[][] }) => void;
    onDagProgress?: (progress: { action_id?: string; tool?: string; status: string; layer?: number; error?: string }) => void;
  },
  sessionId = 'admin_streamlit',
  fileIds: string[] = [],
): AbortController {
  const controller = new AbortController();
  const token = getToken();
  let receivedDone = false;

  (async () => {
    try {
      const res = await fetch(`${API_BASE}/admin/agent/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ message, session_id: sessionId, file_ids: fileIds }),
        signal: controller.signal,
      });

      if (!res.ok) {
        callbacks.onError?.(`HTTP ${res.status}`);
        return;
      }

      const reader = res.body?.getReader();
      if (!reader) {
        callbacks.onError?.('No response body');
        return;
      }

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const event = JSON.parse(line.slice(6));
            switch (event.type) {
              case 'tool_call':
                callbacks.onToolCall?.(event.data.tool, event.data.args, event.data.sensitive, event.data.confirm_id);
                break;
              case 'tool_result':
                callbacks.onToolResult?.(event.data.tool, event.data.result_preview);
                break;
              case 'text':
                callbacks.onText?.(event.data.content);
                break;
              case 'status':
                callbacks.onStatus?.(event.data.message);
                break;
              case 'fsm':
                callbacks.onFsm?.(event.data);
                break;
              case 'done':
                receivedDone = true;
                callbacks.onDone?.(event.data.response, event.data.resume_id ?? null, event.data.guide_id ?? null);
                break;
              case 'error':
                callbacks.onError?.(event.data.message);
                break;
              case 'dag_plan':
                callbacks.onDagPlan?.(event.data);
                break;
              case 'dag_progress':
                callbacks.onDagProgress?.(event.data);
                break;
            }
          } catch {
            // skip unparseable
          }
        }
      }

      if (!receivedDone) {
        callbacks.onDisconnect?.('连接已断开，回复内容已保存，请刷新页面查看完整结果');
      }
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        callbacks.onError?.(err.message || 'Stream error');
      }
    }
  })();

  return controller;
}

export interface HistoryMessage {
  role: 'user' | 'assistant';
  content: string;
  resume_id?: number | null;
  guide_id?: number | null;
  created_at?: string;
}

export const getAgentHistory = async (sessionId = 'admin_streamlit'): Promise<HistoryMessage[]> => {
  try {
    const res = await api.get<{ messages: HistoryMessage[] }>('/admin/agent/history', {
      params: { session_id: sessionId },
    });
    return res.data.messages;
  } catch {
    return [];
  }
};

export const getAgentTaskStatus = async (sessionId = 'admin_streamlit') => {
  try {
    const res = await api.get<{
      status: string;
      response?: string;
      resume_id?: number;
      request?: string;
    }>('/admin/agent/task-status', {
      params: { session_id: sessionId },
    });
    return res.data;
  } catch {
    return null;
  }
};

export interface AgentEvent {
  type: string;
  data: Record<string, any>;
  sequence: number;
  created_at?: string;
}

export const getAgentEvents = async (sessionId = 'admin_streamlit'): Promise<AgentEvent[]> => {
  try {
    const res = await api.get<{ events: AgentEvent[] }>('/admin/agent/events', {
      params: { session_id: sessionId },
    });
    return res.data.events;
  } catch {
    return [];
  }
};

export const clearAgentHistory = async (sessionId = 'admin_streamlit') => {
  await api.post('/admin/agent/clear', { session_id: sessionId });
};

export const clearAllAgentHistory = async () => {
  await api.post('/admin/agent/clear-all');
};

export const cancelTask = async (sessionId = 'admin_streamlit') => {
  await api.post('/admin/agent/cancel', { session_id: sessionId });
};

export const confirmTool = async (confirmId: string, confirmed: boolean) => {
  const res = await api.post<{ status: string; confirmed: boolean }>('/admin/agent/confirm-tool', {
    confirm_id: confirmId,
    confirmed,
  });
  return res.data;
};
