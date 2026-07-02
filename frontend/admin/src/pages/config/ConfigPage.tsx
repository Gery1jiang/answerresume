import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { Card, Form, Input, InputNumber, Button, message, Space, Select, Radio } from 'antd';
import { SunOutlined, MoonOutlined, LaptopOutlined } from '@ant-design/icons';
import {
  getConfig, updateConfig, testLlm, testEmbedding, changePassword,
} from '../../api/config';
import PromptsManagePage from '../prompts/PromptsManagePage';

const { TextArea } = Input;

const PROVIDERS: Record<string, { api_base: string; models?: string[]; note: string }> = {
  SiliconFlow: { api_base: 'https://api.siliconflow.cn/v1', models: ['deepseek-ai/DeepSeek-V3', 'deepseek-ai/DeepSeek-R1', 'Pro/deepseek-ai/DeepSeek-V3', 'Qwen/Qwen2.5-72B-Instruct', 'Qwen/Qwen2.5-7B-Instruct'], note: '硅基流动' },
  DeepSeek: { api_base: 'https://api.deepseek.com/v1', models: ['deepseek-v4-pro', 'deepseek-v4-flash', 'deepseek-chat', 'deepseek-reasoner'], note: 'DeepSeek' },
  LongCat: { api_base: 'https://api.longcat.chat/openai/v1', models: ['LongCat-2.0', 'LongCat-Flash-Chat', 'LongCat-Pro-Chat', 'LongCat-Ultra-Chat', 'LongCat-Nova-Chat', 'LongCat-Turbo-Chat'], note: '默认中转平台' },
  OpenAI: { api_base: 'https://api.openai.com/v1', models: ['gpt-5.5', 'gpt-5.4', 'gpt-4.1', 'gpt-4o', 'gpt-4o-mini', 'o3', 'o4-mini'], note: 'OpenAI' },
  阿里云: { api_base: 'https://dashscope.aliyuncs.com/compatible-mode/v1', models: ['qwen3.5-plus', 'qwen3-max', 'qwen3-coder-plus', 'qwen3-coder-next', 'qwen-plus', 'qwen-turbo'], note: '阿里云（通义千问）' },
  百度智能云: { api_base: 'https://qianfan.baidubce.com/v2', models: ['ernie-4.5', 'ernie-x1', 'ernie-4.0', 'ernie-3.5', 'ernie-speed', 'ernie-lite'], note: '百度智能云（文心）' },
  字节云: { api_base: 'https://ark.cn-beijing.volces.com/api/v3', note: '字节云（火山引擎）- 需在控制台创建接入点(Endpoint)后填入接入点ID作为模型名' },
  腾讯云: { api_base: 'https://hunyuan.tencentcs.com/v2', models: ['hunyuan-turbos-latest', 'hunyuan-pro', 'hunyuan-standard', 'hunyuan-lite'], note: '腾讯云（混元）' },
  智谱AI: { api_base: 'https://open.bigmodel.cn/api/paas/v4', models: ['glm-5', 'glm-4.5', 'glm-4.5-air', 'glm-4-plus', 'glm-4-flash'], note: '智谱 AI（GLM）' },
  百川智能: { api_base: 'https://api.baichuan-ai.com/v1', models: ['Baichuan4', 'Baichuan3', 'Baichuan2'], note: '百川智能' },
  月之暗面: { api_base: 'https://api.moonshot.cn/v1', models: ['moonshot-v1-8k', 'moonshot-v1-32k', 'moonshot-v1-128k'], note: '月之暗面（Moonshot）' },
  Anthropic: { api_base: 'https://api.anthropic.com/v1', models: ['claude-opus-4-8', 'claude-sonnet-4-6', 'claude-haiku-4-5'], note: 'Anthropic（Claude）' },
  Google: { api_base: 'https://generativelanguage.googleapis.com/v1beta', models: ['gemini-3.5-flash', 'gemini-2.5-pro', 'gemini-2.5-flash', 'gemini-2.0-flash'], note: 'Google（Gemini）' },
};

interface Props {
  themeMode: 'system' | 'light' | 'dark';
  onThemeModeChange: (m: 'system' | 'light' | 'dark') => void;
}

interface Props {
  themeMode: 'system' | 'light' | 'dark';
  onThemeModeChange: (m: 'system' | 'light' | 'dark') => void;
}

const SERVICE_TABS: Record<string, { label: string }> = {
  service: { label: '管理端配置' },
  visitor: { label: '访客端配置' },
  prompt: { label: '提示词管理' },
};

export default function ConfigPage({ themeMode, onThemeModeChange }: Props) {
  const { tab = 'service' } = useParams();
  const [baseForm] = Form.useForm();
  const [llmForm] = Form.useForm();
  const [embedForm] = Form.useForm();
  const [visitorLlmForm] = Form.useForm();
  const [searchForm] = Form.useForm();
  const [visitorKeyForm] = Form.useForm();
  const [pwForm] = Form.useForm();
  const [llmTesting, setLlmTesting] = useState(false);
  const [embedTesting, setEmbedTesting] = useState(false);
  const [baseConfig, setBaseConfig] = useState<any>(null);
  const [llmProvider, setLlmProvider] = useState('DeepSeek');
  const [visitorProvider, setVisitorProvider] = useState('DeepSeek');
  const [intentForm] = Form.useForm();
  const [intentProvider, setIntentProvider] = useState('LongCat');
  const [intentTesting, setIntentTesting] = useState(false);

  useEffect(() => { loadAll(); }, []);

  const loadAll = async () => {
    try {
      const cfg = await getConfig().catch(() => null);
      if (cfg) {
        setBaseConfig(cfg);
        baseForm.setFieldsValue({
          max_sessions: cfg.max_sessions,
          session_timeout_minutes: cfg.session_timeout_minutes,
          visitor_password: cfg.visitor_password,
          portfolio_show: cfg.portfolio_show,
        });
        llmForm.setFieldsValue({
          llm_provider: cfg.llm_provider,
          llm_model: cfg.llm_model,
          llm_api_key: cfg.llm_api_key,
        });
        setLlmProvider(cfg.llm_provider || 'DeepSeek');
        embedForm.setFieldsValue({
          embedding_provider: cfg.embedding_provider,
          embedding_model: cfg.embedding_model,
          embedding_api_key: cfg.embedding_api_key,
        });
        visitorLlmForm.setFieldsValue({
          visitor_llm_provider: cfg.visitor_llm_provider || 'DeepSeek',
          visitor_llm_model: cfg.visitor_llm_model || 'deepseek-v4-flash',
          visitor_llm_api_key: cfg.visitor_llm_api_key || '',
        });
        setVisitorProvider(cfg.visitor_llm_provider || 'DeepSeek');
        searchForm.setFieldsValue({
          tavily_api_key: cfg.tavily_api_key || '',
          firecrawl_api_key: cfg.firecrawl_api_key || '',
          anysearch_api_key: cfg.anysearch_api_key || '',
          amap_api_key: cfg.amap_api_key || '',
        });
        visitorKeyForm.setFieldsValue({
          visitor_tavily_api_key: cfg.visitor_tavily_api_key || '',
          visitor_amap_api_key: cfg.visitor_amap_api_key || '',
        });
        intentForm.setFieldsValue({
          intent_llm_provider: cfg.intent_llm_provider || 'LongCat',
          intent_llm_model: cfg.intent_llm_model || 'LongCat-2.0',
          intent_llm_api_key: cfg.intent_llm_api_key || '',
        });
        setIntentProvider(cfg.intent_llm_provider || 'LongCat');
      }
    } catch {}
  };

  const getKeyMap = (): Record<string, string> => ({
    LongCat: baseConfig?.longcat_api_key || '',
    SiliconFlow: baseConfig?.siliconflow_api_key || '',
    DeepSeek: baseConfig?.deepseek_api_key || '',
    OpenAI: baseConfig?.openai_api_key || '',
  });

  const handleProviderChange = (val: string) => {
    setLlmProvider(val);
    const p = PROVIDERS[val];
    const keyMap = getKeyMap();
    llmForm.setFieldsValue({
      llm_model: p?.models?.length ? p.models[0] : '',
      llm_api_key: keyMap[val] || '',
    });
  };

  if (tab === 'prompt') return <PromptsManagePage />;

  return (
    <div>
      <div style={{ fontSize: 18, fontWeight: 600, color: 'var(--admin-text)', marginBottom: 16 }}>
        {SERVICE_TABS[tab]?.label || '配置'}
      </div>
      {/* ---- 管理端配置 ---- */}
      {tab === 'service' && (
        <div>
          <Card title="主题设置" size="small" style={{ marginBottom: 16, maxWidth: 600 }}>
            <div style={{ marginBottom: 12 }}>
              <div style={{ fontWeight: 600, color: 'var(--admin-text)', marginBottom: 4 }}>外观模式</div>
              <div style={{ fontSize: 13, color: 'var(--admin-text-muted)', marginBottom: 12 }}>选择管理后台的显示主题，可选择跟随系统自动切换</div>
              <Radio.Group
                value={themeMode}
                onChange={(e) => onThemeModeChange(e.target.value)}
                optionType="button"
                buttonStyle="solid"
                size="large"
              >
                <Radio.Button value="system"><LaptopOutlined /> 跟随系统</Radio.Button>
                <Radio.Button value="light"><SunOutlined /> 浅色</Radio.Button>
                <Radio.Button value="dark"><MoonOutlined /> 深色</Radio.Button>
              </Radio.Group>
            </div>
          </Card>
          <Card title="LLM 配置" size="small" style={{ marginBottom: 16, maxWidth: 600 }}>
            <Form form={llmForm} layout="vertical">
              <Form.Item name="llm_provider" label="提供商" rules={[{ required: true, message: '请选择提供商' }]}>
                <Select onChange={handleProviderChange}>
                  {Object.entries(PROVIDERS).map(([k, v]) => (
                    <Select.Option key={k} value={k}>{k} - {v.note}</Select.Option>
                  ))}
                </Select>
              </Form.Item>
              {(() => {
                const models = PROVIDERS[llmProvider]?.models;
                return models ? (
                  <Form.Item name="llm_model" label="模型" rules={[{ required: true, message: '请选择模型' }]}>
                    <Select key={llmProvider} showSearch optionFilterProp="children">
                      {models.map(m => <Select.Option key={m} value={m}>{m}</Select.Option>)}
                    </Select>
                  </Form.Item>
                ) : (
                  <Form.Item name="llm_model" label="模型" rules={[{ required: true, message: '请输入模型名称' }]}>
                    <Input maxLength={200} placeholder="输入模型名称，如 gpt-4o" />
                  </Form.Item>
                );
              })()}
              <Form.Item name="llm_api_key" label="API Key" rules={[{ required: true, message: '请输入API Key' }, { min: 8, message: 'API Key至少8位' }]}><Input.Password maxLength={200} /></Form.Item>
              <Space>
                <Button type="primary" onClick={async () => { await updateConfig(llmForm.getFieldsValue()); message.success('LLM配置已保存'); }}>保存</Button>
                <Button loading={llmTesting} onClick={async () => {
                  setLlmTesting(true);
                  try {
                    const p = llmForm.getFieldValue('llm_provider');
                    await testLlm(p, llmForm.getFieldValue('llm_api_key'), llmForm.getFieldValue('llm_model'), PROVIDERS[p]?.api_base || '');
                    message.success('连接成功');
                  } catch (e: any) { message.error(e?.response?.data?.detail || e?.message || '连接失败'); }
                  finally { setLlmTesting(false); }
                }}>测试连接</Button>
              </Space>
            </Form>
          </Card>
          <Card title="Embedding 配置" size="small" style={{ marginBottom: 16, maxWidth: 600 }}>
            <Form form={embedForm} layout="vertical">
              <Form.Item name="embedding_provider" label="提供商" rules={[{ required: true, message: '请选择提供商' }]}>
                <Select disabled options={[{ value: 'SiliconFlow', label: 'SiliconFlow' }]} />
              </Form.Item>
              <Form.Item name="embedding_model" label="模型" rules={[{ required: true, message: '请选择模型' }]}>
                <Input maxLength={200} placeholder="如 BAAI/bge-m3" />
              </Form.Item>
              <Form.Item name="embedding_api_key" label="API Key" rules={[{ required: true, message: '请输入API Key' }, { min: 8, message: 'API Key至少8位' }]}><Input.Password maxLength={200} /></Form.Item>
              <Space>
                <Button type="primary" onClick={async () => { await updateConfig(embedForm.getFieldsValue()); message.success('Embedding配置已保存'); }}>保存</Button>
                <Button loading={embedTesting} onClick={async () => {
                  setEmbedTesting(true);
                  try {
                    await testEmbedding(embedForm.getFieldValue('embedding_api_key'), embedForm.getFieldValue('embedding_model'), embedForm.getFieldValue('embedding_provider') === 'SiliconFlow' ? 'https://api.siliconflow.cn/v1' : '');
                    message.success('连接成功');
                  } catch (e: any) { message.error(e?.response?.data?.detail || e?.message || '连接失败'); }
                  finally { setEmbedTesting(false); }
                }}>测试连接</Button>
              </Space>
            </Form>
          </Card>
          <Card title="搜索服务密钥" size="small" style={{ marginBottom: 16, maxWidth: 600 }}>
            <div style={{ fontSize: 13, color: 'var(--admin-text-muted)', marginBottom: 16 }}>
              配置管理端使用的搜索服务 API 密钥（Agent 搜索、面试报告生成、面试宝典通勤计算）。
              <div style={{ marginTop: 8, color: 'var(--admin-text)', fontStyle: 'italic' }}>
                搜索密钥为空表示尚未配置，需要填写对应服务商的 API Key 后才能使用相关功能。
              </div>
            </div>
            <Form form={searchForm} layout="vertical">
              <Form.Item name="tavily_api_key" label="Tavily API Key（Agent 搜索）" extra="用于智能 Agent 的实时网页搜索">
                <Input.Password maxLength={200} placeholder="输入 Tavily API Key" />
              </Form.Item>
              <Form.Item name="firecrawl_api_key" label="Firecrawl API Key（深度网页抓取）" extra="用于面试报告生成时的深度页面内容抓取">
                <Input.Password maxLength={200} placeholder="输入 Firecrawl API Key" />
              </Form.Item>
              <Form.Item name="anysearch_api_key" label="Anysearch API Key（工商信息搜索）" extra="用于面试报告中的企业工商信息、竞品分析数据">
                <Input.Password maxLength={200} placeholder="输入 Anysearch API Key" />
              </Form.Item>
              <Form.Item name="amap_api_key" label="高德地图 API Key（面试宝典通勤）" extra="用于管理端面试宝典的通勤时间计算">
                <Input.Password maxLength={200} placeholder="输入高德地图 Web Service API Key" />
              </Form.Item>
              <Button type="primary" onClick={async () => {
                await updateConfig(searchForm.getFieldsValue());
                message.success('搜索服务密钥已保存');
              }}>保存密钥</Button>
            </Form>
          </Card>
          <Card title="意图识别模型配置" size="small" style={{ marginBottom: 16, maxWidth: 600 }}>
            <div style={{ fontSize: 13, color: 'var(--admin-text-muted)', marginBottom: 16 }}>
              管理端意图识别使用的 AI 模型，负责将用户输入解析为工具调用。留空则使用管理端 LLM 配置。
            </div>
            <Form form={intentForm} layout="vertical">
              <Form.Item name="intent_llm_provider" label="提供商">
                <Select onChange={(val: string) => {
                  setIntentProvider(val);
                  const p = PROVIDERS[val];
                  const keyMap = getKeyMap();
                  intentForm.setFieldsValue({
                    intent_llm_model: p?.models?.length ? p.models[0] : '',
                    intent_llm_api_key: keyMap[val] || '',
                  });
                }}>
                  {Object.entries(PROVIDERS).map(([k, v]) => (
                    <Select.Option key={k} value={k}>{k} - {v.note}</Select.Option>
                  ))}
                </Select>
              </Form.Item>
              {(() => {
                const models = PROVIDERS[intentProvider]?.models;
                return models ? (
                  <Form.Item name="intent_llm_model" label="模型">
                    <Select key={intentProvider} showSearch optionFilterProp="children">
                      {models.map(m => <Select.Option key={m} value={m}>{m}</Select.Option>)}
                    </Select>
                  </Form.Item>
                ) : (
                  <Form.Item name="intent_llm_model" label="模型">
                    <Input maxLength={200} placeholder="输入模型名称" />
                  </Form.Item>
                );
              })()}
              <Form.Item name="intent_llm_api_key" label="API Key">
                <Input.Password maxLength={200} placeholder="留空则使用服务配置的 API Key" />
              </Form.Item>
              <Space>
                <Button type="primary" onClick={async () => { await updateConfig(intentForm.getFieldsValue()); message.success('意图识别模型配置已保存'); }}>保存</Button>
                <Button loading={intentTesting} onClick={async () => {
                  setIntentTesting(true);
                  try {
                    const p = intentForm.getFieldValue('intent_llm_provider');
                    let apiKey = intentForm.getFieldValue('intent_llm_api_key');
                    if (!apiKey) {
                      apiKey = llmForm.getFieldValue('llm_api_key');
                    }
                    await testLlm(p, apiKey, intentForm.getFieldValue('intent_llm_model'), PROVIDERS[p]?.api_base || '');
                    message.success('连接成功');
                  } catch (e: any) { message.error(e?.response?.data?.detail || e?.message || '连接失败'); }
                  finally { setIntentTesting(false); }
                }}>测试连接</Button>
              </Space>
            </Form>
          </Card>
          <Card title="拓展知识库目录" size="small" style={{ marginBottom: 16, maxWidth: 600 }}>
            <Form form={baseForm} layout="vertical">
              <Form.Item name="appendix_knowledge_dir" label="知识库目录" extra="可指定额外的知识库目录（绝对路径），多个用 ; 分隔">
                <Input maxLength={500} placeholder="/data/knowledge" />
              </Form.Item>
              <Button type="primary" onClick={async () => { await updateConfig(baseForm.getFieldsValue()); message.success('配置已保存'); }}>保存</Button>
            </Form>
          </Card>
        </div>
      )}
      {/* ---- 访客端配置 ---- */}
      {tab === 'visitor' && (
        <div>
          <Card title="基础配置" size="small" style={{ marginBottom: 16, maxWidth: 600 }}>
            <Form form={baseForm} layout="vertical">
              <Form.Item name="max_sessions" label="最大会话数" rules={[{ required: true, message: '请输入最大会话数' }, { type: 'number', min: 1, max: 1000, message: '范围1-1000' }]}><InputNumber style={{ width: '100%' }} min={1} max={1000} /></Form.Item>
              <Form.Item name="session_timeout_minutes" label="会话超时（分钟）" rules={[{ required: true, message: '请输入超时时间' }, { type: 'number', min: 5, max: 1440, message: '范围5-1440分钟' }]}><InputNumber style={{ width: '100%' }} min={5} max={1440} /></Form.Item>
              <Form.Item name="visitor_password" label="访客访问口令" rules={[{ min: 4, message: '口令至少4位' }]}><Input.Password maxLength={50} /></Form.Item>
              <Button type="primary" onClick={async () => { await updateConfig(baseForm.getFieldsValue()); message.success('基础配置已保存'); }}>保存</Button>
            </Form>
          </Card>
          <Card title="访客端 LLM 配置" size="small" style={{ marginBottom: 16, maxWidth: 600 }}>
            <div style={{ fontSize: 13, color: 'var(--admin-text-muted)', marginBottom: 16 }}>
              访客端聊天使用的 AI 模型，影响访客的对话体验。DeepSeek/OpenAI 需填写对应的 API Key。
            </div>
            <Form form={visitorLlmForm} layout="vertical">
              <Form.Item name="visitor_llm_provider" label="提供商" rules={[{ required: true, message: '请选择提供商' }]}>
                <Select onChange={(val: string) => {
                  setVisitorProvider(val);
                  const p = PROVIDERS[val];
                  const keyMap = getKeyMap();
                  visitorLlmForm.setFieldsValue({
                    visitor_llm_model: p?.models?.length ? p.models[0] : '',
                    visitor_llm_api_key: keyMap[val] || '',
                  });
                }}>
                  {Object.entries(PROVIDERS).map(([k, v]) => (
                    <Select.Option key={k} value={k}>{k} - {v.note}</Select.Option>
                  ))}
                </Select>
              </Form.Item>
              {(() => {
                const models = PROVIDERS[visitorProvider]?.models;
                return models ? (
                  <Form.Item name="visitor_llm_model" label="模型" rules={[{ required: true, message: '请选择模型' }]}>
                    <Select key={visitorProvider} showSearch optionFilterProp="children">
                      {models.map(m => <Select.Option key={m} value={m}>{m}</Select.Option>)}
                    </Select>
                  </Form.Item>
                ) : (
                  <Form.Item name="visitor_llm_model" label="模型" rules={[{ required: true, message: '请输入模型名称' }]}>
                    <Input maxLength={200} placeholder="输入模型名称，如 gpt-4o" />
                  </Form.Item>
                );
              })()}
              <Form.Item name="visitor_llm_api_key" label="API Key">
                <Input.Password maxLength={200} placeholder="留空则使用服务配置的 API Key" />
              </Form.Item>
              <Space>
                <Button type="primary" onClick={async () => { await updateConfig(visitorLlmForm.getFieldsValue()); message.success('访客端 LLM 配置已保存'); }}>保存</Button>
                <Button loading={llmTesting} onClick={async () => {
                  setLlmTesting(true);
                  try {
                    const p = visitorLlmForm.getFieldValue('visitor_llm_provider');
                    let apiKey = visitorLlmForm.getFieldValue('visitor_llm_api_key');
                    if (!apiKey && p === 'DeepSeek') {
                      throw new Error('DeepSeek 需要填写 API Key，请先保存配置');
                    }
                    if (!apiKey) {
                      apiKey = llmForm.getFieldValue('llm_api_key');
                    }
                    await testLlm(p, apiKey, visitorLlmForm.getFieldValue('visitor_llm_model'), PROVIDERS[p]?.api_base || '');
                    message.success('连接成功');
                  } catch (e: any) { message.error(e?.response?.data?.detail || e?.message || '连接失败'); }
                  finally { setLlmTesting(false); }
                }}>测试连接</Button>
              </Space>
            </Form>
          </Card>
          <Card title="访客端 API 密钥" size="small" style={{ marginBottom: 16, maxWidth: 600 }}>
            <div style={{ fontSize: 13, color: 'var(--admin-text-muted)', marginBottom: 16 }}>
              配置访问端（求职者页面）使用的第三方 API 密钥，与管理端密钥分开管理。
            </div>
            <Form form={visitorKeyForm} layout="vertical">
              <Form.Item name="visitor_tavily_api_key" label="Tavily API Key（访客搜索）" extra="用于访客对话中的在线搜索，与管理端搜索密钥分开管理">
                <Input.Password maxLength={200} placeholder="输入访客 Tavily API Key" />
              </Form.Item>
              <Form.Item name="visitor_amap_api_key" label="高德地图 API Key（地址搜索）" extra="用于访问端页面中的地址搜索和地图选点功能">
                <Input.Password maxLength={200} placeholder="输入高德地图 Web Service API Key" />
              </Form.Item>
              <Button type="primary" onClick={async () => {
                await updateConfig(visitorKeyForm.getFieldsValue());
                message.success('访客端 API 密钥已保存');
              }}>保存</Button>
            </Form>
          </Card>
        </div>
      )}
    </div>
  );
}
