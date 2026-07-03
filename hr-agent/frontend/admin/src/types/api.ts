// ──────────────────────────────────────────────────────
// Auto-generated TypeScript types mirroring backend Pydantic models
// Backend: schemas/admin_schemas.py + routers/admin.py + routers/agent.py
// ──────────────────────────────────────────────────────

// ── Generic ───────────────────────────────────────────

export interface MessageResponse {
  message: string;
}

export interface IdResponse {
  id: number;
}

// ── Auth ──────────────────────────────────────────────

export interface LoginResponse {
  access_token: string;
  token_type: string;
  role?: string;
  user_id?: string;
  username?: string;
  display_name?: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  role: string;
  user_id: string;
  username: string;
}

export interface UserInfoResponse {
  id: string;
  username: string;
  email: string;
  role: string;
  is_active: boolean;
  created_at: string | null;
}

// ── Config ────────────────────────────────────────────

export interface ConfigResponse {
  max_sessions: number;
  session_timeout_minutes: number;
  resume_show: boolean;
  portfolio_show: boolean;
  visitor_enabled?: boolean;
  visitor_password: string;
  llm_provider: string;
  llm_model: string;
  llm_api_key: string;
  embedding_provider: string;
  embedding_model: string;
  embedding_api_key: string;
  appendix_knowledge_dir: string;
  visitor_llm_provider: string;
  visitor_llm_model: string;
  visitor_llm_api_key: string;
  longcat_api_key: string;
  siliconflow_api_key: string;
  deepseek_api_key: string;
  openai_api_key: string;
  // ── Admin search / API Keys ──
  tavily_api_key: string;
  firecrawl_api_key: string;
  anysearch_api_key: string;
  amap_api_key: string;
  // ── Visitor-side API Keys ──
  visitor_tavily_api_key: string;
  visitor_amap_api_key: string;
  // ── Intent recognition LLM ──
  intent_llm_provider: string;
  intent_llm_model: string;
  intent_llm_api_key: string;
}

export interface TestLLMRequest {
  provider: string;
  model: string;
  api_key: string;
  base_url: string;
}

export interface TestEmbeddingRequest {
  api_key: string;
  base_url: string;
  model: string;
}

// ── Prompts ───────────────────────────────────────────

export interface PromptResponse {
  content: string;
}

export interface PromptListItem {
  key: string;
  version: number;
  description: string;
  updated_at?: string;
}

export interface PromptVersion {
  id: number;
  version: number;
  content: string;
  change_log: string;
  created_by: string;
  created_at: string;
}

export interface PromptDetail {
  key: string;
  version: number;
  description: string;
  content: string;
  updated_at?: string;
  history: PromptVersion[];
}

// ── Welcome Config ────────────────────────────────────

export interface WelcomeConfigResponse {
  greeting: string;
  self_intro: string;
  initial_message: string;
  quick_questions: string;
}

export interface GenerateIntroResponse {
  self_intro: string;
  initial_message: string;
}

// ── Applicant Profile ─────────────────────────────────

export interface ApplicantProfileResponse {
  home_address: string;
  home_lng: number | null;
  home_lat: number | null;
  default_travel_mode: string;
  interview_duration_min: number;
  min_gap_min: number;
  max_daily_interviews: number;
  workday_start: string;
  workday_end: string;
}

export interface ApplicantProfileUpdate {
  home_address?: string;
  home_lng?: number | null;
  home_lat?: number | null;
  default_travel_mode?: string;
  interview_duration_min?: number;
  min_gap_min?: number;
  max_daily_interviews?: number;
  workday_start?: string;
  workday_end?: string;
}

export interface ApplicantProfileUpdateResponse {
  message: string;
  profile: ApplicantProfileResponse;
}

// ── Interview Guide ───────────────────────────────────

export interface InterviewGuideResponse {
  id: number;
  company_name: string;
  company_description: string;
  job_title: string;
  salary: string;
  hr_name: string;
  hr_phone: string;
  hr_email: string;
  interview_address: string;
  interview_address_lng: number | null;
  interview_address_lat: number | null;
  address_type: string;
  video_link: string;
  interview_round: string;
  interview_time: string | null;
  status: string;
  result: string;
  commute_duration_min: number | null;
  commute_distance_km: number | null;
  conflict_warnings: unknown[];
  guide_content: Record<string, unknown>;
  generated_report_id: number | null;
  jd_text: string;
  jd_parsed: Record<string, unknown>;
  generated_report_md: string;
  source: string;
  session_id: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface InterviewGuideCreate {
  company_name: string;
  job_title: string;
  salary?: string;
  interview_time: string;
  company_description?: string;
  hr_name?: string;
  hr_phone?: string;
  hr_email?: string;
  interview_address?: string;
  interview_address_lng?: number | null;
  interview_address_lat?: number | null;
  address_type?: string;
  video_link?: string;
  interview_round?: string;
  result?: string;
  jd_text?: string;
  source?: string;
  session_id?: string | null;
}

export interface InterviewGuideUpdate {
  company_name?: string;
  company_description?: string;
  job_title?: string;
  salary?: string;
  hr_name?: string;
  hr_phone?: string;
  hr_email?: string;
  interview_address?: string;
  interview_address_lng?: number | null;
  interview_address_lat?: number | null;
  address_type?: string;
  video_link?: string;
  interview_round?: string;
  interview_time?: string;
  status?: string;
  result?: string;
  jd_text?: string;
  jd_parsed?: string;
}

export interface InterviewGuideListResponse {
  total: number;
  page: number;
  size: number;
  items: InterviewGuideResponse[];
}

export interface InterviewGuideDeleteResponse {
  message: string;
}

// ── Report Generation ─────────────────────────────────

export interface GenerateReportResponse {
  task_id: number;
  status: string;
}

export interface TaskStatusResponse {
  status: string;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  pdf_path: string | null;
}

export interface JdParseResponse {
  summary: string;
  requirements: unknown[];
  responsibilities: unknown[];
  keywords: string[];
}

// ── Stats ─────────────────────────────────────────────

export interface QuestionStatsItem {
  question: string;
  count: number;
}

export interface StatsResponse {
  total_sessions: number;
  total_conversations: number;
  total_chat_questions: number;
  total_resume_downloads: number;
  total_portfolio_visits: number;
  daily_new_users: number;
  conversations_today: number;
  total_knowledge_entries: number;
  today_new_knowledge: number;
  top_questions: unknown[];
}

export interface QuestionStatsResponse {
  questions: QuestionStatsItem[];
}

export interface StatsClearResponse {
  message: string;
}

export interface QuestionAddResponse {
  message: string;
}

// ── Sessions ──────────────────────────────────────────

export interface SessionSummary {
  id: string;
  created_at: string | null;
  last_active: string | null;
  is_active: boolean;
}

export interface SessionListResponse {
  sessions: SessionSummary[];
}

export interface ConversationMessage {
  role: string;
  content: string;
  created_at: string | null;
}

export interface ConversationListResponse {
  conversations: ConversationMessage[];
}

// ── Knowledge Base ────────────────────────────────────

export interface KnowledgeCategoryResponse {
  category: string;
  content: string;
}

export interface KnowledgeStructuredResponse {
  category: string;
  data: Record<string, unknown>;
}

export interface KnowledgePreviewResponse {
  success: boolean;
  message: string;
  category: string;
  changes: unknown[];
}

export interface KnowledgeConfirmResponse {
  success: boolean;
  message: string;
}

export interface KnowledgePreviewRequest {
  category: string;
  content: string;
  action: string;
}

export interface KnowledgeConfirmRequest {
  preview_id: string;
}

// ── Appendix ──────────────────────────────────────────

export interface AppendixDirsResponse {
  dirs: string[];
}

export interface AppendixInfoResponse {
  configured_dirs: string[];
  doc_count: number;
  chunk_count: number;
}

export interface AppendixUploadResponse {
  message: string;
  count: number;
  files: number;
}

export interface AppendixRecordsResponse {
  records: unknown[];
}

export interface AddAppendixPathRequest {
  path: string;
}

export interface RemoveAppendixDirRequest {
  path: string;
}

export interface ListDirectoriesRequest {
  path: string;
}

export interface DirectoriesResponse {
  entries: unknown[];
  parent: string;
  error: string;
}

// ── Resume ────────────────────────────────────────────

export interface ResumeListItem {
  id: number;
  title: string;
  job_title: string;
  is_default: boolean;
  created_at: string | null;
}

export interface ResumeListResponse {
  resumes: ResumeListItem[];
}

export interface ResumeDetailResponse {
  id: number;
  title: string;
  content: string;
  created_at: string | null;
  is_default: boolean;
}

export interface ResumeGenerateResponse {
  message: string;
  resume_id: number;
}

export interface ResumeStatusResponse {
  resume_show: boolean;
}

export interface ResumeToggleResponse {
  message: string;
  resume_show: boolean;
}

export interface ResumePreviewResponse {
  html: string;
  css: string;
  content: string;
}

export interface ResumeTemplateResponse {
  message: string;
  template: string;
}

export interface TemplatesResponse {
  templates: string[];
}

export interface GenerateResumeWithTemplateRequest {
  raw_text: string;
  target_job: string;
  template: string;
}

export interface UpdateResumeTemplateRequest {
  template: string;
}

// ── Portfolio ─────────────────────────────────────────

export interface PortfolioConfig {
  style: string;
  blocks_order: string[];
  blocks_hidden: string[];
  contact_enabled: { email: boolean; phone: boolean; github: boolean; wechat: boolean };
  chat_enabled: boolean;
  chat_position: string;
}

export interface KnowledgeData {
  personal_info: Record<string, unknown>;
  education: { education_list: unknown[] };
  work_experience: { work_list: unknown[] };
  projects: { project_list: unknown[] };
  skills: {
    skill_groups: Record<string, string[]>;
    skill_sections?: Array<{ title: string; items: Array<{ name: string; desc?: string }> }>;
  };
  faq: { faq_list: unknown[] };
}

export interface PortfolioPreviewResponse {
  config: PortfolioConfig;
  knowledge: KnowledgeData;
}

export interface PortfolioStatusResponse {
  portfolio_show: boolean;
  chat_enabled: boolean;
}

export interface PortfolioToggleResponse {
  message: string;
  portfolio_show: boolean;
}

export interface StyleOption {
  id: string;
  name: string;
  description: string;
}

export interface ExportRequest {
  style: string;
}

// ── Jobs ──────────────────────────────────────────────

export interface CrawlJobItem {
  platform: string;
  title: string;
  company: string;
  city: string;
  salary: string;
  jd_text: string;
  jd_url: string;
  work_address: string;
}

export interface CrawlJobsRequest {
  keywords: string;
  city: string;
  platform: string;
  max_count: number;
  sort: string;
  threshold: number;
}

export interface CrawlSubmitRequest {
  jobs: CrawlJobItem[];
}

export interface BatchDeleteJobsRequest {
  ids: number[];
}

export interface JobListItem {
  id: number;
  platform: string;
  title: string;
  company: string;
  city: string;
  salary: string;
  jd_url: string;
  work_address: string;
  match_score: number | null;
  match_detail: Record<string, unknown> | null;
  status: string;
  created_at: string | null;
}

export interface JobListResponse {
  jobs: JobListItem[];
}

export interface JobDetailResponse {
  id: number;
  platform: string;
  title: string;
  company: string;
  city: string;
  salary: string;
  jd_text: string;
  jd_url: string;
  jd_parsed: Record<string, unknown> | null;
  work_address: string;
  match_score: number | null;
  match_detail: Record<string, unknown> | null;
  status: string;
  created_at: string | null;
  updated_at: string | null;
}

export interface JobAddResponse {
  message: string;
  id: number;
}

export interface JobMatchResponse {
  message: string;
  score: number;
  detail: Record<string, unknown>;
}

export interface JobBatchMatchResponse {
  message: string;
  results: unknown[];
}

export interface CrawlJobsResponse {
  message: string;
  count: number;
  jobs: JobListItem[];
  skipped_dedup: number;
  skipped_expired: number;
}

export interface CrawlSubmitResponse {
  message: string;
  count: number;
}

// ── Agent ─────────────────────────────────────────────

export interface AgentStep {
  type: 'tool_call' | 'tool_result';
  tool?: string;
  args?: Record<string, unknown>;
  result_preview?: string;
  /** Marked true when the tool is in SENSITIVE_TOOLS */
  sensitive?: boolean;
  /** Present on tool_call when user confirmation should be collected first */
  requires_confirmation?: boolean;
}

export interface AgentChatResponse {
  response: string;
  steps: AgentStep[];
  resume_id: number | null;
}

export interface AgentChatRequest {
  message: string;
  session_id?: string | null;
}

export interface ClearRequest {
  session_id: string;
}

// ── SSE Event Types ───────────────────────────────────

export interface SSEToolCallEvent {
  type: 'tool_call';
  data: {
    tool: string;
    args: Record<string, unknown>;
    sensitive?: boolean;
    requires_confirmation?: boolean;
  };
}

export interface SSEToolResultEvent {
  type: 'tool_result';
  data: {
    tool: string;
    result_preview: string;
  };
}

export interface SSETextEvent {
  type: 'text';
  data: {
    content: string;
  };
}

export interface SSEErrorEvent {
  type: 'error';
  data: {
    message: string;
  };
}

export interface SSEStatusEvent {
  type: 'status';
  data: {
    message: string;
  };
}

export interface SSEDoneEvent {
  type: 'done';
  data: {
    response: string;
  };
}

export type SSEEvent =
  | SSEToolCallEvent
  | SSEToolResultEvent
  | SSETextEvent
  | SSEErrorEvent
  | SSEStatusEvent
  | SSEDoneEvent;
