from flask import Flask, render_template_string, request, session, redirect, url_for
import httpx
import json

import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'answer-agent-secret-key')
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = 1800  # 30 minutes

BACKEND_PORT = int(os.getenv('BACKEND_PORT', 51666))
BACKEND_URL = os.environ.get("BACKEND_URL", f"http://localhost:{BACKEND_PORT}")

# Fetch AMAP API key from backend (dynamic config, not hardcoded)
_AMAP_API_KEY = ""
try:
    _resp = httpx.get(f"{BACKEND_URL}/api/public-config", timeout=5)
    if _resp.status_code == 200:
        _AMAP_API_KEY = _resp.json().get("amap_api_key", "")
except Exception:
    pass

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AS Agent</title>
    <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" crossorigin="" />
    <script src="https://cdn.jsdelivr.net/npm/marked@15/marked.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/dompurify@3/dist/purify.min.js"></script>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" crossorigin=""></script>
    <style>
        :root {
            --primary-bg: #f5f7fa;
            --secondary-bg: #ffffff;
            --tertiary-bg: #eef1f6;
            --accent-color: #6366f1;
            --accent-hover: #818cf8;
            --accent-light: rgba(99, 102, 241, 0.08);
            --text-primary: #1e293b;
            --text-secondary: #64748b;
            --text-muted: #94a3b8;
            --border-color: #e2e8f0;
            --success-color: #10b981;
            --error-color: #ef4444;
            --card-bg: #ffffff;
            --shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
            --card-shadow: 0 4px 16px rgba(0, 0, 0, 0.06);
        }

        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
            background: var(--primary-bg);
            color: var(--text-primary);
            min-height: 100vh;
            line-height: 1.6;
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
        }

        .container {
            margin: 0 auto;
            padding: 0;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }

        /* Markdown rendered content */
        .chat-bubble p { margin: 0; }
        .chat-bubble ul, .chat-bubble ol { margin: 0; padding-left: 20px; }
        .chat-bubble li { margin: 0; padding: 0; }
        .chat-bubble li + li { margin-top: 2px; }
        .chat-bubble br { display: none; }
        .chat-bubble pre {
            background: #f1f5f9;
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 12px;
            overflow-x: auto;
            font-size: 13px;
            margin: 4px 0;
        }
        .chat-bubble code {
            font-family: 'JetBrains Mono', 'SF Mono', 'Fira Code', monospace;
            font-size: 13px;
            background: #f1f5f9;
            padding: 2px 5px;
            border-radius: 4px;
        }
        .chat-bubble pre code {
            background: none;
            padding: 0;
            border-radius: 0;
        }
        .chat-bubble h1, .chat-bubble h2, .chat-bubble h3,
        .chat-bubble h4, .chat-bubble h5, .chat-bubble h6 {
            margin: 4px 0;
            font-weight: 600;
            color: var(--text-primary);
        }
        .chat-bubble h1 { font-size: 18px; }
        .chat-bubble h2 { font-size: 16px; }
        .chat-bubble h3 { font-size: 15px; }
        .chat-bubble blockquote {
            border-left: 3px solid var(--accent-color);
            padding: 4px 12px;
            margin: 4px 0;
            color: var(--text-secondary);
            background: var(--accent-light);
            border-radius: 0 6px 6px 0;
        }
        .chat-bubble table {
            border-collapse: collapse;
            width: 100%;
            margin: 4px 0;
            font-size: 13px;
        }
        .chat-bubble th, .chat-bubble td {
            border: 1px solid var(--border-color);
            padding: 6px 10px;
            text-align: left;
        }
        .chat-bubble th {
            background: var(--tertiary-bg);
            font-weight: 600;
        }
        .chat-bubble strong { font-weight: 600; }
        .chat-bubble a { color: var(--accent-color); text-decoration: none; }
        .chat-bubble a:hover { text-decoration: underline; }
        .chat-bubble hr {
            border: none;
            border-top: 1px solid var(--border-color);
            margin: 6px 0;
        }

        .step-1 {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            padding: 20px;
        }

        .step-2 {
            display: none;
            flex-direction: column;
            height: 100vh;
            overflow: hidden;
            background: var(--secondary-bg);
        }

        .step-2 > .welcome-section {
            flex-shrink: 0;
        }

        .step-2 > .chat-history {
            flex: 1;
            min-height: 0;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            align-items: center;
        }

        .step-2 > .chat-history > .chat-history-inner {
            width: 100%;
            max-width: 720px;
            display: flex;
            flex-direction: column;
            gap: 12px;
            padding: 16px 0;
        }

        .step-2 > .chat-input-area {
            flex-shrink: 0;
        }

        .logo {
            text-align: center;
            margin-bottom: 40px;
        }

        .logo-icon {
            font-size: 56px;
            margin-bottom: 12px;
            filter: drop-shadow(0 4px 12px rgba(99, 102, 241, 0.3));
        }

        .logo-title {
            font-size: 28px;
            font-weight: 700;
            color: var(--text-primary);
            letter-spacing: -0.5px;
        }

        .logo-subtitle {
            font-size: 15px;
            color: var(--text-muted);
            margin-top: 8px;
        }

        .form-group {
            width: 100%;
            max-width: 380px;
            margin-bottom: 20px;
        }

        .form-label {
            display: block;
            font-size: 14px;
            font-weight: 500;
            color: var(--text-secondary);
            margin-bottom: 8px;
        }

        .form-input {
            width: 100%;
            padding: 14px 18px;
            background: var(--tertiary-bg);
            border: 1px solid var(--border-color);
            border-radius: 10px;
            font-size: 15px;
            color: var(--text-primary);
            transition: all 0.2s ease;
            font-family: inherit;
        }

        .form-input::placeholder {
            color: var(--text-muted);
        }

        .form-input:focus {
            outline: none;
            border-color: var(--accent-color);
            box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.15);
        }

        .btn {
            width: 100%;
            max-width: 380px;
            padding: 14px 28px;
            background: linear-gradient(135deg, var(--accent-color) 0%, #8b5cf6 100%);
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 15px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
            box-shadow: 0 2px 8px rgba(99, 102, 241, 0.25);
        }

        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(99, 102, 241, 0.35);
        }

        .btn:active {
            transform: translateY(0);
        }

        .btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
            box-shadow: none;
        }

        .error-message {
            display: none;
            width: 100%;
            max-width: 380px;
            padding: 12px 16px;
            background: rgba(239, 68, 68, 0.08);
            border: 1px solid rgba(239, 68, 68, 0.2);
            border-radius: 8px;
            border-radius: 8px;
            color: var(--error-color);
            font-size: 14px;
            margin-bottom: 16px;
            text-align: center;
        }

        .error-message.show {
            display: block;
        }

        .loading-indicator {
            display: none;
            flex-direction: row;
            align-items: center;
            justify-content: flex-start;
            gap: 8px;
            padding: 8px 14px;
            background: var(--tertiary-bg);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            max-width: 80%;
            flex-wrap: nowrap;
        }

        .loading-indicator.show {
            display: flex;
        }

        .loading-indicator span:first-child {
            color: var(--text-muted);
            font-size: 13px;
            white-space: nowrap;
        }

        .loading-dots {
            display: flex;
            flex-direction: row;
            gap: 4px;
            flex-wrap: nowrap;
        }

        .loading-dot {
            width: 8px;
            height: 8px;
            background: var(--accent-color);
            border-radius: 50%;
            animation: loadingPulse 1.2s ease-in-out infinite;
        }

        .loading-dot:nth-child(1) { animation-delay: 0s; }
        .loading-dot:nth-child(2) { animation-delay: 0.15s; }
        .loading-dot:nth-child(3) { animation-delay: 0.3s; }

        @keyframes loadingPulse {
            0%, 100% { opacity: 0.4; transform: scale(0.9); }
            50% { opacity: 1; transform: scale(1); }
        }

        .chat-header {
            padding: 20px 0;
            border-bottom: 1px solid var(--border-color);
            margin-bottom: 20px;
        }

        .chat-title {
            font-size: 20px;
            font-weight: 600;
            color: var(--text-primary);
            margin-bottom: 8px;
        }

        .chat-subtitle {
            font-size: 14px;
            color: var(--text-muted);
        }

        .welcome-section {
            padding: 24px 16px 14px;
            position: relative;
            display: flex;
            flex-direction: column;
            align-items: center;
        }

        .welcome-section::after {
            content: '';
            position: absolute;
            bottom: 0;
            left: 50%;
            transform: translateX(-50%);
            width: 100%;
            max-width: 720px;
            height: 1px;
            background: var(--border-color);
            pointer-events: none;
        }

        .welcome-greeting,
        .welcome-intro,
        .quick-questions {
            width: 100%;
            max-width: 720px;
        }

        .welcome-greeting {
            font-size: 20px;
            font-weight: 700;
            color: var(--text-primary);
            margin-bottom: 6px;
            text-align: left;
        }

        .welcome-intro {
            font-size: 13px;
            color: var(--text-secondary);
            line-height: 1.5;
            margin-bottom: 12px;
            text-align: left;
        }

        .quick-questions {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            justify-content: flex-start;
        }

        .quick-question-btn {
            padding: 8px 14px;
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            color: var(--text-secondary);
            font-size: 13px;
            cursor: pointer;
            transition: all 0.2s ease;
            text-align: left;
        }

        .quick-question-btn:hover {
            background: var(--accent-color);
            border-color: var(--accent-color);
            color: white;
        }

        .quick-question-btn.resume-btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-color: #667eea;
            color: white;
            font-weight: 500;
        }

        .quick-question-btn.resume-btn:hover {
            background: linear-gradient(135deg, #5568d3 0%, #683aa2 100%);
            border-color: #5568d3;
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
        }

        .chat-message {
            max-width: 80%;
            animation: slideIn 0.3s ease-out;
        }

        @keyframes slideIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .chat-message.user { align-self: flex-end; }
        .chat-message.ai { align-self: flex-start; }

        .chat-bubble {
            padding: 14px 18px;
            border-radius: 16px;
            font-size: 15px;
            line-height: 1.55;
            word-break: break-word;
        }

        .user .chat-bubble {
            background: linear-gradient(135deg, var(--accent-color) 0%, #818cf8 100%);
            color: white;
            border-bottom-right-radius: 6px;
        }

        .ai .chat-bubble {
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            color: var(--text-primary);
            border-bottom-left-radius: 6px;
            box-shadow: var(--shadow);
        }

        .chat-avatar {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 6px;
            font-size: 12px;
            font-weight: 500;
        }

        .user .chat-avatar { color: var(--accent-hover); justify-content: flex-end; }
        .ai .chat-avatar { color: var(--success-color); }

        .chat-input-area {
            padding: 12px 16px;
            padding-bottom: 24px;
            position: sticky;
            bottom: 0;
            z-index: 50;
        }

        .chat-input-area::before {
            content: '';
            position: absolute;
            top: 0;
            left: 50%;
            transform: translateX(-50%);
            width: 100%;
            max-width: 720px;
            height: 1px;
            background: var(--border-color);
            pointer-events: none;
        }

        .input-wrapper {
            display: flex;
            justify-content: center;
        }

        .input-area {
            width: 100%;
            max-width: 720px;
            display: flex;
            gap: 8px;
            padding: 8px;
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            box-shadow: var(--card-shadow);
        }

        .disclaimer {
            text-align: center;
            font-size: 11px;
            color: var(--text-muted);
            padding-top: 8px;
        }

        .textbox {
            flex: 1;
            padding: 10px 14px;
            border: none;
            border-radius: 8px;
            font-size: 15px;
            background: var(--tertiary-bg);
            color: var(--text-primary);
            font-family: inherit;
        }

        .textbox:focus {
            outline: none;
        }

        .textbox::placeholder {
            color: var(--text-muted);
        }

        .send-btn {
            padding: 10px 20px;
            background: linear-gradient(135deg, var(--accent-color) 0%, #8b5cf6 100%);
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.2s ease;
        }

        .send-btn:hover {
            transform: scale(1.02);
            box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
        }

        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: var(--tertiary-bg); }
        ::-webkit-scrollbar-thumb { background: var(--border-color); border-radius: 3px; }

        /* Booking Modal */
        /* Booking card in chat */
.booking-card {
    cursor: pointer !important;
    display: flex !important;
    align-items: center;
    gap: 12px;
    padding: 16px !important;
    border: 2px solid var(--accent-color) !important;
    border-radius: 12px !important;
    transition: all 0.2s;
    max-width: 380px;
    background: linear-gradient(135deg, var(--secondary-bg), var(--accent-light));
}
.booking-card:hover {
    border-color: var(--accent-hover) !important;
    box-shadow: 0 4px 16px rgba(99,102,241,0.15);
    transform: translateY(-1px);
}
.booking-card-icon {
    font-size: 32px;
    flex-shrink: 0;
}
.booking-card-text {
    flex: 1;
    min-width: 0;
}
.booking-card-title {
    font-weight: 600;
    font-size: 15px;
    color: var(--text-primary);
    margin-bottom: 4px;
}
.booking-card-desc {
    font-size: 12px;
    color: var(--text-secondary);
    line-height: 1.4;
}
.booking-card-btn {
    flex-shrink: 0;
    background: var(--accent-color);
    color: #fff;
    padding: 6px 14px;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 500;
    white-space: nowrap;
}

.booking-overlay {
            position: fixed; top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0,0,0,0.5); z-index: 1000;
            display: flex; align-items: center; justify-content: center;
        }
        .map-picker-overlay {
            position: fixed; top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0,0,0,0.5); z-index: 1100;
            display: flex; align-items: center; justify-content: center;
        }
        .booking-modal {
            background: var(--secondary-bg); border-radius: 16px;
            width: 480px; max-width: 90vw; max-height: 90vh; overflow-y: auto;
            box-shadow: 0 20px 60px rgba(0,0,0,0.15);
        }
        .booking-header {
            display: flex; justify-content: space-between; align-items: center;
            padding: 20px 24px 0; font-size: 18px; font-weight: 600;
        }
        .booking-close {
            font-size: 24px; cursor: pointer; color: var(--text-muted);
            line-height: 1; padding: 4px;
        }
        .booking-close:hover { color: var(--text-primary); }
        .booking-body { padding: 16px 24px; }
        .booking-field { margin-bottom: 14px; }
        .booking-field label { display: block; font-size: 13px; color: var(--text-secondary); margin-bottom: 4px; font-weight: 500; }
        .booking-input {
            width: 100%;
            padding: 8px 12px;
            border: 1px solid var(--border-color);
            border-radius: 8px;
            font-size: 14px;
            outline: none;
            transition: border-color 0.2s;
            background: var(--card-bg);
            color: var(--text-primary);
        }
        .booking-input:focus { border-color: var(--accent-color); }
        .booking-input::placeholder { color: var(--text-muted); }
        .booking-error { background: #fef2f2; color: var(--error-color); padding: 10px 12px; border-radius: 8px; font-size: 13px; margin-bottom: 8px; }
        .booking-success { background: #f0fdf4; color: var(--success-color); padding: 10px 12px; border-radius: 8px; font-size: 13px; margin-bottom: 8px; }
        .booking-footer {
            display: flex; justify-content: flex-end; gap: 10px;
            padding: 16px 24px 20px; border-top: 1px solid var(--border-color);
        }
        .booking-btn {
            padding: 10px 20px; border-radius: 8px; font-size: 14px; font-weight: 500;
            cursor: pointer; border: none; transition: all 0.2s;
        }
        .booking-btn-cancel {
            background: var(--tertiary-bg); color: var(--text-secondary);
        }
        .booking-btn-cancel:hover { background: var(--border-color); }
        .booking-btn-submit {
            background: var(--accent-color); color: white;
        }
        .booking-btn-submit:hover { background: var(--accent-hover); }
        .booking-btn-submit:disabled { opacity: 0.6; cursor: not-allowed; }
    </style>
</head>
<body>
    <div class="container">
        <div id="step1" class="step-1" style="display:none;">
            <div class="logo">
                <div class="logo-icon">🤖</div>
                <div class="logo-title">AS Agent</div>
                <div class="logo-subtitle">求职者信息咨询系统</div>
            </div>

            <div class="error-message" id="errorMessage"></div>

            <div class="form-group">
                <label class="form-label">请输入访问口令</label>
                <input type="password" id="password" class="form-input" placeholder="请输入口令" onkeydown="if(event.keyCode==13) verifyPassword()">
            </div>

            <button class="btn" id="submitBtn" onclick="verifyPassword()">
                <span id="btnText">验证身份</span>
                <div class="loading-indicator" id="loadingIndicator">
                    <span>验证中</span>
                    <span class="loading-dots">
                        <span class="loading-dot"></span>
                        <span class="loading-dot"></span>
                        <span class="loading-dot"></span>
                    </span>
                </div>
            </button>
        </div>

        <div id="step2" class="step-2">
            <div class="welcome-section" id="welcomeSection">
                <div class="welcome-greeting" id="welcomeGreeting">加载中...</div>
                <div class="welcome-intro" id="welcomeIntro">加载中...</div>
                <div class="quick-questions" id="quickQuestions">
                    <button class="quick-question-btn">加载中...</button>
                </div>
            </div>

            <div class="chat-history" id="chatHistory">
                <div class="chat-history-inner">
                    <div class="chat-message ai">
                        <div class="chat-avatar"><span>🤖</span> AI</div>
                        <div class="chat-bubble" id="initialMessage">加载中...</div>
                    </div>
                </div>
            </div>

            <div class="chat-input-area">
                <div class="input-wrapper">
                    <div class="input-area">
                        <input type="text" id="message" class="textbox" placeholder="输入问题后按回车发送..." onkeydown="if(event.keyCode==13) sendMessage()">
                        <input type="hidden" id="hiddenContext" value="">
                        <button class="send-btn" onclick="sendMessage()"><span>➤</span></button>
                    </div>
                </div>
                <div class="disclaimer">内容由AI基于个人知识库生成，仅供参考</div>
                <div style="text-align:right;font-size:11px;padding:2px 8px;color:#999">
                    <span id="debugLoading">⚪</span>
                </div>
            </div>
        </div>
    </div>

    <script>
        let sessionId = null;
        const VISITOR_EXPIRE_MINUTES = 120;

        function saveVisitorSession(sid) {
            const expiry = Date.now() + VISITOR_EXPIRE_MINUTES * 60 * 1000;
            localStorage.setItem('visitor_session', JSON.stringify({session_id: sid, expiry: expiry}));
        }

        function loadVisitorSession() {
            try {
                const stored = localStorage.getItem('visitor_session');
                if (stored) {
                    const data = JSON.parse(stored);
                    if (Date.now() < data.expiry) {
                        return data.session_id;
                    }
                }
            } catch(e) {}
            return null;
        }

        function clearVisitorSession() {
            localStorage.removeItem('visitor_session');
        }

        function saveMessagesToLocalStorage() {
            if (!sessionId) return;
            const messages = [];
            document.querySelectorAll('#chatHistory .chat-message').forEach(msg => {
                if (msg.classList.contains('booking-card-message')) return;
                const role = msg.classList.contains('user') ? 'user' : 'ai';
                const bubble = msg.querySelector('.chat-bubble');
                const content = bubble?.getAttribute('data-raw') || bubble?.textContent || '';
                messages.push({ role, content });
            });
            localStorage.setItem('visitor_messages_' + sessionId, JSON.stringify(messages));
        }

        function loadMessagesFromLocalStorage() {
            if (!sessionId) return;
            const rawMessages = JSON.parse(localStorage.getItem('visitor_messages_' + sessionId) || '[]');
            if (rawMessages.length === 0) return;
            // Clean old booking card artifacts that may have been saved before the fix
            const messages = rawMessages.filter(msg => !(msg.role === 'ai' && msg.content && msg.content.includes('📋 邀约面试')));
            if (messages.length !== rawMessages.length) {
                localStorage.setItem('visitor_messages_' + sessionId, JSON.stringify(messages));
            }
            // Clear and recreate inner wrapper
            const chatHistoryInner = document.querySelector('#chatHistory .chat-history-inner');
            chatHistoryInner.innerHTML = '';
            messages.forEach(msg => {
                if (msg.role && msg.content) {
                    addMessage(msg.role, msg.content);
                }
            });
        }

        function clearMessagesFromLocalStorage() {
            if (sessionId) {
                localStorage.removeItem('visitor_messages_' + sessionId);
            }
        }

        async function checkSavedSession() {
            const saved = loadVisitorSession();
            if (saved) {
                try {
                    const resp = await fetch(VB + '/api/check-session', {
                        headers: {"X-Session-ID": saved}
                    });
                    if (resp.ok) {
                        sessionId = saved;
                        document.getElementById('step1').style.display = 'none';
                        document.getElementById('step2').style.display = 'flex';
                        await loadWelcomeConfig();
                        loadMessagesFromLocalStorage();
                        startBookingPolling();
                        fetchExistingBooking();
                        return true;
                    }
                } catch(e) {}
                clearVisitorSession();
            }
            return false;
        }

        const VB = window.location.pathname.startsWith('/visitor/') ? '/visitor' : '';

        let isLoading = false;
        let _loadingTimeout = null;

        function _resetLoading() {
            isLoading = false;
            _updateLoadingIndicator();
            if (_loadingTimeout) {
                clearTimeout(_loadingTimeout);
                _loadingTimeout = null;
            }
        }

        // DEBUG: visual loading indicator
        function _updateLoadingIndicator() {
            const el = document.getElementById('debugLoading');
            if (!el) return;
            el.textContent = isLoading ? '🔴' : '🟢';
            el.style.color = isLoading ? 'red' : 'green';
        }
        setInterval(_updateLoadingIndicator, 100);

        (async function initVisitor() {
            const restored = await checkSavedSession();
            if (restored) return;

            let hasPassword = {{ _HAS_PASSWORD }};

            if (!hasPassword) {
                try {
                    const response = await fetch(VB + '/verify', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ password: '', user_id: '{{ _USER_ID }}' })
                    });
                    const data = await response.json();
                    if (data.success) {
                        sessionId = data.session_id;
                        saveVisitorSession(sessionId);
                        document.getElementById('step2').style.display = 'flex';
                        await loadWelcomeConfig();
                        startBookingPolling();
                        fetchExistingBooking();
                    }
                } catch(e) {
                    document.getElementById('step1').style.display = 'flex';
                }
            } else {
                document.getElementById('step1').style.display = 'flex';
            }
        })();

        async function verifyPassword() {
            if (isLoading) return;
            const password = document.getElementById('password').value.trim();
            if (!password) { showError('请输入访问口令'); return; }

            const btn = document.getElementById('submitBtn');
            const btnText = document.getElementById('btnText');
            const loadingIndicator = document.getElementById('loadingIndicator');
            const errorMessage = document.getElementById('errorMessage');

            isLoading = true;
            if (_loadingTimeout) clearTimeout(_loadingTimeout);
            _loadingTimeout = setTimeout(_resetLoading, 60000);
            btn.disabled = true;
            btnText.style.display = 'none';
            loadingIndicator.classList.add('show');
            errorMessage.classList.remove('show');

            try {
                    const response = await fetch(VB + '/verify', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ password: password, user_id: '{{ _USER_ID }}' })
                });
                const data = await response.json();

                if (data.success) {
                    sessionId = data.session_id;
                    saveVisitorSession(sessionId);
                    document.getElementById('step1').style.display = 'none';
                    document.getElementById('step2').style.display = 'flex';
                    await loadWelcomeConfig();
                    startBookingPolling();
                    fetchExistingBooking();
                } else {
                    showError(data.message || '验证失败');
                }
            } catch (e) {
                showError('网络错误，请稍后重试');
            } finally {
                _resetLoading();
                btn.disabled = false;
                btnText.style.display = 'inline';
                loadingIndicator.classList.remove('show');
            }
        }

        function showError(message) {
            const errorMessage = document.getElementById('errorMessage');
            errorMessage.textContent = message;
            errorMessage.classList.add('show');
        }

        async function sendMessage() {
            if (isLoading) return;
            const message = document.getElementById('message').value.trim();
            if (!message) return;

            document.getElementById('message').value = '';
            addMessage('user', message);

            isLoading = true;
            _updateLoadingIndicator();
            if (_loadingTimeout) clearTimeout(_loadingTimeout);
            _loadingTimeout = setTimeout(_resetLoading, 60000);
            const loadingMessage = addLoadingMessage();

            // Use hidden context for the API call if set (e.g., from portfolio preview)
            const hiddenCtx = document.getElementById('hiddenContext').value;
            document.getElementById('hiddenContext').value = '';
            const apiMessage = hiddenCtx || message;

            try {
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Session-ID': sessionId
                    },
                    body: JSON.stringify({ message: apiMessage })
                });

                if (!response.ok) {
                    loadingMessage.remove();
                    const errorData = await response.json().catch(() => ({}));
                    const msg = errorData.detail || '请求失败 (' + response.status + ')';
                    addMessage('ai', msg);
                    return;
                }

                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let aiResponse = '';
                let messageId = null;

                let streamDone = false, streamTimer = null;
                while (!streamDone) {
                    const readPromise = reader.read();
                    const timeoutPromise = messageId
                        ? new Promise(resolve => setTimeout(() => resolve({ done: true, value: undefined }), 5000))
                        : new Promise(() => {});
                    const { done, value } = await Promise.race([readPromise, timeoutPromise]);
                    if (done) { streamDone = true; break; }
                    const chunk = decoder.decode(value, { stream: true });
                    aiResponse += chunk;
                    // Detect application-level stream-end marker
                    const endMarker = '__STREAM_END__';
                    if (aiResponse.includes(endMarker)) {
                        aiResponse = aiResponse.replace(endMarker, '');
                        streamDone = true;
                    }

                    if (!messageId) {
                        loadingMessage.remove();
                        messageId = addMessage('ai', '');
                    }
                    updateMessage(messageId, aiResponse);
                    if (streamDone) break;
                }
                if (streamTimer) clearTimeout(streamTimer);
            } catch (e) {
                loadingMessage.remove();
                if (messageId) updateMessage(messageId, '连接错误: ' + e.message);
            } finally {
                _resetLoading();
                // 每次消息后重新开启轮询，检测是否有面试意向
                startBookingPolling();
            }
        }

        function sendQuickQuestion(question) {
            document.getElementById('message').value = question;
            sendMessage();
        }

        // Called from portfolio preview window via window.opener
        window.askAboutPortfolioItem = function(name, description) {
            const displayText = '想了解更多关于「' + name + '」的信息';
            const fullContext = displayText + '：' + description;
            document.getElementById('hiddenContext').value = fullContext;
            sendQuickQuestion(displayText);
            // 滚动到聊天区域，聚焦输入框
            const chatContainer = document.querySelector('.chat-container');
            if (chatContainer) chatContainer.scrollIntoView({ behavior: 'smooth' });
            setTimeout(function() {
                document.getElementById('message').focus();
            }, 300);
        };

        function openResumePreview() {
            window.open(VB + '/resume-preview?user_id={{ _USER_ID }}', '_blank');
        }

        function openPortfolioPreview() {
            var sid = sessionId || '';
            window.open(VB + '/portfolio-preview?user_id={{ _USER_ID }}' + (sid ? '&session_id=' + encodeURIComponent(sid) : ''), '_blank');
        }

        async function loadWelcomeConfig() {
            try {
                const response = await fetch(VB + '/api/welcome-config', {
                    headers: sessionId ? {"X-Session-ID": sessionId} : {}
                });
                if (response.ok) {
                    const config = await response.json();
                    
                    document.getElementById('welcomeGreeting').textContent = config.greeting || '您好，欢迎您的到来';
                    document.getElementById('welcomeIntro').textContent = config.self_intro || '正在加载个人信息...';
                    document.getElementById('initialMessage').textContent = config.initial_message || '您好！欢迎了解我的求职信息，请问您想了解哪些方面？';
                    
                    const questionsContainer = document.getElementById('quickQuestions');
                    questionsContainer.innerHTML = '';
                    
                    const resumeShow = config.resume_show || false;
                    
                    if (config.quick_questions && config.quick_questions.length > 0) {
                        const filtered = config.quick_questions.filter(q => !q.includes('简历') || resumeShow);
                        const limited = filtered.slice(0, 6);
                        limited.forEach(question => {
                            const btn = document.createElement('button');
                            if (question.includes('简历')) {
                                btn.className = 'quick-question-btn resume-btn';
                            } else {
                                btn.className = 'quick-question-btn';
                            }
                            btn.textContent = question;
                            if (question.includes('简历')) {
                                btn.onclick = openResumePreview;
                            } else {
                                btn.onclick = () => sendQuickQuestion(question);
                            }
                            questionsContainer.appendChild(btn);
                        });
                    }
                    
                    if (resumeShow) {
                        const resumeBtn = document.createElement('button');
                        resumeBtn.className = 'quick-question-btn resume-btn';
                        resumeBtn.textContent = '📄 查看/下载怀旧版简历';
                        resumeBtn.onclick = openResumePreview;
                        questionsContainer.appendChild(resumeBtn);
                    }
                    const portfolioShow = config.portfolio_show || false;
                    if (portfolioShow) {
                        const portfolioBtn = document.createElement('button');
                        portfolioBtn.className = 'quick-question-btn resume-btn';
                        portfolioBtn.textContent = '🌐 新版个人主页';
                        portfolioBtn.onclick = openPortfolioPreview;
                        questionsContainer.appendChild(portfolioBtn);
                    }
                    
                    const bookingBtn = document.createElement('button');
                    bookingBtn.className = 'quick-question-btn resume-btn';
                    bookingBtn.textContent = '📋 邀约面试';
                    bookingBtn.onclick = showBookingForm;
                    questionsContainer.appendChild(bookingBtn);
                }
            } catch (e) {
                console.error('加载配置失败:', e);
            }
        }

        function renderMarkdown(text) {
            if (!text) return '';
            try {
                // Collapse 3+ blank lines into 1 (reduce excessive whitespace in AI output)
                text = text.replace(/\\n{3,}/g, '\\n\\n');
                const html = marked.parse(text, { gfm: true });
                return DOMPurify.sanitize(html);
            } catch(e) {
                return text;
            }
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML.replace(/"/g, '&quot;');
        }

        function addMessage(role, content) {
            const chatHistoryInner = document.querySelector('#chatHistory .chat-history-inner');
            const chatHistory = document.getElementById('chatHistory');
            const messageDiv = document.createElement('div');
            messageDiv.className = 'chat-message ' + role;
            const avatar = role === 'user' ? '👤' : '🤖';
            const roleText = role === 'user' ? '我' : 'AI';

            const bubbleContent = role === 'ai'
                ? renderMarkdown(content)
                : escapeHtml(content);

            messageDiv.innerHTML = `
                <div class="chat-avatar"><span>${avatar}</span> ${roleText}</div>
                <div class="chat-bubble" data-raw="${escapeHtml(content || '')}">${bubbleContent || ''}</div>
            `;
            chatHistoryInner.appendChild(messageDiv);
            chatHistory.scrollTop = chatHistory.scrollHeight;
            saveMessagesToLocalStorage();
            return messageDiv;
        }

        function addLoadingMessage() {
            const chatHistoryInner = document.querySelector('#chatHistory .chat-history-inner');
            const chatHistory = document.getElementById('chatHistory');
            const messageDiv = document.createElement('div');
            messageDiv.className = 'chat-message ai';
            messageDiv.innerHTML = `
                <div class="chat-avatar"><span>🤖</span> AI</div>
                <div class="chat-bubble" style="display: flex; align-items: center; gap: 8px;">
                    <span>思考中</span>
                    <span class="loading-dots">
                        <span class="loading-dot"></span>
                        <span class="loading-dot"></span>
                        <span class="loading-dot"></span>
                    </span>
                </div>
            `;
            chatHistoryInner.appendChild(messageDiv);
            chatHistory.scrollTop = chatHistory.scrollHeight;
            return messageDiv;
        }

        let _saveTimeout = null;
        function updateMessage(element, content) {
            const bubble = element.querySelector('.chat-bubble');
            bubble.innerHTML = renderMarkdown(content || '');
            bubble.setAttribute('data-raw', content || '');
            const chatHistory = document.getElementById('chatHistory');
            chatHistory.scrollTop = chatHistory.scrollHeight;
            clearTimeout(_saveTimeout);
            _saveTimeout = setTimeout(saveMessagesToLocalStorage, 500);
        }
    </script>

    <!-- Booking Modal -->
    <!-- Map Picker Modal -->
    <div id="mapPickerOverlay" class="map-picker-overlay" style="display:none">
      <div class="booking-modal" style="max-width:700px">
        <div class="booking-header">
          <h3>📍 选择地址</h3>
          <span class="booking-close" onclick="closeMapPicker()">&times;</span>
        </div>
        <div class="booking-body">
          <div class="booking-field">
            <label>搜索地址</label>
            <div style="display:flex;gap:8px">
              <input type="text" id="mapSearchKeyword" class="booking-input" placeholder="输入公司或地址名称搜索" style="flex:1" />
              <button class="booking-btn booking-btn-submit" onclick="mapSearch()" style="white-space:nowrap">搜索</button>
            </div>
          </div>
          <div id="mapSearchResults" style="max-height:160px;overflow:auto;margin-bottom:8px;display:none"></div>
          <div id="mapContainer" style="width:100%;height:300px;border-radius:8px;overflow:hidden"></div>
          <div id="mapSelectedAddress" style="margin-top:8px;padding:8px 12px;background:var(--accent-light);border-radius:6px;font-size:13px;display:none"></div>
        </div>
        <div class="booking-footer">
          <button class="booking-btn booking-btn-cancel" onclick="closeMapPicker()">取消</button>
          <button class="booking-btn booking-btn-submit" id="mapConfirmBtn" onclick="confirmMapAddress()" disabled>确认地址</button>
        </div>
      </div>
    </div>

    <!-- Booking Form Modal -->
    <div id="bookingOverlay" class="booking-overlay" style="display:none">
      <div class="booking-modal">
        <div class="booking-header">
          <h3>📋 邀约面试</h3>
          <span class="booking-close" onclick="closeBookingForm()">&times;</span>
        </div>
        <div class="booking-body">
          <p style="color:var(--text-secondary);margin-bottom:16px;">请填写以下信息进行邀约面试：</p>
          <div class="booking-field">
            <label>公司名称 *</label>
            <input type="text" id="bkCompany" class="booking-input" placeholder="例如：字节跳动" />
          </div>
          <div class="booking-field">
            <label>岗位名称 *</label>
            <input type="text" id="bkJob" class="booking-input" placeholder="例如：高级产品经理" />
          </div>
          <div class="booking-field">
            <label>HR姓名</label>
            <input type="text" id="bkHrName" class="booking-input" placeholder="您的称呼" />
          </div>
          <div class="booking-field">
            <label>联系电话</label>
            <input type="text" id="bkHrPhone" class="booking-input" placeholder="手机号" />
          </div>
          <div class="booking-field">
            <label>联系邮箱 *</label>
            <input type="email" id="bkEmail" class="booking-input" placeholder="用于接收邀约反馈" />
          </div>
          <div class="booking-field">
            <label>面试地址</label>
            <div style="display:flex;gap:8px">
              <input type="text" id="bkAddress" class="booking-input" placeholder="公司地址（可手动输入，也可点击右侧地图选点）" style="flex:1" />
              <button class="booking-btn booking-btn-submit" onclick="openMapPicker()" style="white-space:nowrap;font-size:13px">📍 地图选择</button>
            </div>
          </div>
          <div class="booking-field">
            <label>面试时间 *</label>
            <div style="display:flex;gap:8px;align-items:center">
              <input type="date" id="bkDate" class="booking-input" style="flex:1;min-width:0" />
              <select id="bkHour" class="booking-input" style="width:75px;flex:none">
                <option value="09">09时</option>
                <option value="10">10时</option>
                <option value="11">11时</option>
                <option value="12">12时</option>
                <option value="13">13时</option>
                <option value="14">14时</option>
                <option value="15">15时</option>
                <option value="16">16时</option>
                <option value="17">17时</option>
                <option value="18">18时</option>
              </select>
              <select id="bkMinute" class="booking-input" style="width:75px;flex:none">
                <option value="00">00分</option>
                <option value="15">15分</option>
                <option value="30">30分</option>
                <option value="45">45分</option>
              </select>
            </div>
          </div>
          <div id="bookingError" class="booking-error" style="display:none"></div>
          <div id="bookingSuccess" class="booking-success" style="display:none"></div>
        </div>
        <div class="booking-footer">
          <button class="booking-btn booking-btn-cancel" onclick="closeBookingForm()">稍后再说</button>
          <button class="booking-btn booking-btn-submit" id="bkSubmitBtn" onclick="submitBooking()">确认提交</button>
        </div>
      </div>
    </div>

    <script>
    // --- Interview Booking Flow ---
    var bookingPollInterval = null;
    var bookingCardShown = false;

    function startBookingPolling() {
        if (bookingPollInterval) clearInterval(bookingPollInterval);
        checkBookingSuggestion();
        bookingPollInterval = setInterval(checkBookingSuggestion, 5000);
    }

    function stopBookingPolling() {
        if (bookingPollInterval) {
            clearInterval(bookingPollInterval);
            bookingPollInterval = null;
        }
    }

    function dismissSuggestion() {
        fetch(VB + '/api/booking-dismiss', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: sessionId }),
        }).catch(function(){});
    }

    var pendingBookingTime = null;
    var sessionBookingId = null;
    var sessionBookingData = null;

    async function fetchExistingBooking() {
        if (!sessionId) return;
        try {
            var resp = await fetch(VB + '/api/booking/' + sessionId);
            var data = await resp.json();
            if (data.guide_id && data.status !== 'none') {
                sessionBookingId = data.guide_id;
                sessionBookingData = data;
                bookingCardShown = true;
                stopBookingPolling();
                // Show the booking card with submitted status if not already in chat
                var existing = document.querySelector('.booking-card');
                if (!existing) {
                    addBookingCard();
                }
                updateBookingCardSubmitted();
            }
        } catch(e) {}
    }

    function padTime(n) { return n.toString().padStart(2, '0'); }

    function updateBookingCardSubmitted() {
        var cards = document.querySelectorAll('.booking-card');
        if (cards.length > 0) {
            var lastCard = cards[cards.length - 1];
            var titleEl = lastCard.querySelector('.booking-card-title');
            var descEl = lastCard.querySelector('.booking-card-desc');
            var btnEl = lastCard.querySelector('.booking-card-btn');
            if (titleEl) titleEl.textContent = '✅ 已提交邀约';
            if (descEl) descEl.textContent = '点击可修改已提交的信息';
            if (btnEl) btnEl.textContent = '修改信息';
        }
    }

    function getTodayStr() {
        var now = new Date();
        return now.getFullYear() + '-' + padTime(now.getMonth()+1) + '-' + padTime(now.getDate());
    }

    function buildDateTimeStr() {
        var dateVal = document.getElementById('bkDate').value;
        var hourVal = document.getElementById('bkHour').value;
        var minVal = document.getElementById('bkMinute').value;
        if (!dateVal || !hourVal || !minVal) return null;
        return dateVal + 'T' + hourVal + ':' + minVal;
    }

    function setDateTimeFields(isoStr) {
        if (!isoStr) return;
        try {
            var d = new Date(isoStr);
            if (!isNaN(d.getTime())) {
                document.getElementById('bkDate').value = d.getFullYear() + '-' + padTime(d.getMonth()+1) + '-' + padTime(d.getDate());
                document.getElementById('bkHour').value = padTime(d.getHours());
                document.getElementById('bkMinute').value = padTime(Math.floor(d.getMinutes() / 15) * 15);
            }
        } catch(e) {}
    }

    async function checkBookingSuggestion() {
        if (!sessionId) return;
        try {
            var resp = await fetch(VB + '/api/booking-suggestion', {
                headers: {"X-Session-ID": sessionId}
            });
            var data = await resp.json();
            if (data.suggest_booking && data.booking_intent && !bookingCardShown) {
                stopBookingPolling();
                bookingCardShown = true;
                if (data.booking_time) {
                    pendingBookingTime = data.booking_time;
                }
                dismissSuggestion();
                addBookingCard();
            }
        } catch (e) {
            // Silently fail
        }
    }

    function addBookingCard() {
        var chatHistoryInner = document.querySelector('#chatHistory .chat-history-inner');
        var card = document.createElement('div');
        var desc = pendingBookingTime
            ? '已确认时间：' + pendingBookingTime + '，点击卡片确认邀约安排。'
            : '看来您对我很感兴趣！点击此卡片填写邀约信息。';
        card.className = 'chat-message ai booking-card-message';
        card.innerHTML = `
            <div class="chat-avatar"><span>🤖</span> AI</div>
            <div class="chat-bubble booking-card" onclick="showBookingForm()">
                <div class="booking-card-icon">📋</div>
                <div class="booking-card-text">
                    <div class="booking-card-title">邀约面试</div>
                    <div class="booking-card-desc">${desc}</div>
                </div>
                <div class="booking-card-btn">立即填写</div>
            </div>
        `;
        chatHistoryInner.appendChild(card);
        document.getElementById('chatHistory').scrollTop = document.getElementById('chatHistory').scrollHeight;
        saveMessagesToLocalStorage();
    }

    function showBookingForm() {
        document.getElementById('bookingOverlay').style.display = 'flex';
        document.getElementById('bookingError').style.display = 'none';
        document.getElementById('bookingSuccess').style.display = 'none';
        document.getElementById('bkSubmitBtn').disabled = false;
        document.getElementById('bkDate').min = getTodayStr();
        // Default hour:minute
        if (!document.getElementById('bkHour').value) document.getElementById('bkHour').value = '09';
        if (!document.getElementById('bkMinute').value) document.getElementById('bkMinute').value = '00';
        if (sessionBookingData && sessionBookingData.guide_id) {
            // Edit mode: pre-fill existing data
            document.getElementById('bkCompany').value = sessionBookingData.company_name || '';
            document.getElementById('bkJob').value = sessionBookingData.job_title || '';
            document.getElementById('bkHrName').value = sessionBookingData.hr_name || '';
            document.getElementById('bkHrPhone').value = sessionBookingData.hr_phone || '';
            document.getElementById('bkEmail').value = sessionBookingData.hr_email || '';
            document.getElementById('bkAddress').value = sessionBookingData.interview_address || '';
            setDateTimeFields(sessionBookingData.interview_time);
            document.getElementById('bkSubmitBtn').textContent = '更新提交';
        } else {
            // New booking mode
            document.getElementById('bkCompany').value = '';
            document.getElementById('bkJob').value = '';
            document.getElementById('bkHrName').value = '';
            document.getElementById('bkHrPhone').value = '';
            document.getElementById('bkEmail').value = '';
            document.getElementById('bkAddress').value = '';
            document.getElementById('bkDate').value = '';
            document.getElementById('bkSubmitBtn').textContent = '确认提交';
            // Pre-fill time from conversation if available
            if (pendingBookingTime) {
                setDateTimeFields(pendingBookingTime);
            }
        }
    }

    function closeBookingForm() {
        document.getElementById('bookingOverlay').style.display = 'none';
    }

    async function submitBooking() {
        var company = document.getElementById('bkCompany').value.trim();
        var job = document.getElementById('bkJob').value.trim();
        var hrName = document.getElementById('bkHrName').value.trim();
        var hrPhone = document.getElementById('bkHrPhone').value.trim();
        var email = document.getElementById('bkEmail').value.trim();
        var address = document.getElementById('bkAddress').value.trim();
        var time = buildDateTimeStr();

        var errorDiv = document.getElementById('bookingError');
        var successDiv = document.getElementById('bookingSuccess');
        errorDiv.style.display = 'none';
        successDiv.style.display = 'none';

        if (!company) { errorDiv.textContent = '请填写公司名称'; errorDiv.style.display = 'block'; return; }
        if (!job) { errorDiv.textContent = '请填写岗位名称'; errorDiv.style.display = 'block'; return; }
        if (!email) { errorDiv.textContent = '请填写联系邮箱'; errorDiv.style.display = 'block'; return; }
        if (!time) { errorDiv.textContent = '请选择面试时间'; errorDiv.style.display = 'block'; return; }
        if (new Date(time) <= new Date()) { errorDiv.textContent = '面试时间必须在当前时间之后'; errorDiv.style.display = 'block'; return; }

        document.getElementById('bkSubmitBtn').disabled = true;
        document.getElementById('bkSubmitBtn').textContent = '提交中...';

        try {
            var resp = await fetch(VB + '/api/booking', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    company_name: company,
                    job_title: job,
                    hr_name: hrName,
                    hr_phone: hrPhone,
                    hr_email: email,
                    interview_address: address,
                    interview_time: new Date(time).toISOString(),
                }),
            });
            var data = await resp.json();
            if (data.message || data.guide_id) {
                sessionBookingId = data.guide_id;
                sessionBookingData = {
                    guide_id: data.guide_id,
                    company_name: company,
                    job_title: job,
                    hr_name: hrName,
                    hr_phone: hrPhone,
                    hr_email: email,
                    interview_address: address,
                    interview_time: new Date(time).toISOString(),
                };
                addMessage('ai', '✅ 面试邀约已提交！信息已记录，我会查阅后通过邮箱给您回复。');
                updateBookingCardSubmitted();
                closeBookingForm();
            } else {
                errorDiv.textContent = data.error || '提交失败，请重试';
                errorDiv.style.display = 'block';
                document.getElementById('bkSubmitBtn').disabled = false;
                document.getElementById('bkSubmitBtn').textContent = '确认提交';
            }
        } catch (e) {
            errorDiv.textContent = '网络错误，请重试';
            errorDiv.style.display = 'block';
            document.getElementById('bkSubmitBtn').disabled = false;
            document.getElementById('bkSubmitBtn').textContent = '确认提交';
        }
    }

    // --- Map Picker ---
                var AMAP_API_KEY = '{{ _AMAP_API_KEY | safe }}';
                var mapPickerMap = null;
                var mapPickerMarker = null;
    var mapSelectedLng = null;
    var mapSelectedLat = null;
    var mapSelectedName = '';
    var mapUserCity = '';

    function tryAutoLocate() {
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(function(pos) {
                var lat = pos.coords.latitude, lng = pos.coords.longitude;
                if (mapPickerMap) {
                    mapPickerMap.setView([lat, lng], 14);
                    reverseGeocodeMap(lng, lat, true);
                }
            }, function() {
                // 定位失败，保持默认中心
            }, { enableHighAccuracy: false, timeout: 10000, maximumAge: 60000 });
        }
    }

    function openMapPicker() {
        document.getElementById('mapPickerOverlay').style.display = 'flex';
        document.getElementById('mapSearchResults').style.display = 'none';
        document.getElementById('mapSelectedAddress').style.display = 'none';
        document.getElementById('mapConfirmBtn').disabled = true;
        mapSelectedLng = null;
        mapSelectedLat = null;
        mapSelectedName = '';
        setTimeout(function() {
            initMapPicker();
            tryAutoLocate();
        }, 300);
    }

    function closeMapPicker() {
        document.getElementById('mapPickerOverlay').style.display = 'none';
        if (mapPickerMap) {
            mapPickerMap.remove();
            mapPickerMap = null;
        }
        mapPickerMarker = null;
    }

    function initMapPicker() {
        if (mapPickerMap) return;
        var container = document.getElementById('mapContainer');
        if (!container || container.offsetWidth === 0) { setTimeout(initMapPicker, 200); return; }
        var DEFAULT_CENTER = [39.90923, 116.397428];
        mapPickerMap = L.map('mapContainer', { center: DEFAULT_CENTER, zoom: 12, zoomControl: true });
        L.tileLayer('https://webrd01.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}', {
            attribution: '&copy; 高德地图', maxZoom: 18,
        }).addTo(mapPickerMap);
        mapPickerMap.on('click', function(e) {
            var lat = e.latlng.lat, lng = e.latlng.lng;
            reverseGeocodeMap(lng, lat);
        });
        // Fix map rendering after modal opens
        setTimeout(function() { mapPickerMap.invalidateSize(); }, 300);
    }

    async function reverseGeocodeMap(lng, lat, storeCity) {
        try {
            var resp = await fetch('https://restapi.amap.com/v3/geocode/regeo?key=' + AMAP_API_KEY + '&location=' + lng + ',' + lat + '&radius=1000&extensions=base');
            var data = await resp.json();
            var addr = (data.status === '1' && data.regeocode && (data.regeocode.formatted_address || data.regeocode.formattedAddress))
                ? (data.regeocode.formatted_address || data.regeocode.formattedAddress)
                : (lat.toFixed(6) + ',' + lng.toFixed(6));
            if (storeCity && data.status === '1' && data.regeocode && data.regeocode.addressComponent) {
                mapUserCity = data.regeocode.addressComponent.city || data.regeocode.addressComponent.province || '';
            }
            placeMapMarker(lat, lng, addr);
        } catch(e) {
            placeMapMarker(lat, lng, lat.toFixed(6) + ',' + lng.toFixed(6));
        }
    }

    function placeMapMarker(lat, lng, name) {
        if (mapPickerMarker && mapPickerMap) mapPickerMap.removeLayer(mapPickerMarker);
        if (mapPickerMap) {
            mapPickerMarker = L.marker([lat, lng]).addTo(mapPickerMap);
            mapPickerMarker.bindPopup(name);
        }
        mapSelectedLat = lat;
        mapSelectedLng = lng;
        mapSelectedName = name;
        document.getElementById('mapSelectedAddress').textContent = '📍 已选: ' + name;
        document.getElementById('mapSelectedAddress').style.display = 'block';
        document.getElementById('mapConfirmBtn').disabled = false;
    }

    async function mapSearch() {
        var keyword = document.getElementById('mapSearchKeyword').value.trim();
        if (!keyword) return;
        try {
            var searchUrl = 'https://restapi.amap.com/v3/place/text?key=' + AMAP_API_KEY + '&keywords=' + encodeURIComponent(keyword) + '&offset=10&page=1&extensions=base';
            if (mapUserCity) searchUrl += '&city=' + encodeURIComponent(mapUserCity);
            var resp = await fetch(searchUrl);
            var data = await resp.json();
            var resultsDiv = document.getElementById('mapSearchResults');
            resultsDiv.innerHTML = '';
            if (data.status === '1' && data.pois && data.pois.length > 0) {
                resultsDiv.style.display = 'block';
                data.pois.forEach(function(poi) {
                    var coords = poi.location.split(',').map(Number);
                    var item = document.createElement('div');
                    item.style.cssText = 'padding:8px 10px;cursor:pointer;border-bottom:1px solid var(--border-color);font-size:13px';
                    item.innerHTML = '<div style="font-weight:500">' + poi.name + '</div>' + (poi.address ? '<div style="font-size:12px;color:var(--text-muted)">' + poi.address + '</div>' : '');
                    item.onmouseenter = function(){this.style.background='var(--accent-light)'};
                    item.onmouseleave = function(){this.style.background='transparent'};
                    item.onclick = function() {
                        placeMapMarker(coords[1], coords[0], poi.name + (poi.address ? ' - ' + poi.address : ''));
                        if (mapPickerMap) mapPickerMap.setView([coords[1], coords[0]], 15);
                        resultsDiv.style.display = 'none';
                    };
                    resultsDiv.appendChild(item);
                });
            } else {
                resultsDiv.style.display = 'block';
                resultsDiv.innerHTML = '<div style="padding:10px;color:var(--text-muted);font-size:13px">未找到结果</div>';
            }
        } catch(e) {
            document.getElementById('mapSearchResults').style.display = 'block';
            document.getElementById('mapSearchResults').innerHTML = '<div style="padding:10px;color:var(--error-color);font-size:13px">搜索失败</div>';
        }
    }

    function confirmMapAddress() {
        if (mapSelectedName) {
            document.getElementById('bkAddress').value = mapSelectedName;
        }
        closeMapPicker();
    }

;
    </script>
</body>
</html>
"""

RESUME_PREVIEW_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>简历预览</title>
    <style>
        body { background: #f5f5f5; margin: 0; padding: 20px; font-family: system-ui, sans-serif; }
        .toolbar { display: flex; gap: 12px; justify-content: center; margin-bottom: 20px; }
        .btn { padding: 10px 24px; background: linear-gradient(135deg, #6366f1, #a78bfa); color: white; border: none; border-radius: 8px; cursor: pointer; font-size: 14px; }
        .btn-secondary { background: white; color: #333; border: 1px solid #ddd; }
        .preview-wrapper { display: flex; justify-content: center; }
    </style>
</head>
<body>
    <div class="toolbar">
        <button class="btn btn-secondary" onclick="window.close()">← 返回</button>
        <button class="btn" onclick="downloadResume()">📥 下载 PDF</button>
    </div>
    <div class="preview-wrapper" id="resumeContainer">
        <div style="color:#666;">加载中...</div>
    </div>
    <script>
        const VB = window.location.pathname.startsWith('/visitor/') ? '/visitor' : '';
        const urlParams = new URLSearchParams(window.location.search);
        const uid = urlParams.get('user_id') || '';
        let sessionId = (function(){try{var s=localStorage.getItem('visitor_session');if(s){var d=JSON.parse(s);if(Date.now()<d.expiry)return d.session_id}}catch(e){}return null})();
        let resumeData = null;
        async function loadResume() {
            try {
                const url = VB + '/api/resume-content' + (uid ? '?user_id=' + uid : '');
                const response = await fetch(url, {
                    headers: sessionId ? {"X-Session-ID": sessionId} : {}
                });
                if (response.ok) {
                    const data = await response.json();
                    if (data.html && data.html.startsWith('<')) {
                        resumeData = data;
                        let html = data.html;
                        if (data.css) html = '<style>' + data.css + '</style>' + html;
                        document.getElementById('resumeContainer').innerHTML = html;
                    } else {
                        document.getElementById('resumeContainer').innerHTML = '<div class="resume-text">' + escapeHtml(data.html || data.content || '') + '</div>';
                    }
                } else {
                    document.getElementById('resumeContainer').innerHTML = '<div class="error">简历加载失败</div>';
                }
            } catch (e) {
                document.getElementById('resumeContainer').innerHTML = '<div class="error">网络错误</div>';
            }
        }
        async function downloadResume() {
            if (!resumeData) return alert('请等待简历加载完成');
            var btn = document.querySelector('.btn[onclick*=\"downloadResume\"]');
            if (btn && btn.disabled) return;
            var origText = btn ? btn.textContent : '📥 下载 PDF';
            if (btn) { btn.disabled = true; btn.textContent = '⏳ 正在生成PDF...'; }
            const personal = resumeData.personal || {};
            const name = personal.name || '';
            const phone = personal.phone || '';
            const jobTitle = personal.jobTitle || '';
            const parts = [name, jobTitle, phone].filter(Boolean);
            const filename = parts.join('_') + '.pdf';
            try {
                const resp = await fetch(VB + '/api/export-pdf', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json', 'X-Session-ID': sessionId},
                    body: JSON.stringify({html: resumeData.html, css: resumeData.css || ''})
                });
                if (resp.ok) {
                    if (btn) btn.textContent = '⏳ 正在下载...';
                    const blob = await resp.blob();
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url; a.download = filename; a.click();
                    URL.revokeObjectURL(url);
                } else { alert('PDF生成失败'); if (btn) btn.textContent = origText; }
            } catch(e) { alert('下载失败: '+e.message); }
            if (btn) { btn.disabled = false; btn.textContent = origText; }
        }
        window.onload = loadResume;
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    """Root redirect to a default or show a user selection page."""
    return "请使用 /username 访问，如 /admin", 404

MAINTENANCE_PAGE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>系统升级中</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif;
            background: linear-gradient(135deg, #f5f7fa 0%, #e4e9f0 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .card {
            background: white;
            border-radius: 16px;
            padding: 60px 80px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.08);
            text-align: center;
            max-width: 480px;
        }
        .icon {
            width: 80px;
            height: 80px;
            margin: 0 auto 24px;
            background: #f0f0ff;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 36px;
        }
        h1 { font-size: 22px; color: #1e293b; margin-bottom: 12px; font-weight: 600; }
        p { color: #64748b; line-height: 1.8; font-size: 15px; }
    </style>
</head>
<body>
    <div class="card">
        <div class="icon">🔧</div>
        <h1>系统升级中</h1>
        <p>我们正在对系统进行升级维护，<br>暂时无法访问，请稍后再试。</p>
    </div>
</body>
</html>
"""

@app.route('/<username>')
def visitor_page(username: str):
    """Visitor page for a specific username."""
    try:
        resp = httpx.get(f"{BACKEND_URL}/api/user-by-username/{username}", timeout=5)
        if resp.status_code != 200 or not resp.json().get("exists"):
            return "用户不存在", 404
        user_id = resp.json()["user_id"]

        # Check if visitor access is enabled
        status_resp = httpx.get(f"{BACKEND_URL}/api/visitor-status", params={"user_id": user_id}, timeout=5)
        if status_resp.status_code == 200:
            status_data = status_resp.json()
            if not status_data.get("enabled", False):
                return MAINTENANCE_PAGE, 200
            has_password = status_data.get("has_password", False)
        else:
            has_password = True  # 保守起见，无法获取状态时默认需要口令
    except Exception:
        return "服务暂时不可用", 503
    return render_template_string(HTML_TEMPLATE, _AMAP_API_KEY=_AMAP_API_KEY, _USER_ID=user_id, _HAS_PASSWORD='true' if has_password else 'false')

@app.route('/verify', methods=['POST'])
def verify():
    password = request.json.get('password', '')
    user_id = request.json.get('user_id', '')
    # If no user_id in request, try to get from session (set during visitor_page)
    if not user_id and session.get('visitor_user_id'):
        user_id = session['visitor_user_id']
    try:
        payload = {"password": password, "client_ip": "127.0.0.1"}
        if user_id:
            payload["user_id"] = user_id
        response = httpx.post(f"{BACKEND_URL}/api/verify-password", json=payload, timeout=10)
        if response.status_code == 200:
            data = response.json()
            session.permanent = True
            session['session_id'] = data["session_id"]
            if user_id:
                session['visitor_user_id'] = user_id
            return {"success": True, "session_id": data["session_id"]}
        else:
            error = response.json().get("detail", "验证失败")
            return {"success": False, "message": error}
    except Exception as e:
        return {"success": False, "message": str(e)}

@app.route('/chat', methods=['POST'])
def chat():
    session_id = session.get('session_id') or request.headers.get('X-Session-ID')
    if not session_id:
        return {"response": "请先完成口令验证"}

    message = request.json.get('message')

    def generate():
        try:
            with httpx.stream("POST", f"{BACKEND_URL}/api/chat", json={"message": message}, headers={"X-Session-ID": session_id}, timeout=180) as response:
                for chunk in response.iter_bytes(chunk_size=1):
                    if chunk:
                        yield chunk
        except Exception as e:
            yield f"连接错误: {str(e)}".encode('utf-8')

    return app.response_class(generate(), content_type='text/plain')

def _get_session_id():
    """Get session ID from request header or Flask session cookie"""
    sid = request.headers.get("X-Session-ID")
    if sid:
        return sid
    return session.get("session_id")

@app.route('/api/check-session')
def check_session():
    sid = _get_session_id()
    if not sid:
        return {"valid": False, "error": "未登录"}, 401
    try:
        resp = httpx.get(f"{BACKEND_URL}/api/check-session", headers={"X-Session-ID": sid}, timeout=10)
        if resp.status_code == 200:
            return {"valid": True}
        return {"valid": False}, 401
    except:
        return {"valid": False}, 500

@app.route('/api/welcome-config')
def welcome_config():
    sid = _get_session_id()
    if not sid:
        return {"error": "请先完成口令验证"}, 401
    try:
        response = httpx.get(f"{BACKEND_URL}/api/welcome-config", headers={"X-Session-ID": sid}, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": "获取配置失败"}, response.status_code
    except Exception as e:
        return {"error": str(e)}, 500

@app.route('/api/booking-suggestion')
def booking_suggestion():
    """Poll for booking suggestion from visitor router"""
    sid = _get_session_id()
    if not sid:
        return {"suggest_booking": False, "booking_intent": None}
    try:
        resp = httpx.get(f"{BACKEND_URL}/api/booking-suggestion", headers={"X-Session-ID": sid}, timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return {"suggest_booking": False, "booking_intent": None}


@app.route('/api/booking/<session_id>')
def get_booking(session_id):
    try:
        resp = httpx.get(f"{BACKEND_URL}/api/booking/{session_id}", timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return {"guide_id": None, "status": "none"}


@app.route('/api/booking', methods=['POST'])
def submit_booking():
    """Submit interview booking form"""
    sid = _get_session_id()
    if not sid:
        return {"success": False, "error": "未登录"}, 401
    data = request.json or {}
    data["session_id"] = sid
    try:
        resp = httpx.post(f"{BACKEND_URL}/api/booking", json=data, timeout=30)
        if resp.status_code == 200:
            return resp.json()
        return {"success": False, "error": "提交失败"}
    except Exception as e:
        return {"success": False, "error": str(e)}, 500


@app.route('/portfolio-preview')
def portfolio_preview():
    session_id = session.get('session_id') or request.headers.get('X-Session-ID') or request.args.get('session_id')
    if not session_id:
        return redirect('/')
    style = request.args.get('style', 'editorial')
    user_id = request.args.get('user_id', session.get('visitor_user_id', ''))
    try:
        sid = session_id
        params = {"style": style}
        if user_id:
            params["user_id"] = user_id
        response = httpx.get(
            f"{BACKEND_URL}/admin/portfolio/visitor-preview",
            params=params,
            headers={"X-Session-ID": sid},
            timeout=10,
        )
        if response.status_code == 200:
            return response.text, 200, {'Content-Type': 'text/html; charset=utf-8'}
        else:
            return "<h1>加载失败</h1>", 500
    except Exception as e:
        return f"<h1>错误</h1><p>{e}</p>", 500

@app.route('/resume-preview')
def resume_preview():
    return render_template_string(RESUME_PREVIEW_TEMPLATE)

@app.route('/api/resume-content')
def resume_content():
    session_id = session.get('session_id') or request.headers.get('X-Session-ID')
    if not session_id:
        return {"content": "请先完成口令验证"}, 401
    user_id = request.args.get('user_id', session.get('visitor_user_id', ''))
    try:
        url = f"{BACKEND_URL}/api/resume/preview"
        params = {}
        if user_id:
            # Backend resume/preview uses session_id to look up user_id
            pass  # Already fixed to use session
        response = httpx.get(url, params=params, headers={"X-Session-ID": session_id}, timeout=10)
        if response.status_code == 200:
            data = response.json()
            import json as _vj
            personal = {}
            content_raw = data.get('content', '{}')
            if content_raw:
                try:
                    personal = _vj.loads(content_raw).get('personal', {})
                except Exception:
                    personal = {}
            return {"html": data.get('html', ''), "css": data.get('css', ''), "personal": personal}
        else:
            return {"html": "简历加载失败", "css": "", "personal": {}}
    except Exception as e:
        return {"html": str(e), "css": "", "personal": {}}

@app.route('/download-resume')
def download_resume():
    session_id = session.get('session_id') or request.headers.get('X-Session-ID')
    if not session_id:
        return "请先完成口令验证", 401
    try:
        response = httpx.get(f"{BACKEND_URL}/api/resume/download", headers={"X-Session-ID": session_id}, timeout=30)
        if response.status_code == 200:
            content_disp = response.headers.get("Content-Disposition", "attachment; filename=resume.pdf")
            return response.content, 200, {'Content-Type': 'application/pdf', 'Content-Disposition': content_disp}
        else:
            return "下载失败", 400
    except Exception as e:
        return str(e), 500

HR_RESUME_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>简历查看 - HR端</title>
    <meta charset="UTF-8">
    <style>
        body { margin: 0; padding: 20px; background: #e9ecef; text-align: center; font-family: 'Segoe UI', 'Roboto', 'Microsoft YaHei', sans-serif; }
        .resume-container { max-width: 210mm; margin: 0 auto; background: white; box-shadow: 0 10px 30px rgba(0,0,0,0.1); }
        .toolbar { margin-bottom: 20px; }
        button { background: #2c7da0; color: white; border: none; padding: 12px 28px; border-radius: 40px; cursor: pointer; font-size: 16px; }
        button:hover { background: #1f5e7a; }
        .back-link { display: inline-block; margin-left: 16px; color: #6c757d; text-decoration: none; }
        .back-link:hover { text-decoration: underline; }
        .resume-card { width: 100%; background: white; padding: 10mm 12mm; line-height: 1.5; color: #1e2a3a; }
        .resume-card h1 { font-size: 28px; margin-bottom: 8px; color: #0f3b5c; }
        .resume-card h2 { font-size: 18px; border-left: 4px solid #2c7da0; padding-left: 10px; margin: 20px 0 12px 0; color: #0f3b5c; }
        .contact { display: flex; gap: 20px; font-size: 14px; color: #2c3e50; margin-bottom: 12px; flex-wrap: wrap; }
        .item-header { display: flex; justify-content: space-between; font-weight: 600; margin: 12px 0 6px 0; flex-wrap: wrap; }
        .company, .school { color: #2c7da0; }
        .date { color: #6c757d; font-weight: normal; font-size: 0.9em; }
        .resume-card ul { margin: 4px 0 8px 20px; padding-left: 0; }
        .resume-card li { margin-bottom: 6px; text-align: justify; }
        .skills-list { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }
        .skill-tag { background: #e9ecef; padding: 4px 12px; border-radius: 20px; font-size: 13px; }
        .tech { font-size: 13px; color: #495057; margin-top: 4px; }
        .summary { text-align: justify; font-size: 14px; color: #495057; }
        .error-message { color: #dc3545; font-size: 14px; padding: 20px; }
        @media print {
            body { margin: 0; padding: 0; background: white; }
            .toolbar, button, .back-link { display: none; }
            .resume-container { box-shadow: none; margin: 0; }
            .resume-card { padding: 10mm; }
        }
    </style>
</head>
<body>
<div class="toolbar">
    <button id="downloadBtn">📄 下载简历 PDF</button>
    <a href="/" class="back-link">← 返回聊天</a>
</div>
<div class="resume-container" id="resumeContent">
    <div class="resume-card" id="resumeCard">
        <div id="resumeContentArea">加载中...</div>
    </div>
</div>
<script>
    function renderResumeToHTML(resume) {
        if (!resume) return '<p class="error-message">简历数据为空</p>';
        
        const personal = resume.personal || {};
        const name = personal.name || '';
        const phone = personal.phone || '';
        const email = personal.email || '';
        const city = personal.city || '';
        const jobTitle = personal.jobTitle || '';
        
        let html = '<div class="resume-card"><h1>' + name + '</h1>';
        
        let contacts = [];
        if (phone) contacts.push('手机: ' + phone);
        if (email) contacts.push('邮箱: ' + email);
        if (city) contacts.push('城市: ' + city);
        if (jobTitle) contacts.push('求职意向: ' + jobTitle);
        if (contacts.length > 0) html += '<div class="contact">' + contacts.join(', ') + '</div>';
        
        if (resume.summary) {
            html += '<h2>个人概述</h2><p class="summary">' + resume.summary + '</p>';
        }
        
        if (resume.education && resume.education.length > 0) {
            html += '<h2>教育背景</h2>';
            resume.education.forEach(edu => {
                html += '<div class="item-header"><span class="school">' + (edu.school || '') + (edu.major ? ' | ' + edu.major : '') + ' ' + (edu.degree || '') + '</span>';
                if (edu.year) html += '<span class="date">' + edu.year + '</span>';
                html += '</div>';
            });
        }
        
        if (resume.work && resume.work.length > 0) {
            html += '<h2>工作经历</h2>';
            resume.work.forEach(exp => {
                html += '<div class="item-header"><span class="company">' + (exp.company || '') + ' | ' + (exp.title || '') + '</span>';
                if (exp.startDate) html += '<span class="date">' + (exp.startDate || '') + (exp.endDate ? ' - ' + exp.endDate : '') + '</span>';
                html += '</div><ul>';
                if (exp.highlights) exp.highlights.forEach(h => html += '<li>' + h + '</li>');
                html += '</ul>';
            });
        }
        
        if (resume.projects && resume.projects.length > 0) {
            html += '<h2>项目经验</h2>';
            resume.projects.forEach(proj => {
                html += '<div class="item-header"><span>' + (proj.name || '') + (proj.role ? ' | ' + proj.role : '') + '</span>';
                if (proj.date) html += '<span class="date">' + proj.date + '</span>';
                html += '</div><ul>';
                if (proj.highlights) proj.highlights.forEach(h => html += '<li>' + h + '</li>');
                html += '</ul>';
                if (proj.tech) html += '<p class="tech">技术: ' + proj.tech + '</p>';
            });
        }
        
        if (resume.skills && resume.skills.length > 0) {
            // Check if new structured format (has category) or flat list
            if (typeof resume.skills[0] === 'object' && resume.skills[0].category) {
                resume.skills.forEach(function(group) {
                    if (group.category) {
                        html += '<h3 style="font-size:14px;margin:10px 0 4px;color:#333;">' + group.category + '</h3>';
                    }
                    (group.items || []).forEach(function(item) {
                        if (item.label) {
                            html += '<div style="margin:2px 0;font-size:13px;"><strong>' + item.label + '</strong>';
                            if (item.detail) html += '：' + item.detail;
                            html += '</div>';
                        }
                    });
                });
            } else {
                html += '<h2>专业技能</h2><div class="skills-list">';
                resume.skills.forEach(function(s) { html += '<span class="skill-tag">' + s + '</span>'; });
                html += '</div>';
            }
        }
        
        html += '</div>';
        return html;
    }

    async function loadResume() {
        try {
            const response = await fetch(VB + '/api/resume-full', {
                headers: {'X-Session-ID': sessionId}
            });
            const data = await response.json();
            
            if (data.error) {
                document.getElementById('resumeContentArea').innerHTML = '<p class="error-message">' + data.error + '</p>';
                return;
            }
            
            window._resumePersonal = data.personal || {};
            
            let html = '';
            if (data.html) {
                html = data.html;
            } else if (data.json) {
                html = renderResumeToHTML(data.json);
            } else if (data.content) {
                try {
                    const jsonData = JSON.parse(data.content);
                    html = renderResumeToHTML(jsonData);
                } catch(e) {
                    html = '<div class="resume-card"><pre>' + data.content + '</pre></div>';
                }
            }
            
            if (html) {
                document.getElementById('resumeContentArea').innerHTML = html;
            } else {
                document.getElementById('resumeContentArea').innerHTML = '<p class="error-message">简历加载失败</p>';
            }
        } catch(e) {
            document.getElementById('resumeContentArea').innerHTML = '<p class="error-message">简历加载失败: ' + e.message + '</p>';
        }
    }

    document.getElementById('downloadBtn').onclick = async () => {
        var btn = document.getElementById('downloadBtn');
        if (btn.disabled) return;
        btn.disabled = true;
        btn.textContent = '⏳ 正在生成PDF...';
        const htmlContent = document.getElementById('resumeContentArea').innerHTML;
        const cssContent = `.resume-card { width: 100%; max-width: 180mm; margin: 0 auto; background: white; padding: 5mm 10mm 10mm 10mm; font-family: 'Segoe UI', 'Roboto', 'Microsoft YaHei', sans-serif; line-height: 1.6; color: #1e2a3a; } h1 { font-size: 28px; margin-bottom: 8px; color: #0f3b5c; } h2 { font-size: 18px; border-left: 4px solid #2c7da0; padding-left: 10px; margin: 20px 0 12px 0; color: #0f3b5c; } .contact { display: flex; gap: 20px; font-size: 14px; color: #2c3e50; margin-bottom: 12px; flex-wrap: wrap; } .item-header { display: flex; justify-content: space-between; font-weight: 600; margin: 12px 0 6px 0; flex-wrap: wrap; } .company, .school { color: #2c7da0; } .date { color: #6c757d; font-weight: normal; font-size: 0.9em; } ul { margin: 4px 0 8px 20px; padding-left: 0; } li { margin-bottom: 6px; text-align: justify; } .skills-list { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; } .skill-tag { background: #e9ecef; padding: 4px 12px; border-radius: 20px; font-size: 13px; } .tech { font-size: 13px; color: #495057; margin-top: 4px; } .summary { text-align: justify; font-size: 14px; color: #495057; }`;
        
        const personal = window._resumePersonal || {};
        const name = personal.name || '';
        const phone = personal.phone || '';
        const jobTitle = personal.jobTitle || '';
        const parts = [name, jobTitle, phone].filter(Boolean);
        const filename = parts.join('_') + '.pdf';
        
        try {
            const response = await fetch(VB + '/api/export-pdf', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Session-ID': sessionId
                },
                body: JSON.stringify({ html: htmlContent, css: cssContent })
            });
            if (response.ok) {
                const blob = await response.blob();
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = filename;
                a.click();
                URL.revokeObjectURL(url);
            } else {
                alert('PDF生成失败');
            }
        } catch(e) {
            alert('PDF生成失败: ' + e.message);
        }
        btn.disabled = false;
        btn.textContent = '📄 下载简历 PDF';
    };

    loadResume();
</script>
</body>
</html>
"""

@app.route('/hr-resume')
def hr_resume():
    if 'session_id' not in session:
        return redirect('/')
    return render_template_string(HR_RESUME_TEMPLATE)

@app.route('/api/resume-full')
def api_resume_full():
    sid_resume = _get_session_id()
    if not sid_resume:
        return {"error": "请先完成口令验证"}, 401
    try:
        response = httpx.get(f"{BACKEND_URL}/api/resume/preview", headers={"X-Session-ID": sid_resume}, timeout=10)
        if response.status_code == 200:
            data = response.json()
            import json as _vj
            personal = {}
            content_raw = data.get('content', '{}')
            if content_raw:
                try:
                    personal = _vj.loads(content_raw).get('personal', {})
                except Exception:
                    personal = {}
            return {"html": data.get('html', ''), "personal": personal}
        else:
            return {"error": "获取简历失败"}
    except Exception as e:
        return {"error": str(e)}

@app.route('/favicon.svg')
def favicon():
    favicon_path = os.path.join(os.path.dirname(__file__), 'admin', 'public', 'favicon.svg')
    if os.path.exists(favicon_path):
        return open(favicon_path, 'rb').read(), 200, {'Content-Type': 'image/svg+xml'}
    return '', 404

@app.route('/api/export-pdf', methods=['POST'])
def proxy_export_pdf():
    session_id = session.get('session_id') or request.headers.get('X-Session-ID')
    if not session_id:
        return {"error": "请先完成口令验证"}, 401
    data = request.get_json()
    try:
        response = httpx.post(
            f"{BACKEND_URL}/api/export-pdf",
            json=data,
            headers={"X-Session-ID": session_id},
            timeout=60
        )
        if response.status_code == 200:
            return response.content, 200, {'Content-Type': 'application/pdf', 'Content-Disposition': 'attachment; filename=resume.pdf'}
        else:
            return {"error": f"PDF生成失败: {response.text}"}, response.status_code
    except Exception as e:
        return {"error": str(e)}, 500

if __name__ == '__main__':
    VISITOR_PORT = int(os.getenv('VISITOR_PORT', 51670))
    import platform
    if platform.system() == 'Windows':
        app.run(host='0.0.0.0', port=VISITOR_PORT, debug=True)
    else:
        from waitress import serve
        serve(app, host='0.0.0.0', port=VISITOR_PORT, threads=16, connection_limit=100)