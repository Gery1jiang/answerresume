import { useState, useEffect } from 'react';
import {
  Card, Row, Col, Button, Select, Input, Tag, List, Space, Modal, message, Switch, Radio, Spin,
} from 'antd';
import { DownloadOutlined, EyeOutlined, DeleteOutlined, StarOutlined, ThunderboltOutlined } from '@ant-design/icons';
import { Typography } from 'antd';
const { Text } = Typography;
import { getTemplates, getResumes, generateResume, deleteResume, setDefaultResume, getResume, updateTemplate, toggleResumeShow, getResumeStatus, getResumeViewUrl, getResumeDownloadUrl } from '../../api/resume';
import type { ResumeTemplate } from '../../api/resume';
import type { ResumeListItem } from '../../types/api';
import api, { getToken } from '../../api';

export default function ResumePage() {
  const [templates, setTemplates] = useState<ResumeTemplate[]>([]);
  const [resumes, setResumes] = useState<ResumeListItem[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState('modern');
  const [jd, setJd] = useState('');
  const [targetJob, setTargetJob] = useState('');
  const [generating, setGenerating] = useState(false);
  const [loading, setLoading] = useState(true);
  const [previewId, setPreviewId] = useState<number | null>(null);
  const [previewHtml, setPreviewHtml] = useState('');
  const [previewTemplate, setPreviewTemplate] = useState('modern');
  const [resumeShow, setResumeShow] = useState(false);

  const loadData = async () => {
    setLoading(true);
    try {
      const [tmpl, res, status] = await Promise.all([
        getTemplates(),
        getResumes(),
        getResumeStatus(),
      ]);
      setTemplates(tmpl);
      setResumes(res.resumes);
      setResumeShow(status.resume_show);
    } catch {
      message.error('加载简历列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadData(); }, []);

  const handleGenerate = async () => {
    if (!targetJob) {
      message.warning('请填写目标职位');
      return;
    }
    setGenerating(true);
    try {
      await generateResume(jd, targetJob, selectedTemplate);
      message.success('简历生成成功！');
      setJd('');
      setTargetJob('');
      loadData();
    } catch { message.error('生成失败'); }
    finally { setGenerating(false); }
  };

  const handlePreview = async (id: number) => {
    setPreviewId(id);
    try {
      const detail = await getResume(id);
      const tmpl = JSON.parse(detail.content || '{}')._template || 'modern';
      setPreviewTemplate(tmpl);
      const url = getResumeViewUrl(id, tmpl);
      const res = await api.get(url, { responseType: 'text' });
      setPreviewHtml(res.data);
    } catch { message.error('加载预览失败'); }
  };

  const handleDelete = (id: number) => {
    Modal.confirm({
      title: '确认删除此简历？',
      onOk: async () => {
        await deleteResume(id);
        message.success('已删除');
        loadData();
      },
    });
  };

  const handleToggleShow = async () => {
    await toggleResumeShow();
    setResumeShow(!resumeShow);
  };

  const handleTemplateChange = async (resumeId: number, template: string) => {
    await updateTemplate(resumeId, template);
    message.success('模板已更新');
    if (previewId === resumeId) handlePreview(resumeId);
  };

  return (
    <div>
      <Row gutter={16}>
        <Col span={8}>
          <Card title="生成新简历" size="small">
            <div style={{ marginBottom: 12 }}>
              <Text type="secondary">选择模板</Text>
              <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
                {templates.map((t) => (
                  <Tag
                    key={t.key}
                    color={selectedTemplate === t.key ? 'blue' : 'default'}
                    style={{ cursor: 'pointer', padding: '4px 12px' }}
                    onClick={() => setSelectedTemplate(t.key)}
                  >
                    {t.name}
                  </Tag>
                ))}
              </div>
            </div>
            <Input.TextArea
              value={jd}
              onChange={(e) => setJd(e.target.value)}
              placeholder="岗位描述/JD（可选，留空则根据岗位和个人经历生成通用简历）"
              rows={6}
              maxLength={10000}
              showCount
              style={{ marginBottom: 8 }}
            />
            <Input
              value={targetJob}
              onChange={(e) => setTargetJob(e.target.value)}
              placeholder="目标职位"
              maxLength={200}
              style={{ marginBottom: 12 }}
            />
            <Button
              type="primary"
              icon={<ThunderboltOutlined />}
              onClick={handleGenerate}
              loading={generating}
              block
            >
              生成简历
            </Button>
          </Card>
        </Col>

        <Col span={16}>
          <Card
            title="简历列表"
            size="small"
            extra={
              <Space>
                <Text type="secondary">访客端预览</Text>
                <Switch checked={resumeShow} onChange={handleToggleShow} />
              </Space>
            }
          >
            <List
              loading={loading}
              dataSource={resumes}
              renderItem={(item, idx) => (
                <List.Item
                  actions={[
                    <Button
                      type="text"
                      icon={<StarOutlined />}
                      onClick={() => setDefaultResume(item.id).then(() => loadData())}
                    >
                      {item.is_default ? '已默认' : '默认'}
                    </Button>,
                    <Button type="text" icon={<EyeOutlined />} onClick={() => handlePreview(item.id)}>
                      预览
                    </Button>,
                    <Button type="text" icon={<DownloadOutlined />}
                      onClick={async () => {
                        try {
                          const detail = await getResume(item.id);
                          const parsed = JSON.parse(detail.content || '{}');
                          const tmpl = parsed._template || 'modern';
                          const personal = parsed.personal || {};
                          const name = personal.name || '';
                          const phone = personal.phone || '';
                          const jobTitle = personal.jobTitle || '';
                          const parts = [name, jobTitle, phone].filter(Boolean);
                          const filename = parts.join('_') + '.pdf';
                          const url = getResumeDownloadUrl(item.id, tmpl);
                          const res = await api.get(url, { responseType: 'blob' });
                          const blob = new Blob([res.data], { type: 'application/pdf' });
                          const link = document.createElement('a');
                          link.href = URL.createObjectURL(blob);
                          link.download = filename;
                          link.click();
                          URL.revokeObjectURL(link.href);
                        } catch { message.error('下载失败'); }
                      }}
                    >
                      下载
                    </Button>,
                    <Button type="text" danger icon={<DeleteOutlined />} onClick={() => handleDelete(item.id)} />,
                  ]}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                    <Tag style={{ minWidth: 36, textAlign: 'center' }}>#{resumes.length - idx}</Tag>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontWeight: 600, fontSize: 15, color: 'var(--admin-text)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {item.title}{item.job_title ? <span style={{ fontWeight: 400, fontSize: 13, color: 'var(--admin-text-muted)', marginLeft: 8 }}>{item.job_title}</span> : null}
                      </div>
                      <div style={{ fontSize: 13, color: 'var(--admin-text-muted)', marginTop: 2 }}>{item.created_at}</div>
                    </div>
                    {item.is_default && <Tag color="gold" style={{ flexShrink: 0 }}>默认</Tag>}
                  </div>
                </List.Item>
              )}
            />
          </Card>
        </Col>
      </Row>

      <Modal
        title="简历预览"
        open={!!previewId}
        onCancel={() => { setPreviewId(null); setPreviewHtml(''); }}
        width="70%"
        footer={null}
      >
        {previewId && (
          <div style={{ marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
            <Text>切换模板：</Text>
            <Select
              value={previewTemplate}
              onChange={async (v) => {
                setPreviewTemplate(v);
                await handleTemplateChange(previewId!, v);
                handlePreview(previewId);
              }}
              options={templates.map(t => ({ label: t.name, value: t.key }))}
              style={{ width: 200 }}
            />
            <Button type="primary" icon={<DownloadOutlined />}
              onClick={async () => {
                try {
                  const detail = await getResume(previewId);
                  const parsed = JSON.parse(detail.content || '{}');
                  const tmpl = parsed._template || 'modern';
                  const personal = parsed.personal || {};
                  const name = personal.name || '';
                  const phone = personal.phone || '';
                  const jobTitle = personal.jobTitle || '';
                  const parts = [name, jobTitle, phone].filter(Boolean);
                  const filename = parts.join('_') + '.pdf';
                  const url = getResumeDownloadUrl(previewId, tmpl);
                  const res = await api.get(url, { responseType: 'blob' });
                  const blob = new Blob([res.data], { type: 'application/pdf' });
                  const link = document.createElement('a');
                  link.href = URL.createObjectURL(blob);
                  link.download = filename;
                  link.click();
                  URL.revokeObjectURL(link.href);
                } catch { message.error('下载失败'); }
              }}
            >下载 PDF</Button>
          </div>
        )}
        <div dangerouslySetInnerHTML={{ __html: previewHtml }} style={{ height: '70vh', overflow: 'auto' }} />
      </Modal>
    </div>
  );
}
