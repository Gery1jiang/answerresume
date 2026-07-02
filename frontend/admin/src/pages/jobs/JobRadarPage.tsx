import { useState, useEffect, useCallback, useRef } from 'react';
import {
  Card, Table, Button, Input, InputNumber, Space, Tag, Modal, Descriptions, message,
  Progress, Typography, Tooltip, Popconfirm, Select,
} from 'antd';
import {
  SearchOutlined, PlusOutlined, DeleteOutlined, ThunderboltOutlined,
  ReloadOutlined, EyeOutlined, ApiOutlined,
} from '@ant-design/icons';

const RADAR_SEEN_KEY = 'jobRadarLastSeen';
import type { ColumnsType } from 'antd/es/table';
import {
  getJobs, deleteJob, batchMatchJobs, matchJob,
  addJob, getJob, crawlJobs, batchDeleteJobs,
  type CrawledJob, type MatchDetail,
} from '../../api/jobs';

const { TextArea } = Input;
const { Text, Title } = Typography;

export default function JobRadarPage() {
  const [jobs, setJobs] = useState<CrawledJob[]>([]);
  const [loading, setLoading] = useState(false);
  const [keyword, setKeyword] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [minScore, setMinScore] = useState<number>(0);
  const lastSeenRef = useRef(parseInt(localStorage.getItem(RADAR_SEEN_KEY) || '0', 10));

  // 标记本次加载中的"新"岗位，离开页面时更新最后查看时间
  useEffect(() => {
    return () => {
      localStorage.setItem(RADAR_SEEN_KEY, String(Date.now()));
    };
  }, []);

  const markNewJobs = useCallback((jobList: CrawledJob[]) => {
    return jobList.map(job => ({
      ...job,
      isNew: job.created_at ? new Date(job.created_at).getTime() > lastSeenRef.current : false,
    }));
  }, []);

  // Crawl state
  const [crawlKeywords, setCrawlKeywords] = useState('');
  const [crawlCity, setCrawlCity] = useState('');
  const [crawlPlatform, setCrawlPlatform] = useState('51job');
  const [crawlCount, setCrawlCount] = useState(5);
  const [crawlAutoMatch, setCrawlAutoMatch] = useState(true);
  const [crawling, setCrawling] = useState(false);

  // Selection for batch match
  const [selectedRowIds, setSelectedRowIds] = useState<number[]>([]);

  // Add job modal
  const [addModal, setAddModal] = useState(false);
  const [addForm, setAddForm] = useState({ title: '', company: '', city: '', salary: '', jd_text: '', work_address: '' });

  // Detail modal
  const [detailModal, setDetailModal] = useState(false);
  const [detailJob, setDetailJob] = useState<any>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const loadJobs = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getJobs({
        status: statusFilter || undefined,
        min_score: minScore || undefined,
        keyword: keyword || undefined,
      });
      setJobs(markNewJobs(data.jobs));
    } catch {
      message.error('加载岗位列表失败');
    } finally {
      setLoading(false);
    }
  }, [keyword, statusFilter, minScore]);

  useEffect(() => {
    loadJobs();
    try { Notification.requestPermission(); } catch {}
    return () => {
      message.destroy('crawl');
      message.destroy('batchMatch');
    };
  }, [loadJobs]);

  // Recover stuck matching jobs on mount
  useEffect(() => {
    (async () => {
      try {
        const all = await getJobs({});
        const stuck = all.jobs.filter(j => j.status === 'matching' && j.created_at && Date.now() - new Date(j.created_at).getTime() > 30000);
        if (stuck.length > 0) {
          console.log(`[recover] re-matching ${stuck.length} stuck jobs`);
          await batchMatchJobs(stuck.map(j => j.id));
          loadJobs();
        }
      } catch {}
    })();
  }, []);

  const handleAdd = async () => {
    if (!addForm.title.trim()) {
      message.warning('请输入岗位名称');
      return;
    }
    try {
      await addJob(addForm);
      message.success('岗位已添加');
      setAddModal(false);
      setAddForm({ title: '', company: '', city: '', salary: '', jd_text: '', work_address: '' });
      loadJobs();
    } catch {
      message.error('添加失败');
    }
  };

  const handleMatch = async (id: number) => {
    // 立即在本地把状态改成 matching，表格显示"匹配中"
    setJobs(prev => prev.map(j => j.id === id ? { ...j, status: 'matching' as const } : j));
    message.loading({ content: '匹配中...', key: `match-${id}`, duration: 0 });
    try {
      const result = await matchJob(id);
      message.destroy(`match-${id}`);
      message.success(`匹配完成：${result.score}分`);
      loadJobs();
    } catch {
      message.destroy(`match-${id}`);
      message.error('匹配失败');
      loadJobs();
    }
  };

  const handleBatchMatch = async () => {
    const ids = selectedRowIds;
    if (ids.length === 0) {
      message.warning('请先勾选需要匹配的岗位');
      return;
    }
    const unMatched = jobs.filter(j => ids.includes(j.id) && j.status !== 'matched' && j.status !== 'applied');
    if (unMatched.length === 0) {
      message.info('选中的岗位已全部匹配，无需重复匹配');
      return;
    }
    try {
      message.loading({ content: `正在匹配 ${unMatched.length} 个岗位...`, key: 'batchMatch' });
      const result = await batchMatchJobs(unMatched.map(j => j.id));
      message.success({ content: result.message, key: 'batchMatch' });
      setSelectedRowIds([]);
      loadJobs();
    } catch {
      message.error({ content: '批量匹配失败', key: 'batchMatch' });
    }
  };

  const handleBatchDelete = async () => {
    const ids = selectedRowIds;
    if (ids.length === 0) {
      message.warning('请先勾选需要删除的岗位');
      return;
    }
    try {
      message.loading({ content: `正在删除 ${ids.length} 个岗位...`, key: 'batchDelete' });
      const result = await batchDeleteJobs(ids);
      message.success({ content: result.message, key: 'batchDelete' });
      setSelectedRowIds([]);
      loadJobs();
    } catch {
      message.error({ content: '批量删除失败', key: 'batchDelete' });
    }
  };

  const handleCrawl = async () => {
    if (!crawlKeywords.trim()) {
      message.warning('请输入搜索关键词');
      return;
    }
    setCrawling(true);
    const t0 = new Date();
    message.loading({ content: `[${t0.toLocaleTimeString()}] 正在抓取岗位...`, key: 'crawl', duration: 0 });

    try {
      const resp = await crawlJobs(crawlKeywords, crawlCity, crawlPlatform, crawlCount, 'time', crawlAutoMatch ? 0 : -1, crawlAutoMatch);
      const elapsed = Math.round((Date.now() - t0.getTime()) / 1000);
      const savedCount: number = resp.count || 0;
      message.destroy('crawl');

      // Refresh data immediately — matching jobs show "匹配中" tag
      const data = await getJobs({ status: statusFilter || undefined, min_score: minScore || undefined, keyword: keyword || undefined });
      setJobs(markNewJobs(data.jobs));

      if (crawlAutoMatch) {
        // Silent polling: no loading toast, just update statuses as matching completes
        const deadline = Date.now() + 120000;
        const poll = setInterval(async () => {
          try {
            const d = await getJobs({});
            setJobs(markNewJobs(d.jobs));
            const matching = d.jobs.filter(j => j.status === 'matching');
            if (matching.length === 0 || Date.now() > deadline) {
              clearInterval(poll);
              message.success({ content: `匹配完成，共 ${savedCount} 个岗位`, key: 'crawl-done', duration: 6 });
              try { new Notification('岗位雷达', { body: `匹配完成，共 ${savedCount} 个岗位` }); } catch {}
            }
          } catch {}
        }, 3000);
      } else {
        message.success({ content: `[${elapsed}s] ${resp.message}`, key: 'crawl-result', duration: 6 });
        try { new Notification('岗位雷达', { body: `[${elapsed}s] ${resp.message}` }); } catch {}
      }
    } catch (e: any) {
      message.destroy('crawl');
      const errMsg = e?.response?.data?.detail || e?.message || '抓取失败';
      message.error({ content: errMsg, key: 'crawl-result', duration: 6 });
    } finally {
      setCrawling(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteJob(id);
      message.success('已删除');
      loadJobs();
    } catch {
      message.error('删除失败');
    }
  };

  const showDetail = async (id: number) => {
    setDetailLoading(true);
    setDetailModal(true);
    try {
      const data = await getJob(id);
      setDetailJob(data);
    } catch {
      message.error('加载详情失败');
    } finally {
      setDetailLoading(false);
    }
  };

  const MATCH_THRESHOLD = 60; // matches backend threshold
  const scoreColor = (score: number | null) => {
    if (score === null) return '#999';
    if (score >= MATCH_THRESHOLD) return '#52c41a';
    return '#ff4d4f';
  };

  const columns: ColumnsType<CrawledJob> = [
    {
      title: '匹配度',
      dataIndex: 'match_score',
      key: 'score',
      width: 100,
      render: (score: number | null, record: CrawledJob) =>
        score !== null ? (
          <Tooltip title={`${score}%`}>
            <Progress
              percent={score}
              size="small"
              strokeColor={scoreColor(score)}
              format={(p) => `${p}%`}
              style={{ width: 70 }}
            />
          </Tooltip>
        ) : (
            record.status === 'matching' ? <Tag color="processing">匹配中</Tag> : <Tag color="default">待匹配</Tag>
        ),
      sorter: (a, b) => (a.match_score || 0) - (b.match_score || 0),
    },
      { title: '平台', dataIndex: 'platform', key: 'platform', width: 70,
        render: (p: string) => <Tag>{p || 'manual'}</Tag>,
        filters: [{ text: '51job', value: '51job' }, { text: 'BOSS直聘', value: 'boss' }, { text: '智联招聘', value: 'zhaopin' }, { text: '手动', value: 'manual' }],
        onFilter: (v: any, r: CrawledJob) => r.platform === v,
      },
      {
        title: '岗位',
        dataIndex: 'title',
        key: 'title',
        width: 200,
        render: (_: any, record: CrawledJob) => (
          <>
            {record.status === 'new' && <Tag color="orange" style={{ marginRight: 4, fontSize: 10, lineHeight: '16px', padding: '0 4px' }}>新</Tag>}
            {record.status === 'matching' && <Tag color="processing" style={{ marginRight: 4, fontSize: 10, lineHeight: '16px', padding: '0 4px' }}>匹配中</Tag>}
            {record.jd_url ? (
              <a href={record.jd_url} target="_blank" rel="noreferrer">{record.title}</a>
            ) : record.title}
          </>
        ),
      },
      { title: '公司', dataIndex: 'company', key: 'company', width: 160 },
      { title: '城市', dataIndex: 'city', key: 'city', width: 80 },
      { title: '工作地址', dataIndex: 'work_address', key: 'work_address', width: 160,
        render: (v: string) => v || '-',
      },
      { title: '薪资', dataIndex: 'salary', key: 'salary', width: 120 },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 80,
      render: (s: string) => {
        const colorMap: Record<string, string> = { matched: 'green', matching: 'processing', new: 'orange', applied: 'blue' };
        const labelMap: Record<string, string> = { matched: '已匹配', matching: '匹配中', new: '新' };
        return <Tag color={colorMap[s] || 'default'}>{labelMap[s] || s}</Tag>;
      },
    },
    {
      title: '抓取时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 160,
      render: (t: string | null) => t ? new Date(t).toLocaleString('zh-CN') : '-',
      sorter: (a, b) => new Date(a.created_at || 0).getTime() - new Date(b.created_at || 0).getTime(),
      defaultSortOrder: 'descend' as const,
    },
    {
      title: '操作',
      key: 'actions',
      width: 200,
      render: (_: any, record: CrawledJob) => (
        <Space>
          <Button size="small" icon={<EyeOutlined />} onClick={() => showDetail(record.id)}>详情</Button>
          {record.status !== 'matched' && record.status !== 'applied' && (
            <Button size="small" icon={<ThunderboltOutlined />} onClick={() => handleMatch(record.id)}>
              匹配
            </Button>
          )}
          <Popconfirm title="确认删除？" onConfirm={() => handleDelete(record.id)}>
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const DIM_LABELS: Record<string, string> = {
    education: '学历',
    experience: '经验',
    skills: '技能',
    location: '地点',
    salary: '薪资',
    responsibility: '职责',
    industry: '行业',
    complexity: '复杂度',
  };

  const expandedRowRender = (record: CrawledJob) => {
    const detail = record.match_detail as MatchDetail | null;
    if (!detail) return <Text type="secondary">暂无匹配数据，请先执行匹配</Text>;

    const dimColor = (s: number, m: number) => {
      const pct = s / m;
      if (pct >= 0.8) return '#52c41a';
      if (pct >= 0.5) return '#faad14';
      return '#ff4d4f';
    };

    const blockADims = ['education', 'experience', 'skills', 'location', 'salary'];
    const blockBDims = ['responsibility', 'industry', 'complexity'];

    return (
      <div style={{ padding: '8px 0' }}>
        <Text type="secondary">{detail.summary}</Text>

        {detail.dimensions && (
          <>
            <div style={{ marginTop: 12, fontWeight: 600, fontSize: 13, color: '#333' }}>硬性匹配 (Block A)</div>
            <div style={{ marginTop: 4, marginBottom: 8, display: 'flex', gap: 12, flexWrap: 'wrap' }}>
              {blockADims.map((key) => {
                const dim = (detail.dimensions as any)[key];
                if (!dim) return null;
                const pct = Math.round((dim.score / dim.max) * 100);
                return (
                  <div key={key} style={{ flex: '0 0 140px', padding: 8, borderRadius: 6, background: pct >= 80 ? '#f6ffed' : pct >= 50 ? '#fffbe6' : '#fff2f0' }}>
                    <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 4 }}>{DIM_LABELS[key]}</div>
                    <Progress percent={pct} size="small" format={() => `${dim.score}/${dim.max}`} strokeColor={dimColor(dim.score, dim.max)} />
                    <div style={{ fontSize: 11, color: '#666', marginTop: 4 }}>{dim.detail}</div>
                  </div>
                );
              })}
            </div>

            <div style={{ marginTop: 8, fontWeight: 600, fontSize: 13, color: '#333' }}>软性匹配 (Block B)</div>
            <div style={{ marginTop: 4, display: 'flex', gap: 12, flexWrap: 'wrap' }}>
              {blockBDims.map((key) => {
                const dim = (detail.dimensions as any)[key];
                if (!dim) return null;
                const pct = Math.round((dim.score / dim.max) * 100);
                return (
                  <div key={key} style={{ flex: '0 0 140px', padding: 8, borderRadius: 6, background: pct >= 80 ? '#f6ffed' : pct >= 50 ? '#fffbe6' : '#fff2f0' }}>
                    <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 4 }}>{DIM_LABELS[key]}</div>
                    <Progress percent={pct} size="small" format={() => `${dim.score}/${dim.max}`} strokeColor={dimColor(dim.score, dim.max)} />
                    <div style={{ fontSize: 11, color: '#666', marginTop: 4 }}>{dim.detail}</div>
                  </div>
                );
              })}
            </div>
          </>
        )}

        {detail.matched_skills?.length > 0 && (
          <>
            <div style={{ marginTop: 8, fontWeight: 600, color: '#52c41a' }}>✅ 匹配技能</div>
            <Space wrap style={{ marginTop: 4 }}>
              {detail.matched_skills.map((s: string, i: number) => <Tag key={i} color="green">{s}</Tag>)}
            </Space>
          </>
        )}
        {detail.missing_skills?.length > 0 && (
          <>
            <div style={{ marginTop: 8, fontWeight: 600, color: '#ff4d4f' }}>❌ 缺失技能</div>
            <Space wrap style={{ marginTop: 4 }}>
              {detail.missing_skills.map((s: string, i: number) => <Tag key={i} color="red">{s}</Tag>)}
            </Space>
          </>
        )}
      </div>
    );
  };

  return (
    <div>
      <Card>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <Title level={4} style={{ margin: 0 }}>🔍 岗位雷达</Title>
          <Space>
            <Input
              placeholder="搜索关键词（如 Python后端）"
              value={crawlKeywords}
              onChange={(e) => setCrawlKeywords(e.target.value)}
              style={{ width: 200 }}
              onPressEnter={handleCrawl}
            />
            <Select placeholder="平台" value={crawlPlatform} onChange={(v) => setCrawlPlatform(v)} style={{ width: 110 }}>
              <Select.Option value="51job">51job</Select.Option>
              <Select.Option value="boss">BOSS直聘</Select.Option>
              <Select.Option value="zhaopin">智联招聘</Select.Option>
            </Select>
            <InputNumber
              min={1} max={20} value={crawlCount}
              onChange={(v) => setCrawlCount(v || 5)}
              style={{ width: 65 }}
              placeholder="数量"
            />
            <Select value={crawlAutoMatch} onChange={(v) => setCrawlAutoMatch(v)} style={{ width: 95 }}>
              <Select.Option value={true}>自动匹配</Select.Option>
              <Select.Option value={false}>仅抓取</Select.Option>
            </Select>
            <Select placeholder="城市" value={crawlCity || undefined} onChange={(v) => setCrawlCity(v || '')} allowClear style={{ width: 100 }}>
              <Select.Option value="">不限</Select.Option>
              <Select.Option value="北京">北京</Select.Option>
              <Select.Option value="上海">上海</Select.Option>
              <Select.Option value="深圳">深圳</Select.Option>
              <Select.Option value="杭州">杭州</Select.Option>
            </Select>
            <Button type="primary" icon={<ApiOutlined />} onClick={handleCrawl} loading={crawling}>
              抓取
            </Button>
            <Button icon={<ReloadOutlined />} onClick={loadJobs}>刷新</Button>
            <Button icon={<ThunderboltOutlined />} onClick={handleBatchMatch}>批量匹配</Button>
            {selectedRowIds.length > 0 && (
              <>
                <Popconfirm title={`确认删除选中的 ${selectedRowIds.length} 个岗位？`} onConfirm={handleBatchDelete}>
                  <Button danger icon={<DeleteOutlined />}>删除选中 ({selectedRowIds.length})</Button>
                </Popconfirm>
              </>
            )}
            <Button icon={<PlusOutlined />} onClick={() => setAddModal(true)}>
              添加
            </Button>
          </Space>
        </div>

        <Space style={{ marginBottom: 16, width: '100%' }}>
          <Input
            placeholder="本地筛选 岗位/公司..."
            prefix={<SearchOutlined />}
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            style={{ width: 250 }}
            allowClear
          />
          <Select
            placeholder="状态"
            value={statusFilter || undefined}
            onChange={(v) => setStatusFilter(v || '')}
            allowClear
            style={{ width: 120 }}
          >
            <Select.Option value="">全部</Select.Option>
            <Select.Option value="matching">匹配中</Select.Option>
            <Select.Option value="matched">已匹配</Select.Option>
            <Select.Option value="new">新</Select.Option>
            <Select.Option value="applied">已投递</Select.Option>
          </Select>
          <Select
            placeholder="最低匹配度"
            value={minScore || undefined}
            onChange={(v) => setMinScore(v || 0)}
            allowClear
            style={{ width: 140 }}
          >
            <Select.Option value={0}>全部</Select.Option>
            <Select.Option value={60}>60% 以上</Select.Option>
            <Select.Option value={80}>80% 以上</Select.Option>
          </Select>
        </Space>

        <Table
          rowSelection={{
            selectedRowKeys: selectedRowIds,
            onChange: (keys) => setSelectedRowIds(keys as number[]),
          }}
          columns={columns}
          dataSource={jobs}
          rowKey="id"
          loading={loading}
          expandable={{
            expandedRowRender,
            rowExpandable: (r) => !!r.match_detail,
          }}
          pagination={{ pageSize: 20, showTotal: (t) => {
            const matched = jobs.filter(j => selectedRowIds.includes(j.id) && (j.status === 'matched' || j.status === 'applied')).length;
            const unmatched = selectedRowIds.length - matched;
            let sel = '';
            if (selectedRowIds.length) {
              const parts: string[] = [];
              if (unmatched) parts.push(`未匹配 ${unmatched}`);
              if (matched) parts.push(`已匹配 ${matched}`);
              sel = `，已选 ${selectedRowIds.length}（${parts.join('，')}）`;
            }
            return `共 ${t} 个岗位${sel}`;
          } }}
          size="small"
        />
      </Card>

      {/* Add Job Modal */}
      <Modal
        title="手动添加岗位"
        open={addModal}
            onOk={handleAdd}
            onCancel={() => {
              setAddModal(false);
              setAddForm({ title: '', company: '', city: '', salary: '', jd_text: '', work_address: '' });
            }}
        width={600}
      >
        <Space direction="vertical" style={{ width: '100%' }}>
          <Input placeholder="岗位名称 *" value={addForm.title} onChange={(e) => setAddForm({ ...addForm, title: e.target.value })} />
          <Input placeholder="公司名称" value={addForm.company} onChange={(e) => setAddForm({ ...addForm, company: e.target.value })} />
          <Input placeholder="城市" value={addForm.city} onChange={(e) => setAddForm({ ...addForm, city: e.target.value })} style={{ width: 200 }} />
          <Input placeholder="薪资范围" value={addForm.salary} onChange={(e) => setAddForm({ ...addForm, salary: e.target.value })} style={{ width: 200 }} />
          <Input placeholder="工作地址" value={addForm.work_address} onChange={(e) => setAddForm({ ...addForm, work_address: e.target.value })} />
          <TextArea
            placeholder="JD 文本（粘贴岗位描述）"
            value={addForm.jd_text}
            onChange={(e) => setAddForm({ ...addForm, jd_text: e.target.value })}
            rows={8}
          />
        </Space>
      </Modal>

      {/* Detail Modal */}
      <Modal
        title={detailJob ? `${detailJob.title} @ ${detailJob.company}` : '岗位详情'}
        open={detailModal}
        onCancel={() => setDetailModal(false)}
        footer={null}
        width={700}
        loading={detailLoading}
      >
        {detailJob && (
          <div>
            <Descriptions column={2} size="small" bordered>
              <Descriptions.Item label="平台">
                <Tag>{detailJob.platform || 'manual'}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="城市">{detailJob.city}</Descriptions.Item>
              <Descriptions.Item label="工作地址">{detailJob.work_address || '-'}</Descriptions.Item>
              <Descriptions.Item label="公司">{detailJob.company || '-'}</Descriptions.Item>
              <Descriptions.Item label="薪资">{detailJob.salary || '-'}</Descriptions.Item>
              <Descriptions.Item label="来源">
                {detailJob.jd_url ? (
                  <a href={detailJob.jd_url} target="_blank" rel="noreferrer">查看源岗位</a>
                ) : '-'}
              </Descriptions.Item>
              <Descriptions.Item label="匹配度">
                {detailJob.match_score !== null ? (
                  <Progress percent={detailJob.match_score} strokeColor={scoreColor(detailJob.match_score)} />
                ) : '未匹配'}
              </Descriptions.Item>
            </Descriptions>

            {detailJob.match_detail && (
              <Card size="small" title="匹配分析" style={{ marginTop: 16 }}>
                <Text type="secondary">{detailJob.match_detail.summary}</Text>

                {detailJob.match_detail.dimensions && (
                  <>
                    <div style={{ marginTop: 12, fontWeight: 600, fontSize: 13, color: '#333' }}>硬性匹配 (Block A)</div>
                    <div style={{ marginTop: 4, display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                      {['education', 'experience', 'skills', 'location', 'salary'].map((key) => {
                        const dim = detailJob.match_detail.dimensions[key];
                        if (!dim) return null;
                        const pct = Math.round((dim.score / dim.max) * 100);
                        return (
                          <div key={key} style={{ flex: '0 0 130px', padding: 8, borderRadius: 6, textAlign: 'center',
                            background: pct >= 80 ? '#f6ffed' : pct >= 50 ? '#fffbe6' : '#fff2f0' }}>
                            <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 2 }}>{DIM_LABELS[key]}</div>
                            <div style={{ fontSize: 20, fontWeight: 700, color: pct >= 80 ? '#52c41a' : pct >= 50 ? '#faad14' : '#ff4d4f' }}>
                              {dim.score}/{dim.max}
                            </div>
                            <div style={{ fontSize: 11, color: '#888' }}>{dim.detail}</div>
                          </div>
                        );
                      })}
                    </div>

                    <div style={{ marginTop: 12, fontWeight: 600, fontSize: 13, color: '#333' }}>软性匹配 (Block B)</div>
                    <div style={{ marginTop: 4, display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                      {['responsibility', 'industry', 'complexity'].map((key) => {
                        const dim = detailJob.match_detail.dimensions[key];
                        if (!dim) return null;
                        const pct = Math.round((dim.score / dim.max) * 100);
                        return (
                          <div key={key} style={{ flex: '0 0 130px', padding: 8, borderRadius: 6, textAlign: 'center',
                            background: pct >= 80 ? '#f6ffed' : pct >= 50 ? '#fffbe6' : '#fff2f0' }}>
                            <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 2 }}>{DIM_LABELS[key]}</div>
                            <div style={{ fontSize: 20, fontWeight: 700, color: pct >= 80 ? '#52c41a' : pct >= 50 ? '#faad14' : '#ff4d4f' }}>
                              {dim.score}/{dim.max}
                            </div>
                            <div style={{ fontSize: 11, color: '#888' }}>{dim.detail}</div>
                          </div>
                        );
                      })}
                    </div>
                  </>
                )}

                {detailJob.match_detail.matched_skills?.length > 0 && (
                  <>
                    <div style={{ marginTop: 8, fontWeight: 600, color: '#52c41a' }}>✅ 匹配技能</div>
                    <Space wrap style={{ marginTop: 4 }}>
                      {detailJob.match_detail.matched_skills.map((s: string, i: number) => <Tag key={i} color="green">{s}</Tag>)}
                    </Space>
                  </>
                )}
                {detailJob.match_detail.missing_skills?.length > 0 && (
                  <>
                    <div style={{ marginTop: 8, fontWeight: 600, color: '#ff4d4f' }}>❌ 缺失技能</div>
                    <Space wrap style={{ marginTop: 4 }}>
                      {detailJob.match_detail.missing_skills.map((s: string, i: number) => <Tag key={i} color="red">{s}</Tag>)}
                    </Space>
                  </>
                )}
              </Card>
            )}

            <Card size="small" title="JD 原文" style={{ marginTop: 16 }}>
              <pre style={{ whiteSpace: 'pre-wrap', fontSize: 13, maxHeight: 300, overflow: 'auto' }}>
                {detailJob.jd_text || '无'}
              </pre>
            </Card>
          </div>
        )}
      </Modal>
    </div>
  );
}
