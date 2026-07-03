import { useState, useEffect } from 'react';
import { Card, Input, Button, message, Space, Switch, Select } from 'antd';
import {
  getWelcomeConfig, updateWelcomeConfig, generateWelcomeIntro,
  getMyConfig, updateMyConfig,
} from '../../api/config';
import { getStoredUserId } from '../../api/auth';
import { getFaqData } from '../../api/knowledge';

const { TextArea } = Input;

export default function AccessSettingsPage() {
  const [visitorEnabled, setVisitorEnabled] = useState(false);
  const [visitorPassword, setVisitorPassword] = useState('');
  const [visitorGreeting, setVisitorGreeting] = useState('');
  const [visitorIntro, setVisitorIntro] = useState('');
  const [visitorInitMsg, setVisitorInitMsg] = useState('');
  const [visitorQuickQ, setVisitorQuickQ] = useState<string[]>([]);
  const [faqOptions, setFaqOptions] = useState<{ label: string; value: string }[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getMyConfig().then((cfg) => {
      setVisitorEnabled(cfg.visitor_enabled ?? false);
      setVisitorPassword(cfg.visitor_password || '');
    }).catch(() => {});
    loadWelcomeConfig();
    getFaqData().then((res) => {
      const data = res?.data as Record<string, any>;
      const faqList = data?.faq_list || [];
      const opts = faqList.map((item: any) => ({ label: item.question, value: item.question }));
      setFaqOptions(opts);
    }).catch(() => {});
  }, []);

  const loadWelcomeConfig = async () => {
    try {
      const welcome = await getWelcomeConfig();
      setVisitorGreeting(welcome.greeting || '');
      setVisitorIntro(welcome.self_intro || '');
      setVisitorInitMsg(welcome.initial_message || '');
      const savedQQ = welcome.quick_questions ? welcome.quick_questions.split('\n').filter(Boolean) : [];
      setVisitorQuickQ(savedQQ);
    } catch {}
  };

  const saveVisitorConfig = async () => {
    setLoading(true);
    try {
      await updateMyConfig({
        visitor_enabled: visitorEnabled,
        visitor_password: visitorPassword,
      });
      message.success('访客配置已保存');
    } catch (e: any) {
      message.error(e.response?.data?.detail || '保存失败');
    } finally {
      setLoading(false);
    }
  };

  const userId = getStoredUserId();
  const username = localStorage.getItem('username') || userId || '';
  const visitorLink = userId ? `${window.location.origin}/visitor/${username}` : '';

  return (
    <div>
      <div style={{ fontSize: 18, fontWeight: 600, color: 'var(--admin-text)', marginBottom: 16 }}>访问设置</div>

      <Card title="访客基础设置" size="small" style={{ marginBottom: 16, maxWidth: 600 }}>
        <Space direction="vertical" style={{ width: '100%' }}>
          <div>
            <div style={{ fontWeight: 600, color: 'var(--admin-text)', marginBottom: 4 }}>开启访客访问</div>
            <Switch checked={visitorEnabled} onChange={async (checked) => {
              setVisitorEnabled(checked);
              try { await updateMyConfig({ visitor_enabled: checked }); }
              catch { message.error('保存失败'); }
            }} />
          </div>
          <div>
            <div style={{ fontWeight: 600, color: 'var(--admin-text)', marginBottom: 4 }}>访客口令</div>
            <Space>
              <Input.Password
                value={visitorPassword}
                onChange={(e) => setVisitorPassword(e.target.value)}
                maxLength={50}
                placeholder="设置访客访问所需的口令"
                style={{ maxWidth: 300 }}
              />
              <Button type="primary" loading={loading} onClick={saveVisitorConfig}>保存</Button>
              <Button
                disabled={!visitorPassword}
                onClick={() => {
                  navigator.clipboard.writeText(visitorPassword);
                  message.success('口令已复制');
                }}
              >
                复制
              </Button>
            </Space>
          </div>
          {visitorLink && (
            <div>
              <div style={{ fontWeight: 600, color: 'var(--admin-text)', marginBottom: 4 }}>访客链接</div>
              <Space wrap>
                <Input value={visitorLink} readOnly style={{ width: 420 }} />
                <Button onClick={() => { window.open(visitorLink, '_blank'); }}>进入</Button>
                <Button onClick={() => { navigator.clipboard.writeText(visitorLink); message.success('已复制'); }}>复制</Button>
              </Space>
            </div>
          )}
        </Space>
      </Card>

      <Card title="访客迎宾配置" size="small" style={{ maxWidth: 600 }}>
        <div style={{ marginBottom: 16 }}>
          <div style={{ marginBottom: 4 }}><strong>问候语</strong></div>
          <TextArea rows={1} value={visitorGreeting} onChange={e => setVisitorGreeting(e.target.value)} maxLength={200} showCount />
          <Space style={{ marginTop: 4 }}>
            <Button size="small" type="primary"
              onClick={async () => { await updateWelcomeConfig({ greeting: visitorGreeting }); message.success('问候语已保存'); }}>保存</Button>
          </Space>
        </div>
        <div style={{ marginBottom: 16 }}>
          <div style={{ marginBottom: 4 }}><strong>自我介绍</strong></div>
          <TextArea rows={3} value={visitorIntro} onChange={e => setVisitorIntro(e.target.value)} maxLength={500} showCount />
          <Space style={{ marginTop: 4 }}>
            <Button size="small" type="primary"
              onClick={async () => { await updateWelcomeConfig({ self_intro: visitorIntro }); message.success('自我介绍已保存'); }}>保存</Button>
            <Button size="small" onClick={async () => {
              try {
                const res = await generateWelcomeIntro();
                setVisitorIntro(res.self_intro || '');
                message.success('AI 生成成功');
              } catch (e: any) { message.error(e?.response?.data?.detail || '生成失败'); }
            }}>AI 生成</Button>
          </Space>
        </div>
        <div style={{ marginBottom: 16 }}>
          <div style={{ marginBottom: 4 }}><strong>初始消息</strong></div>
          <TextArea rows={2} value={visitorInitMsg} onChange={e => setVisitorInitMsg(e.target.value)} maxLength={500} showCount />
          <Space style={{ marginTop: 4 }}>
            <Button size="small" type="primary"
              onClick={async () => { await updateWelcomeConfig({ initial_message: visitorInitMsg }); message.success('初始消息已保存'); }}>保存</Button>
            <Button size="small" onClick={async () => {
              try {
                const res = await generateWelcomeIntro();
                if (res.initial_message) setVisitorInitMsg(res.initial_message);
                message.success('AI 生成成功');
              } catch (e: any) { message.error(e?.response?.data?.detail || '生成失败'); }
            }}>AI 生成</Button>
          </Space>
        </div>
        <div>
          <div style={{ marginBottom: 4 }}><strong>快捷问题（选6个，来自知识库高频问答）</strong></div>
          <Select mode="multiple" maxCount={6} placeholder="请选择快捷问题" options={faqOptions}
            value={visitorQuickQ} onChange={setVisitorQuickQ} style={{ width: '100%' }} />
          <Button size="small" type="primary" style={{ marginTop: 4 }}
            onClick={async () => { await updateWelcomeConfig({ quick_questions: visitorQuickQ.join('\n') }); message.success('快捷问题已保存'); }}>保存</Button>
        </div>
      </Card>
    </div>
  );
}
