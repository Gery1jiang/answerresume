import { useState, useRef, useEffect, Fragment } from 'react';
import { Input, Button, Card, Typography, Space, Tag, Modal, Select, message, Spin, Upload } from 'antd';
import { DeleteOutlined, FileTextOutlined, LoadingOutlined, UploadOutlined, PaperClipOutlined, FileImageOutlined, DownloadOutlined, AudioOutlined } from '@ant-design/icons';
import { agentChat, agentChatStream, clearAgentHistory, agentUpload, getAgentHistory, getAgentTaskStatus, getAgentEvents, confirmTool, cancelTask } from '../../api/agent';
import type { UploadResult, HistoryMessage, AgentEvent, FsmEvent } from '../../api/agent';
import { getResume, getTemplates, getResumeViewUrl, getResumeDownloadUrl } from '../../api/resume';
import type { ResumeTemplate } from '../../api/resume';
import { getInterviewGuide, previewReport, downloadReport } from '../../api/interviewGuide';
import api from '../../api';

const { Text } = Typography;

interface Message {
  role: 'user' | 'assistant';
  content: string;
  resumeId?: number;
  guideId?: number;
  streaming?: boolean;
  fileIds?: string[];
  fileNames?: string[];
}

const STORAGE_KEY = 'agent_messages';

function loadMessages(): Message[] {
  try {
    const msgs: Message[] = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
    return msgs;
  }
  catch { return []; }
}

function saveMessages(msgs: Message[]) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(msgs)); }
  catch {}
}

const WELCOME_MSG: Message = {
  role: 'assistant',
  content: 'Agent 能做什么？\n\n• 面试记录 — 粘贴截图给我，我能自动识别并创建面试记录\n• 新增/克隆 - 支持新增一面，或增加二面/三面等后续轮次\n• 生成简历 — 说「用知识库生成简历」或自己提供信息\n• 查询统计 — 说「查一下最近7天的访问统计」',
};

function initMessages(): Message[] {
  const saved = loadMessages();
  return saved.length > 0 ? saved : [WELCOME_MSG];
}

export default function AgentPage() {
  const [messages, setMessages] = useState<Message[]>(initMessages);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(true); // true until recover() confirms no pending task
  const [toolCalls, setToolCalls] = useState<string[]>([]);
  const [fsmState, setFsmState] = useState<FsmEvent | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const [uploading, setUploading] = useState(false);
  const [pendingFiles, setPendingFiles] = useState<UploadResult[]>([]);
  const uploadCountRef = useRef(0);

  const [templates, setTemplates] = useState<ResumeTemplate[]>([]);

  // resume preview state (matches ResumePage pattern)
  const [resumePreviewId, setResumePreviewId] = useState<number | null>(null);
  const [resumePreviewHtml, setResumePreviewHtml] = useState('');
  const [resumePreviewTemplate, setResumePreviewTemplate] = useState('modern');

  // report preview state (matches InterviewGuidePage pattern)
  const [reportPreviewVisible, setReportPreviewVisible] = useState(false);
  const [reportPreviewHtml, setReportPreviewHtml] = useState('');
  const [reportPreviewLoading, setReportPreviewLoading] = useState(false);
  const [reportPreviewGuideId, setReportPreviewGuideId] = useState<number | null>(null);
  const [reportPreviewCompanyName, setReportPreviewCompanyName] = useState('');

  // HITL confirmation state
  const [pendingConfirm, setPendingConfirm] = useState<{ confirmId: string; tool: string; args: Record<string, any> } | null>(null);

  // DAG decomposition state
  const [dagSteps, setDagSteps] = useState<{ action_id: string; tool: string; status: string }[]>([]);
  const [dagGoal, setDagGoal] = useState('');
  const [statusMessage, setStatusMessage] = useState('');
  const [listening, setListening] = useState(false);
  const recognitionRef = useRef<any>(null);
  useEffect(() => {
    if (toolCalls.length === 0) setStatusMessage('');
  }, [toolCalls]);

  // Long conversation pagination
  const PAGE_SIZE = 30;
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);
  const displayMessages = messages.filter(m => !(m.streaming && !m.content));
  const totalMessages = displayMessages.length;
  const showLoadMore = totalMessages > visibleCount;

  const isFirstRender = useRef(true);
  useEffect(() => {
    saveMessages(messages);
    if (isFirstRender.current) {
      isFirstRender.current = false;
      bottomRef.current?.scrollIntoView();
    } else {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages]);

  // On mount: sync state from backend
  useEffect(() => {
    let cancelled = false;
    const recover = async () => {
      const task = await getAgentTaskStatus().catch(() => null);
      if (cancelled || !task || task.status === 'none') {
        if (!cancelled) setLoading(false);
        return;
      }

      if (task.status === 'cancelled') {
        setMessages([{ ...WELCOME_MSG }]);
        setLoading(false);
        setToolCalls([]);
        setFsmState(null);
        return;
      }

      if (task.status === 'completed' || task.status === 'failed') {
        const serverMsgs = await getAgentHistory().catch(() => [] as HistoryMessage[]);
        if (cancelled) return;
        const localMsgs = loadMessages();
        const localGuideMap: Record<number, true> = {};
        localMsgs.forEach(m => { if (m.guideId) localGuideMap[m.guideId] = true; });
        const history: Message[] = [{ ...WELCOME_MSG }];
        for (const sm of serverMsgs) {
          if (sm.role === 'user') {
            const fileMatches = [...sm.content.matchAll(/\[文件:\s*([^\]]+)\]/g)];
            const fileIds = fileMatches.map(m => m[1]);
            const fileNames = fileMatches.map(m => m[1]);
            history.push({ role: 'user', content: sm.content, fileIds, fileNames });
          } else if (sm.role === 'assistant' && sm.content) {
            const guideId = sm.guide_id ?? undefined;
            const restoredMsg: Message = { role: 'assistant', content: sm.content, resumeId: sm.resume_id ?? undefined };
            if (guideId) {
              restoredMsg.guideId = guideId;
            } else {
              const localMatch = localMsgs.find(m => m.role === 'assistant' && m.content === sm.content && m.guideId);
              if (localMatch) restoredMsg.guideId = localMatch.guideId;
            }
            history.push(restoredMsg);
          }
        }
    if (task.status === 'failed') {
      history.push({ role: 'assistant', content: `❌ ${task.response || '任务失败'}` });
    }
    setMessages(history);
    setLoading(false);
    setToolCalls([]);
    setFsmState(null);
    return;
      }

      // Task is still running — show recovery state immediately
      setLoading(true);
      setFsmState({ state: 'init', step: 1, max_steps: 15 });
      // Keep all messages, mark last assistant as streaming for updates
      setMessages(prev => {
        const next = [...prev];
        const last = next[next.length - 1];
        if (last?.role === 'assistant' && last.streaming) {
          // already streaming, keep as-is
        } else if (last?.role === 'assistant') {
          next[next.length - 1] = { ...last, streaming: true, content: '' };
        } else {
          next.push({ role: 'assistant', content: '', streaming: true });
        }
        return next;
      });

      let lastSeq = 0;
      while (!cancelled) {
        await new Promise(r => setTimeout(r, 2000));
        if (cancelled) return;
        const cur = await getAgentTaskStatus().catch(() => null);
        if (cancelled || !cur || cur.status === 'none') { setLoading(false); return; }
        if (cur.status === 'cancelled') {
          setMessages(prev => [...prev, { role: 'assistant', content: '(任务已取消)' }]);
          setLoading(false);
          setToolCalls([]);
          setFsmState(null);
          return;
        }

        // Only refresh tool calls, don't append text (causes dupes)
        const events = await getAgentEvents().catch(() => [] as AgentEvent[]);
        if (cancelled) return;
        for (const evt of events.slice(lastSeq)) {
          if (evt.type === 'tool_call') {
            setToolCalls(prev => prev.includes(evt.data.tool) ? prev : [...prev, evt.data.tool]);
            setFsmState({ state: 'tool_call', step: 1, max_steps: 15 });
          }
        }
        lastSeq = events.length;

        if (cur.status === 'completed' || cur.status === 'failed') {
          const serverMsgs = await getAgentHistory().catch(() => [] as HistoryMessage[]);
          if (cancelled) return;
          const history: Message[] = [{ ...WELCOME_MSG }];
          for (const sm of serverMsgs) {
            if (sm.role === 'user') {
              const fileMatches = [...sm.content.matchAll(/\[文件:\s*([^\]]+)\]/g)];
              history.push({ role: 'user', content: sm.content, fileIds: fileMatches.map(m => m[1]), fileNames: fileMatches.map(m => m[1]) });
            } else if (sm.role === 'assistant' && sm.content) {
              const msg: Message = { role: 'assistant', content: sm.content, resumeId: sm.resume_id ?? undefined };
              if (sm.guide_id) msg.guideId = sm.guide_id;
              history.push(msg);
            }
          }
          if (cur.status === 'failed') history.push({ role: 'assistant', content: `❌ ${cur.response || '任务失败'}` });
          setMessages(history);
          setLoading(false);
          setToolCalls([]);
          setFsmState(null);
          return;
        }
      }
    };

    recover();
    return () => { cancelled = true; };
  }, []);

  const reconnectRef = useRef<(() => void) | null>(null);
  reconnectRef.current = () => {
    setLoading(true);
    // Re-enable streaming on last assistant message
    setMessages(prev => {
      const next = [...prev];
      const last = next[next.length - 1];
      if (last?.role === 'assistant' && !last.streaming) {
        next[next.length - 1] = { ...last, streaming: true };
      }
      return next;
    });
    let cancelled = false;
    const timer = setTimeout(() => { cancelled = true; }, 300000);
    (async () => {
      while (!cancelled) {
        await new Promise(r => setTimeout(r, 2000));
        const cur = await getAgentTaskStatus().catch(() => null);
        if (!cur || cur.status === 'none') { cancelled = true; break; }
        if (cur.status === 'cancelled') { clearTimeout(timer); setLoading(false); return; }
        if (cur.status === 'completed' || cur.status === 'failed') {
          const serverMsgs = await getAgentHistory().catch(() => [] as HistoryMessage[]);
          const history: Message[] = [{ ...WELCOME_MSG }];
          for (const sm of serverMsgs) {
            if (sm.role === 'user') {
              const fileMatches = [...sm.content.matchAll(/\[文件:\s*([^\]]+)\]/g)];
              history.push({ role: 'user', content: sm.content, fileIds: fileMatches.map(m => m[1]), fileNames: fileMatches.map(m => m[1]) });
            } else if (sm.role === 'assistant' && sm.content) {
              const msg: Message = { role: 'assistant', content: sm.content, resumeId: sm.resume_id ?? undefined };
              if (sm.guide_id) msg.guideId = sm.guide_id;
              history.push(msg);
            }
          }
          if (cur.status === 'failed') history.push({ role: 'assistant', content: `❌ ${cur.response || '任务失败'}` });
          setMessages(history);
          setLoading(false);
          setToolCalls([]);
          setFsmState(null);
          clearTimeout(timer);
          return;
        }
      }
      clearTimeout(timer);
      setLoading(false);
    })();
  };

  useEffect(() => {
    getTemplates().then(r => setTemplates(r)).catch(() => {});
  }, []);

  const openResumePreview = async (id: number) => {
    setResumePreviewId(id);
    try {
      const detail = await getResume(id);
      const tmpl = JSON.parse(detail.content || '{}')._template || 'modern';
      setResumePreviewTemplate(tmpl);
      const url = getResumeViewUrl(id, tmpl);
      const res = await api.get(url, { responseType: 'text' });
      setResumePreviewHtml(res.data);
    } catch { message.error('加载预览失败'); }
  };

  const handleResumeTemplateChange = async (id: number, tmpl: string) => {
    setResumePreviewTemplate(tmpl);
    try {
      const url = getResumeViewUrl(id, tmpl);
      const res = await api.get(url, { responseType: 'text' });
      setResumePreviewHtml(res.data);
    } catch { message.error('加载预览失败'); }
  };

  const openReportPreview = async (id: number) => {
    setReportPreviewGuideId(id);
    setReportPreviewLoading(true);
    setReportPreviewVisible(true);
    try {
      const guide = await getInterviewGuide(id);
      setReportPreviewCompanyName(guide.company_name || '');
      const html = await previewReport(id);
      setReportPreviewHtml(html);
    } catch {
      message.error('加载预览失败');
      setReportPreviewVisible(false);
    } finally {
      setReportPreviewLoading(false);
    }
  };

  const handleReportDownload = async () => {
    if (reportPreviewGuideId === null) return;
    try {
      const blob = await downloadReport(reportPreviewGuideId);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `面试报告_${reportPreviewCompanyName || reportPreviewGuideId}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch {
      message.error('下载失败');
    }
  };

  const handleSend = () => {
    const text = input.trim();
    if ((!text && pendingFiles.length === 0) || loading) return;

    const fileIds = pendingFiles.map(f => f.file_id);
    const fileNames = pendingFiles.map(f => f.file_name);
    const displayText = text || `(上传了 ${fileNames.length} 个文件)`;

    setInput('');
    setPendingFiles([]);

    const userMsg: Message = { role: 'user', content: displayText, fileIds, fileNames };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);
    setToolCalls([]);
    setVisibleCount(PAGE_SIZE);

    // placeholder message that will be filled by streaming
    const assistMsg: Message = { role: 'assistant', content: '', streaming: true };
    setMessages((prev) => [...prev, assistMsg]);

    let finalResumeId: number | undefined;

    abortRef.current = agentChatStream(text || '请解析上传的文件', {
      onFsm: (fsm) => {
        setFsmState(fsm);
      },
      onStatus: (msg) => {
        setStatusMessage(msg);
      },
      onToolCall: (tool, args, sensitive, confirmId) => {
        setToolCalls((prev) => [...prev, sensitive ? `⚠️ ${tool}` : tool]);
        if (sensitive && confirmId) {
          setPendingConfirm({ confirmId, tool, args });
        }
      },
      onText: (fragment) => {
        setMessages((prev) => {
          const next = [...prev];
          const last = next[next.length - 1];
          if (last && last.streaming) {
            next[next.length - 1] = { ...last, content: last.content + fragment };
          }
          return next;
        });
      },
      onDone: (response, resumeId, guideId) => {
        const finalGuideId = guideId ?? undefined;
        setMessages((prev) => {
          const next = [...prev];
          const last = next[next.length - 1];
          if (last && last.streaming) {
            next[next.length - 1] = { role: 'assistant', content: response, resumeId: resumeId ?? undefined, guideId: finalGuideId };
          } else {
            next.push({ role: 'assistant', content: response, resumeId: resumeId ?? undefined, guideId: finalGuideId });
          }
          return next;
        });
        setLoading(false);
        setToolCalls([]);
        setFsmState(null);
        setDagSteps([]);
        setDagGoal('');
        abortRef.current = null;
      },
      onError: (err) => {
        setMessages((prev) => {
          const next = [...prev];
          const last = next[next.length - 1];
          if (last && last.streaming) {
            next[next.length - 1] = { role: 'assistant', content: `❌ ${err}` };
          } else {
            next.push({ role: 'assistant', content: `❌ ${err}` });
          }
          return next;
        });
        setLoading(false);
        setToolCalls([]);
        setFsmState(null);
        setDagSteps([]);
        setDagGoal('');
        abortRef.current = null;
      },
      onDagPlan: (plan) => {
        setDagGoal(plan.goal);
        const steps = plan.layers.flat().map((id) => ({ action_id: id, tool: id, status: 'pending' }));
        setDagSteps(steps);
      },
      onDagProgress: (progress) => {
        if (progress.action_id) {
          setDagSteps((prev) =>
            prev.map((s) =>
              s.action_id === progress.action_id ? { ...s, status: progress.status } : s
            )
          );
        }
      },
      onDisconnect: (msg) => {
        setMessages((prev) => {
          const next = [...prev];
          const last = next[next.length - 1];
          if (last && last.streaming) {
            next[next.length - 1] = { ...last, content: last.content + `\n\n_${msg}_` };
          }
          return next;
        });
        setLoading(false);
        // Auto-reconnect: poll backend for events until task completes
        reconnectRef.current?.();
      },
    }, undefined, fileIds);
  };

  const handleUpload = async (file: File) => {
    if (uploading) return false;
    try {
      setUploading(true);
      const result = await agentUpload(file);
      setPendingFiles((prev) => [...prev, result]);
      message.success(`${file.name} 上传成功`);
    } catch (err: any) {
      message.error(err.message || '上传失败');
    } finally {
      setUploading(false);
    }
    return false;
  };

  const handleRemoveFile = (fileId: string) => {
    setPendingFiles((prev) => prev.filter(f => f.file_id !== fileId));
  };

  // Upload images collected from clipboard
  const uploadClipboardImages = async (imageFiles: File[]) => {
    for (const file of imageFiles) {
      uploadCountRef.current += 1;
      setUploading(true);
      try {
        const result = await agentUpload(file);
        setPendingFiles((prev) => [...prev, result]);
        message.success(`截图 ${file.name} 已上传，按回车发送`);
      } catch (err: any) {
        message.error(`截图上传失败: ${err.message || err}`);
      } finally {
        uploadCountRef.current -= 1;
        if (uploadCountRef.current <= 0) {
          uploadCountRef.current = 0;
          setUploading(false);
        }
      }
    }
  };

  // Collect image files from clipboard DataTransfer
  const getClipboardImages = (dt: DataTransfer): File[] => {
    const files: File[] = [];
    for (let i = 0; i < dt.files.length; i++) {
      const f = dt.files[i];
      if (f.type.startsWith('image/') && !files.some(x => x.name === f.name && x.size === f.size)) {
        files.push(f);
      }
    }
    for (let i = 0; i < dt.items.length; i++) {
      const item = dt.items[i];
      if (item.kind === 'file' && item.type.startsWith('image/')) {
        const f = item.getAsFile();
        if (f && !files.some(x => x.name === f!.name && x.size === f!.size)) {
          files.push(f);
        }
      }
    }
    return files;
  };

  // Keep a ref pointing to the latest uploadClipboardImages so the
  // capture-phase paste listener never calls a stale closure.
  const uploadRef = useRef(uploadClipboardImages);
  useEffect(() => { uploadRef.current = uploadClipboardImages; });

  useEffect(() => {
    // Try reading image from the async Clipboard API (handles right-click → Paste
    // into a text input where e.clipboardData may not expose image data).
    async function readClipboardAPI(): Promise<File[]> {
      try {
        if (!navigator.clipboard || typeof navigator.clipboard.read !== 'function') return [];
        const items = await navigator.clipboard.read();
        const files: File[] = [];
        for (const item of items) {
          for (const type of item.types) {
            if (type.startsWith('image/')) {
              const blob = await item.getType(type);
              const ext = type.split('/')[1] || 'png';
              files.push(new File([blob], `clipboard.${ext}`, { type }));
            }
          }
        }
        return files;
      } catch {
        return [];
      }
    }

    const handler = (e: ClipboardEvent) => {
      if (!(e.target as HTMLElement).closest('.agent-input-area')) return;
      const dt = e.clipboardData;
      if (!dt) return;

      const images = getClipboardImages(dt);
      if (images.length > 0) {
        e.preventDefault();
        e.stopPropagation();
        uploadRef.current(images);
        return;
      }

      // Fallback: right-click → Paste into a text input may not populate
      // e.clipboardData with images; try the async Clipboard API instead.
      readClipboardAPI().then((files) => {
        if (files.length > 0) {
          uploadRef.current(files);
          // Since we can't preventDefault retroactively, the browser may
          // also try to paste the image as text (harmless no-op for <input type=text>).
        }
      });
    };

    window.addEventListener('paste', handler, true);
    return () => window.removeEventListener('paste', handler, true);
  }, []);

  const handleConfirmTool = async () => {
    if (!pendingConfirm) return;
    const id = pendingConfirm.confirmId;
    setPendingConfirm(null);
    try {
      await confirmTool(id, true);
      message.info('已确认，继续执行');
    } catch (e: any) {
      message.error('确认失败: ' + (e?.message || '未知错误'));
    }
  };

  const handleRejectTool = async () => {
    if (!pendingConfirm) return;
    const id = pendingConfirm.confirmId;
    setPendingConfirm(null);
    try {
      await confirmTool(id, false);
      message.info('已取消敏感操作');
    } catch (e: any) {
      message.error('取消失败: ' + (e?.message || '未知错误'));
    }
  };

  const handleCancel = async () => {
    abortRef.current?.abort();
    await cancelTask().catch(() => {});
    setLoading(false);
    setToolCalls([]);
    setFsmState(null);
    setMessages((prev) => {
      const next = prev.filter(m => !((m as any).streaming));
      next.push({ role: 'assistant', content: '(已取消)' });
      return next;
    });
    abortRef.current = null;
  };

  const toggleVoice = () => {
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SR) { message.warning('当前浏览器不支持语音识别'); return; }
    if (listening) {
      recognitionRef.current?.stop();
      setListening(false);
      return;
    }
    const recognition = new SR();
    recognition.lang = 'zh-CN';
    recognition.interimResults = false;
    recognition.continuous = true;
    recognition.onresult = (e: SpeechRecognitionEvent) => {
      let text = '';
      for (let i = e.resultIndex; i < e.results.length; i++) {
        text += e.results[i][0].transcript;
      }
      if (text) setInput(prev => prev + text);
    };
    recognition.onerror = () => setListening(false);
    recognition.onend = () => setListening(false);
    recognition.start();
    recognitionRef.current = recognition;
    setListening(true);
  };

  const handleClear = async () => {
    abortRef.current?.abort();
    await clearAgentHistory();
    setMessages([WELCOME_MSG]);
    localStorage.removeItem(STORAGE_KEY);
    setToolCalls([]);
    setLoading(false);
    setVisibleCount(PAGE_SIZE);
    abortRef.current = null;
  };

  return (
    <Fragment>
      <div style={{ height: 'calc(100vh - 120px)', display: 'flex', flexDirection: 'column' }}>
        <div className="chat-scroll" style={{ flex: 1, overflow: 'auto', scrollbarWidth: 'thin', scrollbarColor: 'var(--admin-border) transparent' }}>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <div style={{ maxWidth: '53%', width: '100%', padding: '0 12px 16px' }}>
              {showLoadMore && (
                <div style={{ textAlign: 'center', marginBottom: 16 }}>
                  <Button size="small" type="link"
                    onClick={() => setVisibleCount(prev => Math.min(prev + PAGE_SIZE, totalMessages))}>
                    加载更早的消息 ({totalMessages - visibleCount} 条隐藏)
                  </Button>
                </div>
              )}
              {displayMessages.slice(-visibleCount).map((msg, i) => {
                const globalIdx = totalMessages - visibleCount + i;
                return (
                <div key={globalIdx} className={msg.role === 'user' ? 'message-user' : 'message-assistant'}
                  style={{ display: 'flex', flexDirection: 'column', alignItems: msg.role === 'user' ? 'flex-end' : 'flex-start', marginBottom: 16 }}>
                  <div style={{ fontSize: 12, color: 'var(--admin-text-muted)', marginBottom: 4, padding: '0 12px' }}>
                    {msg.role === 'user' ? '👤 我' : '🤖 Agent'}
                  </div>
                  <Card size="small"
                    style={{ maxWidth: '75%', background: msg.role === 'user' ? 'var(--admin-chat-user-bg)' : 'var(--admin-chat-assistant-bg)', color: msg.role === 'user' ? '#fff' : 'var(--admin-text)', border: msg.role === 'user' ? 'none' : '1px solid var(--admin-border)' }}>
                    <div style={{ whiteSpace: 'pre-wrap' }}>{(msg.content.replace(/\[文件:\s*[^\]]+\]\n?/g, '').trim() || (msg.fileNames?.length ? `(上传了 ${msg.fileNames.length} 个文件)` : msg.content))}</div>
                    {msg.role === 'user' && msg.fileNames && msg.fileNames.length > 0 && (
                      <div style={{ marginTop: 6, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                        {msg.fileNames.map((fn, fi) => (
                          <Tag key={fi} icon={<FileImageOutlined />} color="processing" style={{ fontSize: 11 }}>{fn}</Tag>
                        ))}
                      </div>
                    )}
                    {msg.role === 'assistant' && (msg.resumeId || msg.guideId) && (
                      <div style={{ marginTop: 8, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                        {msg.resumeId && (
                          <Card hoverable size="small" onClick={() => openResumePreview(msg.resumeId!)}
                            style={{ background: 'var(--admin-bg-card)', cursor: 'pointer', border: '1px solid var(--admin-border)' }}>
                            <Space>
                              <FileTextOutlined style={{ fontSize: 20, color: 'var(--admin-accent)' }} />
                              <div>
                                <div style={{ fontWeight: 600, color: 'var(--admin-text)' }}>简历</div>
                                <div style={{ fontSize: 12, color: 'var(--admin-text-muted)' }}>点击预览</div>
                              </div>
                            </Space>
                          </Card>
                        )}
                        {msg.guideId && (
                          <Card hoverable size="small" onClick={() => openReportPreview(msg.guideId!)}
                            style={{ background: 'var(--admin-bg-card)', cursor: 'pointer', border: '1px solid var(--admin-border)' }}>
                            <Space>
                              <FileTextOutlined style={{ fontSize: 20, color: 'var(--admin-accent)' }} />
                              <div>
                                <div style={{ fontWeight: 600, color: 'var(--admin-text)' }}>面试报告</div>
                                <div style={{ fontSize: 12, color: 'var(--admin-text-muted)' }}>点击预览</div>
                              </div>
                            </Space>
                          </Card>
                        )}
                      </div>
                    )}
                  </Card>
                </div>
                );
              })}
              {loading && (
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', marginBottom: 16 }}>
                  <div style={{ fontSize: 12, color: 'var(--admin-text-muted)', marginBottom: 4, padding: '0 12px' }}>🤖 Agent</div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, background: 'var(--admin-bg-tertiary)', border: '1px solid var(--admin-border)', borderRadius: 12, padding: '8px 14px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <Spin indicator={<LoadingOutlined style={{ fontSize: 16 }} />} />
                        {fsmState ? (
                          <span style={{ color: 'var(--admin-text-muted)', fontSize: 13 }}>
                            {fsmState.state === 'init' && '准备中'}
                            {fsmState.state === 'agent_think' && (fsmState.step > 1 ? `思考中 (第${fsmState.step}步)` : '思考中')}
                            {fsmState.state === 'tool_call' && `调用工具中`}
                            {fsmState.state === 'finish' && '生成回答'}
                            {fsmState.state === 'error' && '处理出错'}
                          </span>
                        ) : null}
                      </div>
                      {toolCalls.length > 0 && (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 3, marginTop: 6, paddingTop: 6, borderTop: '1px solid var(--admin-border)' }}>
                          <div style={{ fontSize: 11, color: 'var(--admin-text-muted)', marginBottom: 2 }}>工具调用步骤</div>
                          {toolCalls.map((tool, i) => {
                            const isSensitive = tool.startsWith('⚠️ ');
                            const toolName = isSensitive ? tool.slice(2) : tool;
                            const category = toolName.includes('resume') ? '简历' :
                              toolName.includes('interview') || toolName.includes('create_interview') ? '面试' :
                              toolName.includes('match') ? '匹配' :
                              toolName.includes('crawl') ? '爬取' :
                              toolName.includes('search') ? '搜索' :
                              toolName.includes('knowledge') ? '知识库' :
                              toolName.includes('parse') || toolName.includes('ocr') ? '文件' :
                              toolName.includes('query') ? '统计' : '工具';
                            return (
                              <div key={i} style={{
                                display: 'flex', alignItems: 'center', gap: 6,
                                fontSize: 12, color: 'var(--admin-text-muted)',
                                padding: '4px 6px', borderRadius: 6,
                                background: isSensitive ? 'rgba(255, 77, 79, 0.06)' : 'transparent',
                              }}>
                                <span style={{
                                  width: 18, height: 18, borderRadius: '50%',
                                  background: isSensitive ? '#ff4d4f' : 'var(--admin-accent)',
                                  color: '#fff', display: 'inline-flex', alignItems: 'center',
                                  justifyContent: 'center', fontSize: 10, fontWeight: 600, flexShrink: 0,
                                }}>{i + 1}</span>
                                <span style={{
                                  fontSize: 10, fontWeight: 500, color: isSensitive ? '#ff4d4f' : '#888',
                                  background: isSensitive ? 'rgba(255,77,79,0.1)' : 'var(--admin-bg)',
                                  borderRadius: 4, padding: '0 5px', lineHeight: '18px',
                                  flexShrink: 0,
                                }}>{category}</span>
                                <span style={{ fontFamily: 'monospace', fontSize: 12 }}>{toolName.replace(/_tool$/, '')}</span>
                                {isSensitive && <span style={{ fontSize: 10, color: '#ff4d4f' }}>⚠️</span>}
                              </div>
                            );
                          })}
                          {statusMessage && (
                            <div style={{ fontSize: 11, color: '#888', padding: '2px 6px', marginTop: 2 }}>
                              {statusMessage}
                            </div>
                          )}
                        </div>
                      )}
                      {dagSteps.length > 0 && (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 3, marginTop: 6, paddingTop: 6, borderTop: '1px solid var(--admin-border)' }}>
                          <div style={{ fontSize: 11, color: 'var(--admin-text-muted)', marginBottom: 2 }}>
                            任务拆解步骤 {dagGoal ? `- ${dagGoal}` : ''}
                          </div>
                          {dagSteps.map((step, i) => {
                            const statusIcon = step.status === 'running' ? '⏳' : step.status === 'completed' || step.status === 'cached' ? '✅' : step.status === 'failed' ? '❌' : '⏸️';
                            const statusColor = step.status === 'running' ? '#1890ff' : step.status === 'completed' || step.status === 'cached' ? '#52c41a' : step.status === 'failed' ? '#ff4d4f' : 'var(--admin-text-muted)';
                            return (
                              <div key={step.action_id} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: statusColor, padding: '4px 6px', borderRadius: 6 }}>
                                <span style={{ fontSize: 14 }}>{statusIcon}</span>
                                <span style={{ fontFamily: 'monospace', fontSize: 12 }}>{step.tool}</span>
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                </div>
              )}
              <div ref={bottomRef} />
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', justifyContent: 'center', flexShrink: 0 }}>
          <div style={{ maxWidth: '53%', width: '100%', padding: '0 12px' }}>
            {pendingFiles.length > 0 && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, padding: '8px 0', borderTop: '1px solid var(--admin-border)' }}>
                {pendingFiles.map((f) => (
                  <Tag key={f.file_id} closable onClose={() => handleRemoveFile(f.file_id)}
                    icon={<FileImageOutlined />} color="processing" style={{ fontSize: 11, margin: 0 }}>
                    {f.file_name}
                  </Tag>
                ))}
              </div>
            )}
            <div className="agent-input-area" style={{ display: 'flex', gap: 8, borderTop: pendingFiles.length > 0 ? 'none' : '1px solid var(--admin-border)', padding: '12px 0' }}>
              <Upload beforeUpload={handleUpload} showUploadList={false} accept=".png,.jpg,.jpeg,.bmp,.tiff,.pdf,.docx,.doc,.md,.markdown,.pptx,.xlsx,.html,.htm" disabled={loading}>
                <Button icon={<UploadOutlined />} loading={uploading} disabled={loading}
                  style={{ borderRadius: 20 }} />
              </Upload>
              <Input value={input} onChange={(e) => setInput(e.target.value)} onPressEnter={handleSend}
                placeholder={pendingFiles.length > 0 ? "输入对上传文件的指令（可选）..." : "输入你的指令（支持粘贴截图）..."}
                size="large" variant="outlined" style={{ borderRadius: 20 }} disabled={loading}
                suffix={
                  <AudioOutlined onClick={toggleVoice}
                    style={{ fontSize: 18, cursor: 'pointer', color: listening ? '#ff4d4f' : 'var(--admin-text-muted)' }} />
                } />
              {loading ? (
                <Button danger onClick={handleCancel}
                  style={{ borderRadius: 20 }}>取消</Button>
              ) : (
                <Button icon={<DeleteOutlined />} onClick={handleClear}
                  style={{ borderRadius: 20, color: 'var(--admin-text-secondary)' }}>清空</Button>
              )}
            </div>
          </div>
        </div>
      </div>
      <Modal title="⚠️ 确认高危操作" open={!!pendingConfirm}
        onOk={handleConfirmTool} onCancel={handleRejectTool}
        okText="确认执行" cancelText="取消"
        okButtonProps={{ danger: true }}>
        {pendingConfirm && (
          <div>
            <p>Agent 将执行以下敏感操作：</p>
            <Card size="small" style={{ marginTop: 8 }}>
              <div><strong>工具：</strong><Tag color="red">{pendingConfirm.tool.replace(/_tool$/, '')}</Tag></div>
              {Object.keys(pendingConfirm.args).length > 0 && (
                <div style={{ marginTop: 8 }}>
                  <strong>参数：</strong>
                  <pre style={{ fontSize: 12, marginTop: 4, background: '#f5f5f5', padding: 8, borderRadius: 4, maxHeight: 200, overflow: 'auto' }}>
                    {JSON.stringify(pendingConfirm.args, null, 2)}
                  </pre>
                </div>
              )}
            </Card>
          </div>
        )}
      </Modal>
      {/* Resume preview modal (matches ResumePage pattern) */}
      <Modal title="简历预览" open={!!resumePreviewId} width="70%" footer={null}
        onCancel={() => { setResumePreviewId(null); setResumePreviewHtml(''); }}>
        {resumePreviewId && (
          <>
            <div style={{ marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
              <Text>切换模板：</Text>
              <Select value={resumePreviewTemplate} onChange={(v) => handleResumeTemplateChange(resumePreviewId!, v)}
                options={templates.map(t => ({ label: t.name, value: t.key }))} style={{ width: 200 }} />
              <Button type="primary" icon={<DownloadOutlined />}
                onClick={async () => {
                  try {
                    const detail = await getResume(resumePreviewId!);
                    const parsed = JSON.parse(detail.content || '{}');
                    const personal = parsed.personal || {};
                    const name = personal.name || '';
                    const phone = personal.phone || '';
                    const jobTitle = personal.jobTitle || '';
                    const filename = [name, jobTitle, phone].filter(Boolean).join('_') + '.pdf';
                    const url = getResumeDownloadUrl(resumePreviewId!, resumePreviewTemplate);
                    const res = await api.get(url, { responseType: 'blob' });
                    const blob = new Blob([res.data], { type: 'application/pdf' });
                    const link = document.createElement('a');
                    link.href = URL.createObjectURL(blob);
                    link.download = filename;
                    link.click();
                    URL.revokeObjectURL(link.href);
                  } catch { message.error('下载失败'); }
                }}>下载 PDF</Button>
            </div>
            <div dangerouslySetInnerHTML={{ __html: resumePreviewHtml }} style={{ height: '70vh', overflow: 'auto' }} />
          </>
        )}
      </Modal>
      {/* Report preview modal (matches InterviewGuidePage pattern) */}
      <Modal title={`面试报告预览${reportPreviewCompanyName ? ` - ${reportPreviewCompanyName}` : ''}`}
        open={reportPreviewVisible} onCancel={() => setReportPreviewVisible(false)} width={900}
        footer={[
          <Button key="close" onClick={() => setReportPreviewVisible(false)}>关闭</Button>,
          <Button key="download" type="primary" icon={<DownloadOutlined />}
            onClick={handleReportDownload} disabled={reportPreviewGuideId === null}>下载PDF</Button>,
        ]} style={{ top: 20 }}>
        <Spin spinning={reportPreviewLoading}>
          <div style={{ maxHeight: '70vh', overflow: 'auto', background: '#fff' }}>
            <iframe srcDoc={reportPreviewHtml} style={{ width: '100%', height: '70vh', border: 'none' }} title="报告预览" />
          </div>
        </Spin>
      </Modal>
    </Fragment>
  );
}
