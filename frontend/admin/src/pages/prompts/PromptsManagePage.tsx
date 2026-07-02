import { useState, useEffect, useCallback } from 'react';
import {
  Card, Input, Button, List, Typography, Space, Modal, message,
  Table, Tag, Tooltip, Empty, Spin, Descriptions, Popconfirm,
} from 'antd';
import {
  HistoryOutlined, RollbackOutlined, SaveOutlined,
  SearchOutlined, FileTextOutlined, ClockCircleOutlined,
} from '@ant-design/icons';
import { listPrompts, getPromptDetail, updatePrompt, rollbackPrompt } from '../../api/prompts';
import type { PromptListItem, PromptVersion } from '../../types/api';

const { TextArea } = Input;
const { Text, Title } = Typography;

export default function PromptsManagePage() {
  const [prompts, setPrompts] = useState<PromptListItem[]>([]);
  const [filtered, setFiltered] = useState<PromptListItem[]>([]);
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<{
    key: string; version: number; description: string;
    content: string; updated_at?: string; history: PromptVersion[];
  } | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editContent, setEditContent] = useState('');
  const [rollbackVis, setRollbackVis] = useState(false);
  const [rollbackVer, setRollbackVer] = useState<number | null>(null);

  const loadList = useCallback(async () => {
    try {
      const data = await listPrompts();
      setPrompts(data);
      setFiltered(data);
    } catch { message.error('加载提示词列表失败'); }
  }, []);

  useEffect(() => { loadList(); }, [loadList]);

  useEffect(() => {
    if (!search) { setFiltered(prompts); return; }
    const q = search.toLowerCase();
    setFiltered(prompts.filter(p =>
      p.key.toLowerCase().includes(q) || p.description.toLowerCase().includes(q)
    ));
  }, [search, prompts]);

  const loadDetail = async (key: string) => {
    setLoading(true);
    setSelected(key);
    try {
      const d = await getPromptDetail(key);
      setDetail(d);
      setEditContent(d.content);
    } catch { message.error('加载提示词详情失败'); }
    finally { setLoading(false); }
  };

  const handleSave = async () => {
    if (!selected) return;
    setSaving(true);
    try {
      await updatePrompt(selected, editContent);
      message.success('提示词已更新');
      await loadDetail(selected);
      await loadList();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '保存失败');
    } finally { setSaving(false); }
  };

  const handleRollback = async () => {
    if (!selected || rollbackVer === null) return;
    try {
      await rollbackPrompt(selected, rollbackVer);
      message.success(`已回退到版本 ${rollbackVer}`);
      setRollbackVis(false);
      await loadDetail(selected);
      await loadList();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '回退失败');
    }
  };

  return (
    <div style={{ display: 'flex', gap: 16, minHeight: 500 }}>
      {/* ── Left: Prompt list ── */}
      <Card
        style={{ width: 340, flexShrink: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}
        styles={{ body: { padding: 12, flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' } }}
      >
        <Input
          prefix={<SearchOutlined />}
          placeholder="搜索提示词..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          allowClear
          style={{ marginBottom: 8 }}
        />
        <div style={{ flex: 1, overflow: 'auto' }}>
          <List
            dataSource={filtered}
            renderItem={item => (
              <List.Item
                onClick={() => loadDetail(item.key)}
                style={{
                  cursor: 'pointer', padding: '8px 10px', borderRadius: 6,
                  background: selected === item.key ? 'var(--admin-accent-bg)' : 'transparent',
                  borderLeft: selected === item.key ? '3px solid var(--admin-accent)' : '3px solid transparent',
                  transition: 'all 0.2s',
                }}
              >
                <List.Item.Meta
                  title={<Text strong style={{ fontSize: 13 }}>{item.key}</Text>}
                  description={
                    <div>
                      <Text type="secondary" style={{ fontSize: 12 }}>{item.description}</Text>
                      <br />
                      <Tag style={{ fontSize: 11, marginTop: 4 }}>v{item.version}</Tag>
                    </div>
                  }
                />
              </List.Item>
            )}
            locale={{ emptyText: <Empty description="无匹配提示词" /> }}
          />
        </div>
      </Card>

      {/* ── Right: Prompt detail ── */}
      <Card style={{ flex: 1, overflow: 'auto', maxHeight: 600 }} styles={{ body: { padding: 16 } }}>
        {!selected ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', opacity: 0.4 }}>
            <Space direction="vertical" align="center">
              <FileTextOutlined style={{ fontSize: 48 }} />
              <Text type="secondary">请从左侧选择一个提示词</Text>
            </Space>
          </div>
        ) : loading ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: 80 }}><Spin size="large" /></div>
        ) : detail ? (
          <>
            {/* Header */}
            <div style={{ marginBottom: 16 }}>
              <Title level={5} style={{ margin: 0 }}>{detail.key}</Title>
              <Text type="secondary">{detail.description}</Text>
              <div style={{ marginTop: 4 }}>
                <Tag color="blue">v{detail.version}</Tag>
                {detail.updated_at && (
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    <ClockCircleOutlined /> 更新于 {new Date(detail.updated_at).toLocaleString('zh-CN')}
                  </Text>
                )}
              </div>
            </div>

            {/* Editable content */}
            <TextArea
              rows={18}
              value={editContent}
              onChange={e => setEditContent(e.target.value)}
              style={{ fontFamily: 'monospace', fontSize: 13 }}
            />
            <Space style={{ marginTop: 12 }}>
              <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={handleSave}>
                保存
              </Button>
              <Button
                icon={<RollbackOutlined />}
                onClick={() => setRollbackVis(true)}
                disabled={!detail.history || detail.history.length === 0}
              >
                回退
              </Button>
            </Space>

            {/* Version History */}
            {detail.history && detail.history.length > 0 && (
              <Card
                size="small"
                title={<Space><HistoryOutlined />版本历史（{detail.history.length} 个版本）</Space>}
                style={{ marginTop: 16 }}
              >
                <Table
                  dataSource={detail.history}
                  rowKey="id"
                  size="small"
                  pagination={false}
                  columns={[
                    { title: '版本', dataIndex: 'version', width: 70, render: v => <Tag>v{v}</Tag> },
                    {
                      title: '变更说明', dataIndex: 'change_log', width: 200,
                      render: (v: string) => v || '-',
                    },
                    { title: '操作人', dataIndex: 'created_by', width: 100 },
                    {
                      title: '时间', dataIndex: 'created_at', width: 180,
                      render: (v: string) => new Date(v).toLocaleString('zh-CN'),
                    },
                    {
                      title: '操作', key: 'action', width: 80,
                      render: (_: any, row: PromptVersion) => (
                        <Popconfirm
                          title={`回退到 v${row.version}？`}
                          onConfirm={() => {
                            setRollbackVer(row.version);
                            handleRollback();
                          }}
                        >
                          <Button type="link" size="small" icon={<RollbackOutlined />}>回退</Button>
                        </Popconfirm>
                      ),
                    },
                  ]}
                />
              </Card>
            )}
          </>
        ) : null}
      </Card>

      {/* Rollback confirmation modal */}
      <Modal
        title="回退提示词"
        open={rollbackVis}
        onOk={handleRollback}
        onCancel={() => setRollbackVis(false)}
        okText="确认回退"
        cancelText="取消"
      >
        {detail && (
          <div style={{ marginBottom: 12 }}>
            <Text>将 <Tag>{detail.key}</Tag> 回退到 <Tag>v{rollbackVer}</Tag></Text>
          </div>
        )}
        <Text type="warning">回退后当前版本将保存到历史记录中，可通过再次回退恢复。</Text>
      </Modal>
    </div>
  );
}
