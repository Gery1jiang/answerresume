import { useState } from 'react';
import { Card, Row, Col, Statistic, Table, Tabs, Button, Input, message, Modal, Space, Popconfirm } from 'antd';
import { PlusOutlined, MessageOutlined, DeleteOutlined } from '@ant-design/icons';
import { useStats, useQuestionStats, useSessionConversations, useClearStats, useFaqData, useSaveFaq } from '../../hooks/useStats';

const { TextArea } = Input;

export default function StatisticsPage() {
  const { data: stats } = useStats();
  const { data: questionStats } = useQuestionStats();
  const clearStats = useClearStats();
  const { data: faqData } = useFaqData();
  const saveFaq = useSaveFaq();

  const [modalOpen, setModalOpen] = useState(false);
  const [curQuestion, setCurQuestion] = useState('');
  const [curAnswer, setCurAnswer] = useState('');
  const [expandedSession, setExpandedSession] = useState<string | null>(null);
  const { data: sessionConvs, refetch: refetchConvs } = useSessionConversations(expandedSession);

  const handleClear = async () => {
    try {
      await clearStats.mutateAsync();
      message.success('统计数据已清除');
    } catch {
      message.error('清除失败');
    }
  };

  const handleAddToKnowledge = (question: string) => {
    setCurQuestion(question);
    setCurAnswer('');
    setModalOpen(true);
  };

  const handleSaveQa = async () => {
    if (!curQuestion.trim()) { message.warning('请填写问题'); return; }
    try {
      const list = Array.isArray(faqData?.data?.faq_list) ? faqData.data.faq_list : [];
      list.push({ question: curQuestion.trim(), answer: curAnswer.trim() });
      await saveFaq.mutateAsync(list);
      message.success('问答已添加到知识库');
      setModalOpen(false);
    } catch { message.error('保存失败'); }
  };

  const hasStats = stats && (stats.visit_count !== undefined);
  const qStats = Array.isArray(questionStats) ? questionStats : [];
  const sessionsList = Array.isArray(stats?.sessions) ? stats.sessions : [];
  const convList = Array.isArray(sessionConvs) ? sessionConvs : sessionConvs?.conversations || [];

  const tabItems = [
    {
      key: 'overview',
      label: '统计概览',
      children: (
        <div>
          {hasStats && (
            <Row gutter={16} style={{ marginBottom: 16 }}>
              <Col span={6}><Card><Statistic title="总访问量" value={stats.visit_count ?? 0} /></Card></Col>
              <Col span={6}><Card><Statistic title="总对话数" value={stats.chat_count ?? 0} /></Card></Col>
              <Col span={6}><Card><Statistic title="总下载数" value={stats.download_count ?? 0} /></Card></Col>
              <Col span={6}><Card><Statistic title="新版主页访问" value={stats.portfolio_count ?? 0} /></Card></Col>
            </Row>
          )}
        </div>
      ),
    },
    {
      key: 'sessions',
      label: '会话管理',
      children: (
        <div>
          {sessionsList.length > 0 ? (
            <Table
              dataSource={sessionsList}
              rowKey="session_id"
              size="small"
              pagination={{ pageSize: 20 }}
              columns={[
                { title: '会话ID', dataIndex: 'session_id', render: (v: string) => v?.substring(0, 8) + '...' },
                { title: '创建时间', dataIndex: 'created_at' },
                { title: '对话轮数', dataIndex: 'conversation_count' },
                { title: '下载次数', dataIndex: 'download_count' },
                {
                  title: '', width: 50,
                  render: (_: any, record: any) => (
                    <Button type="link" size="small" icon={<MessageOutlined />}
                      onClick={() => setExpandedSession(expandedSession === record.session_id ? null : record.session_id)} />
                  ),
                },
              ]}
              expandable={{
                expandedRowKeys: expandedSession ? [expandedSession] : [],
                expandedRowRender: () => (
                  <div>
                    {convList.length > 0 ? convList.map((c: any, i: number) => (
                      <div key={i} style={{ marginBottom: 4, padding: '4px 8px', background: i % 2 === 0 ? 'var(--admin-bg-tertiary)' : 'var(--admin-bg-card)' }}>
                        <strong>{c.role === 'user' ? '用户' : 'AI'}:</strong> <span style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{c.content || ''}</span>
                      </div>
                    )) : <span style={{ color: 'var(--admin-text-muted)' }}>加载中...</span>}
                  </div>
                ),
              }}
            />
          ) : <div style={{ color: 'var(--admin-text-muted)', padding: 16 }}>暂无会话记录</div>}
        </div>
      ),
    },
    {
      key: 'questions',
      label: '高频问题',
      children: (
        <div>
          {qStats.length > 0 ? (
            <Table
              dataSource={qStats}
              rowKey={(_, i) => String(i)}
              size="small"
              pagination={{ pageSize: 20 }}
              columns={[
                { title: '问题', dataIndex: 'question', ellipsis: true },
                { title: '次数', dataIndex: 'count', width: 80 },
                {
                  title: '操作', width: 50,
                  render: (_: any, record: any) => (
                    <Button type="link" size="small" icon={<PlusOutlined />}
                      onClick={() => handleAddToKnowledge(record.question)} />
                  ),
                },
              ]}
            />
          ) : <div style={{ color: 'var(--admin-text-muted)', padding: 16 }}>暂无数据</div>}

          <Modal title="添加到知识库" open={modalOpen}
            onOk={handleSaveQa} onCancel={() => setModalOpen(false)}
            confirmLoading={saveFaq.isPending} okText="确定"
          >
            <Space direction="vertical" style={{ width: '100%' }}>
              <div>
                <div style={{ marginBottom: 4 }}><strong>问题</strong></div>
                <Input value={curQuestion} onChange={(e) => setCurQuestion(e.target.value)} maxLength={500} />
              </div>
              <div>
                <div style={{ marginBottom: 4 }}><strong>回答</strong></div>
                <TextArea value={curAnswer} onChange={(e) => setCurAnswer(e.target.value)} rows={4} maxLength={2000} showCount />
              </div>
            </Space>
          </Modal>
        </div>
      ),
    },
  ];

  return (
    <Tabs
      items={tabItems}
      renderTabBar={(props, DefaultTabBar) => (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingRight: 4 }}>
          <div style={{ flex: 1 }}>
            <DefaultTabBar {...props} />
          </div>
          <Popconfirm
            title="确认清除所有统计数据？"
            description="此操作不可恢复，所有统计记录将被永久删除。"
            onConfirm={handleClear}
            okText="确认清除"
            cancelText="取消"
            okButtonProps={{ danger: true }}
          >
            <Button icon={<DeleteOutlined />} danger size="small" loading={clearStats.isPending}>清除统计数据</Button>
          </Popconfirm>
        </div>
      )}
    />
  );
}
