import { useState, useEffect, useCallback } from 'react';
import dayjs from 'dayjs';
import {
  Button, Table, Tag, Modal, Form, Input, DatePicker, Select, Space, Popconfirm, message, Spin, Tooltip,
} from 'antd';
import type { Dayjs } from 'dayjs';
import { PlusOutlined, EditOutlined, DeleteOutlined, LoadingOutlined, CheckCircleOutlined, CloseCircleOutlined, DownloadOutlined, ThunderboltOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import type { TablePaginationConfig } from 'antd/es/table/interface';
import ApplicantProfileModal from './ApplicantProfileModal';
import {
  listInterviewGuides, getInterviewGuide, createInterviewGuide, updateInterviewGuide, deleteInterviewGuide,
  generateReport, cancelReport, getTaskStatus, downloadReport, previewReport, updateStatus,
} from '../../api/interviewGuide';
import type { InterviewGuide, TaskStatus } from '../../api/interviewGuide';

const STATUS_MAP: Record<string, { label: string; color: string }> = {
  pending: { label: '待确认', color: 'orange' },
  confirmed: { label: '已确认', color: 'green' },
  cancelled: { label: '已取消', color: 'red' },
  completed: { label: '已完成', color: 'blue' },
};

const SOURCE_MAP: Record<string, { label: string; color: string }> = {
  manual: { label: '手动', color: 'blue' },
  visitor: { label: '访客', color: 'purple' },
  agent: { label: 'Agent', color: 'cyan' },
};

export default function InterviewGuidePage() {
  const [data, setData] = useState<InterviewGuide[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [size, setSize] = useState(20);
  const [company, setCompany] = useState('');
  const [status, setStatus] = useState('');
  const [loading, setLoading] = useState(false);
  const [taskStatusMap, setTaskStatusMap] = useState<Record<number, TaskStatus>>({});
  const [generatingIds, setGeneratingIds] = useState<Set<number>>(new Set());
  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form] = Form.useForm();
  const [previewVisible, setPreviewVisible] = useState(false);
  const [previewHtml, setPreviewHtml] = useState('');
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewGuideId, setPreviewGuideId] = useState<number | null>(null);
  const [previewCompanyName, setPreviewCompanyName] = useState('');
  const [modalVersion, setModalVersion] = useState(0);
  const [editInitialValues, setEditInitialValues] = useState<Record<string, unknown> | null>(null);
  const [isClone, setIsClone] = useState(false);
  const [profileModalOpen, setProfileModalOpen] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await listInterviewGuides({ page, size, company: company || undefined, status: status || undefined });
      setData(res.items);
      setTotal(res.total);
      // Fetch task status for each record in parallel
      const statusResults = await Promise.allSettled(
        res.items.map(item => getTaskStatus(item.id))
      );
      const statusMap: Record<number, TaskStatus> = {};
      statusResults.forEach((result, idx) => {
        if (result.status === 'fulfilled' && result.value.status !== 'none') {
          statusMap[res.items[idx].id] = result.value;
        }
      });
      if (Object.keys(statusMap).length > 0) {
        setTaskStatusMap(prev => ({ ...prev, ...statusMap }));
      }
    } catch {
      message.error('加载数据失败');
    } finally {
      setLoading(false);
    }
  }, [page, size, company, status]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleTableChange = (pagination: TablePaginationConfig) => {
    setPage(pagination.current ?? 1);
    setSize(pagination.pageSize ?? 20);
  };

  const handleSearch = () => {
    setPage(1);
  };

  const handleReset = () => {
    setCompany('');
    setStatus('');
    setPage(1);
  };

  const openCreate = () => {
    setEditingId(null);
    setIsClone(false);
    setEditInitialValues(null);
    form.resetFields();
    setModalVersion(v => v + 1);
    setModalOpen(true);
  };

  const openEdit = async (record: InterviewGuide) => {
    setEditingId(record.id);
    setIsClone(false);
    try {
      const detail = await getInterviewGuide(record.id);
      const values = {
        company_name: detail.company_name,
        company_description: detail.company_description,
        job_title: detail.job_title,
        salary: detail.salary || '',
        hr_name: detail.hr_name,
        hr_phone: detail.hr_phone,
        hr_email: detail.hr_email,
        interview_address: detail.interview_address,
        address_type: detail.address_type || 'offline',
        video_link: detail.video_link || '',
        interview_round: detail.interview_round || '',
        interview_time: detail.interview_time ? dayjs(detail.interview_time) : null,
        jd_text: detail.jd_text,
        result: detail.result || undefined,
      };
      setEditInitialValues(values);
      setModalVersion(v => v + 1);
      setModalOpen(true);
      // Directly set form values after the new Form mounts
      setTimeout(() => {
        form.setFieldsValue(values);
      }, 0);
    } catch {
      message.error('获取详情失败');
    }
  };

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      const payload = {
        company_name: values.company_name,
        company_description: values.company_description || '',
        job_title: values.job_title,
        salary: values.salary || '',
        hr_name: values.hr_name || '',
        hr_phone: values.hr_phone || '',
        hr_email: values.hr_email || '',
        interview_address: values.interview_address || '',
        address_type: values.address_type || 'offline',
        video_link: values.video_link || '',
        interview_round: values.interview_round || '',
        interview_time: values.interview_time
          ? (typeof values.interview_time === 'string' ? values.interview_time : values.interview_time.format('YYYY-MM-DD HH:mm:ss'))
          : null,
        jd_text: values.jd_text || '',
        result: values.result || '',
      };
      if (editingId !== null) {
        await updateInterviewGuide(editingId, payload);
        message.success('更新成功');
      } else {
        await createInterviewGuide(payload);
        message.success('创建成功');
      }
      setModalOpen(false);
      fetchData();
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'errorFields' in err) {
        return;
      }
      message.error('保存失败');
    }
  };

  const handleClone = async (record: InterviewGuide) => {
    try {
      const detail = await getInterviewGuide(record.id);
      const values = {
        company_name: detail.company_name,
        company_description: detail.company_description,
        job_title: detail.job_title,
        salary: detail.salary || '',
        hr_name: detail.hr_name,
        hr_phone: detail.hr_phone,
        hr_email: detail.hr_email,
        interview_address: detail.interview_address,
        address_type: detail.address_type || 'offline',
        video_link: detail.video_link || '',
        interview_round: '',
        interview_time: null,
        jd_text: detail.jd_text,
        result: undefined,
      };
      setEditingId(null);
      setIsClone(true);
      setEditInitialValues(values);
      setModalVersion(v => v + 1);
      setModalOpen(true);
    } catch {
      message.error('获取详情失败');
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteInterviewGuide(id);
      message.success('删除成功');
      fetchData();
    } catch {
      message.error('删除失败');
    }
  };

  const formatTime = (value: string | null) => {
    if (!value) return '-';
    try {
      return new Date(value).toLocaleString('zh-CN');
    } catch {
      return value;
    }
  };

  const handleDownload = async (guideId: number, companyName?: string) => {
    try {
      const blob = await downloadReport(guideId);
      const url = window.URL.createObjectURL(new Blob([blob]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `面试报告_${companyName || guideId}.pdf`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch {
      message.error('下载报告失败');
    }
  };


  const handlePreview = async (record: InterviewGuide) => {
    setPreviewLoading(true);
    setPreviewGuideId(record.id);
    setPreviewCompanyName(record.company_name);
    setPreviewVisible(true);
    try {
      const html = await previewReport(record.id);
      setPreviewHtml(html);
    } catch {
      message.error('加载预览失败');
      setPreviewVisible(false);
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleDownloadFromPreview = async () => {
    if (previewGuideId === null) return;
    const record = data.find((r: InterviewGuide) => r.id === previewGuideId);
    const companyName = record?.company_name || String(previewGuideId);
    try {
      const blob = await downloadReport(previewGuideId);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `面试报告_${companyName}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch {
      message.error('下载失败');
    }
  };

  const handleCancel = async (guideId: number) => {
    try {
      await cancelReport(guideId);
      message.success('已取消报告生成');
      setGeneratingIds(prev => {
        const next = new Set(prev);
        next.delete(guideId);
        return next;
      });
      setTaskStatusMap(prev => ({
        ...prev,
        [guideId]: { status: 'cancelled', started_at: null, completed_at: null, error_message: '用户取消', pdf_path: null },
      }));
    } catch {
      message.error('取消失败');
    }
  };

  const pollTaskStatus = (guideId: number) => {
    const interval = window.setInterval(async () => {
      try {
        const taskStatus = await getTaskStatus(guideId);
        setTaskStatusMap(prev => ({ ...prev, [guideId]: taskStatus }));
        if (taskStatus.status === 'done') {
          window.clearInterval(interval);
          setGeneratingIds(prev => {
            const next = new Set(prev);
            next.delete(guideId);
            return next;
          });
          message.success({ content: '报告生成完成', key: `gen-${guideId}` });
        } else if (taskStatus.status === 'failed') {
          window.clearInterval(interval);
          setGeneratingIds(prev => {
            const next = new Set(prev);
            next.delete(guideId);
            return next;
          });
          message.error({ content: `报告生成失败: ${taskStatus.error_message}`, key: `gen-${guideId}` });
        } else if (taskStatus.status === 'cancelled') {
          window.clearInterval(interval);
          setGeneratingIds(prev => {
            const next = new Set(prev);
            next.delete(guideId);
            return next;
          });
          message.info({ content: '报告生成已取消', key: `gen-${guideId}` });
        }
      } catch {
        window.clearInterval(interval);
      }
    }, 3000);
  };

  const handleStatusChange = async (guideId: number, newStatus: string) => {
    try {
      await updateStatus(guideId, newStatus);
      message.success('状态已更新');
      fetchData();
    } catch {
      message.error('状态更新失败');
    }
  };

  const handleGenerate = async (guideId: number) => {
    setGeneratingIds(prev => new Set(prev).add(guideId));
    try {
      await generateReport(guideId);
      message.loading({ content: '报告生成中...', key: `gen-${guideId}` });
      pollTaskStatus(guideId);
    } catch {
      message.error('触发报告生成失败');
      setGeneratingIds(prev => {
        const next = new Set(prev);
        next.delete(guideId);
        return next;
      });
    }
  };

  const columns: ColumnsType<InterviewGuide> = [
    {
      title: '公司名称',
      dataIndex: 'company_name',
      key: 'company_name',
      width: 180,
    },
    {
      title: '岗位',
      dataIndex: 'job_title',
      key: 'job_title',
      width: 160,
    },
    {
      title: '薪资',
      dataIndex: 'salary',
      key: 'salary',
      width: 140,
      render: (v: string) => v || '-',
    },
    {
      title: 'HR姓名',
      dataIndex: 'hr_name',
      key: 'hr_name',
      width: 100,
      render: (v: string) => v || '-',
    },
    {
      title: 'HR电话',
      dataIndex: 'hr_phone',
      key: 'hr_phone',
      width: 120,
      render: (v: string) => v || '-',
    },
    {
      title: 'HR邮箱',
      dataIndex: 'hr_email',
      key: 'hr_email',
      width: 180,
      render: (v: string) => v ? <a href={`mailto:${v}`}>{v}</a> : '-',
    },
    {
      title: '面试时间',
      dataIndex: 'interview_time',
      key: 'interview_time',
      width: 180,
      render: (v: string | null) => formatTime(v),
    },
    {
      title: '面试地址',
      key: 'address',
      width: 220,
      render: (_: unknown, record: InterviewGuide) => {
        const isOnline = record.address_type === 'online';
        return (
          <Space>
            {isOnline ? (
              record.video_link ? (
                <a href={record.video_link} target="_blank" rel="noopener noreferrer">
                  {record.video_link.length > 30 ? record.video_link.slice(0, 30) + '...' : record.video_link}
                </a>
              ) : <span>-</span>
            ) : (
              <span>{record.interview_address || '-'}</span>
            )}
            <Tag color={isOnline ? 'blue' : 'green'}>{isOnline ? '线上' : '线下'}</Tag>
          </Space>
        );
      },
    },
    {
      title: '面试阶段',
      dataIndex: 'interview_round',
      key: 'interview_round',
      width: 120,
      render: (v: string) => v ? <Tag color="purple">{v}</Tag> : '-',
    },
    {
      title: '通勤',
      key: 'commute',
      width: 100,
      render: (_: unknown, record: InterviewGuide) => {
        if (record.commute_duration_min != null) {
          const dist = record.commute_distance_km != null ? ` ${record.commute_distance_km.toFixed(1)}km` : '';
          return `${record.commute_duration_min}min${dist}`;
        }
        return '-';
      },
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 120,
      render: (v: string, record: InterviewGuide) => {
        const item = STATUS_MAP[v];
        const tag = item ? <Tag color={item.color}>{item.label}</Tag> : <Tag>{v || '待确认'}</Tag>;
        return (
          <Select
            value={v || 'pending'}
            size="small"
            style={{ width: 100 }}
            onChange={(newVal) => handleStatusChange(record.id, newVal)}
            options={[
              { value: 'pending', label: '待确认' },
              { value: 'confirmed', label: '已确认' },
              { value: 'cancelled', label: '已取消' },
              { value: 'completed', label: '已完成' },
            ]}
          />
        );
      },
    },
    {
      title: '面试结果',
      dataIndex: 'result',
      key: 'result',
      width: 110,
      render: (v: string) => {
        const colorMap: Record<string, string> = { '成功': 'green', '失败': 'red', 'offer': 'blue' };
        return v ? <Tag color={colorMap[v] || 'default'}>{v}</Tag> : '-';
      },
    },
    {
      title: '来源',
      dataIndex: 'source',
      key: 'source',
      width: 90,
      render: (v: string) => {
        const item = SOURCE_MAP[v];
        if (!item) return <Tag>{v}</Tag>;
        return <Tag color={item.color}>{item.label}</Tag>;
      },
    },
    {
      title: '报告',
      key: 'report',
      width: 120,
      render: (_: unknown, record: InterviewGuide) => {
        const hasReport = !!(record.generated_report_md);
        const task = taskStatusMap[record.id];
        if (!task || task.status === 'none') {
          if (hasReport) return (
            <Space size={4}>
              <Tag icon={<CheckCircleOutlined />} color="success">已生成</Tag>
              <Button type="link" size="small" onClick={() => handlePreview(record)} style={{ padding: 0 }}>预览</Button>
            </Space>
          );
          return '-';
        }
        if (task.status === 'done') {
          if (hasReport) return (
            <Space size={4}>
              <Tag icon={<CheckCircleOutlined />} color="success">已生成</Tag>
              <Button type="link" size="small" onClick={() => handlePreview(record)} style={{ padding: 0 }}>预览</Button>
            </Space>
          );
          return <Tag color="warning">内容为空</Tag>;
        }
        if (task.status === 'running' || task.status === 'pending') return <Spin indicator={<LoadingOutlined spin />} size="small" />;
        if (task.status === 'failed') {
          if (hasReport) return (
            <Space size={4}>
              <Tooltip title={task.error_message}><Tag icon={<CloseCircleOutlined />} color="warning">PDF生成失败</Tag></Tooltip>
              <Button type="link" size="small" onClick={() => handlePreview(record)} style={{ padding: 0 }}>预览</Button>
            </Space>
          );
          return <Tooltip title={task.error_message}><Tag icon={<CloseCircleOutlined />} color="error">失败</Tag></Tooltip>;
        }
        if (task.status === 'cancelled') return <Tag icon={<CloseCircleOutlined />} color="default">已取消</Tag>;
        return <Tag>{task.status}</Tag>;
      },
    },
    {
      title: '操作',
      key: 'actions',
      width: 200,
      render: (_: unknown, record: InterviewGuide) => {
        const task = taskStatusMap[record.id];
        const isGenerating = generatingIds.has(record.id) || task?.status === 'running' || task?.status === 'pending';
        const isDone = task?.status === 'done' || !!(record.generated_report_md);
        return (
          <Space>
            {isGenerating ? (
              <Button type="link" danger icon={<CloseCircleOutlined />} onClick={() => handleCancel(record.id)}>
                取消
              </Button>
            ) : (
            <Button type="link" icon={<ThunderboltOutlined />} onClick={() => handleGenerate(record.id)}>
              {(record.generated_report_md || task?.status === 'done') ? '重新生成' : '生成报告'}
            </Button>
            )}
            {isDone && (
              <>
                <Button type="link" icon={<DownloadOutlined />} onClick={() => handleDownload(record.id, record.company_name)}>
                  下载PDF
                </Button>
              </>
            )}
            <Button type="link" size="small" icon={<EditOutlined />} onClick={() => openEdit(record)}>
              编辑
            </Button>
            <Button type="link" size="small" onClick={() => handleClone(record)}>
              克隆
            </Button>
            <Popconfirm title="确认删除？" okText="确认" cancelText="取消" onConfirm={() => handleDelete(record.id)}>
              <Button type="link" size="small" danger icon={<DeleteOutlined />}>
                删除
              </Button>
            </Popconfirm>
          </Space>
        );
      },
    },
  ];

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <h2 style={{ margin: 0, color: 'var(--admin-text)' }}>面试宝典</h2>
        <p style={{ margin: '4px 0 0', color: 'var(--admin-text-secondary)', fontSize: 13 }}>
          管理邀约安排、面试地址及面试指南
        </p>
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        <Input
          placeholder="搜索公司名称"
          value={company}
          onChange={e => setCompany(e.target.value)}
          onPressEnter={handleSearch}
          style={{ width: 200 }}
          allowClear
          onClear={handleReset}
        />
        <Select
          value={status}
          onChange={setStatus}
          style={{ width: 140 }}
          placeholder="状态筛选"
          allowClear
          options={[
            { value: '', label: '全部' },
            { value: 'pending', label: '待确认' },
            { value: 'confirmed', label: '已确认' },
            { value: 'cancelled', label: '已取消' },
            { value: 'completed', label: '已完成' },
          ]}
        />
        <Button onClick={handleSearch} type="primary">搜索</Button>
        <Button onClick={handleReset}>重置</Button>
        <Button onClick={() => setProfileModalOpen(true)}>
          求职设置
        </Button>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          新增面试
        </Button>
      </div>

      <Table<InterviewGuide>
        rowKey="id"
        columns={columns}
        dataSource={data}
        loading={loading}
        onChange={handleTableChange}
        pagination={{
          current: page,
          pageSize: size,
          total,
          showSizeChanger: true,
          showTotal: (t) => `共 ${t} 条`,
        }}
        scroll={{ x: 2000 }}
      />

      <Modal
        key={modalVersion}
        title={editingId !== null ? '编辑面试' : isClone ? '克隆面试' : '新增面试'}
        open={modalOpen}
        onOk={handleSave}
        onCancel={() => { setModalOpen(false); }}
        okText={isClone ? '克隆' : editingId !== null ? '保存' : '新增'}
        cancelText="取消"
        destroyOnClose
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }} initialValues={editInitialValues || undefined}>
          <Form.Item
            name="company_name"
            label="公司名称"
            rules={[{ required: true, message: '请输入公司名称' }]}
          >
            <Input placeholder="请输入公司名称" maxLength={100} />
          </Form.Item>
          <Form.Item
            name="job_title"
            label="岗位"
            rules={[{ required: true, message: '请输入岗位' }]}
          >
            <Input placeholder="请输入岗位" maxLength={100} />
          </Form.Item>
          <Form.Item name="salary" label="薪资">
            <Input placeholder="如 15k-25k·14薪" maxLength={100} />
          </Form.Item>
          <Form.Item name="company_description" label="公司描述">
            <Input.TextArea placeholder="公司简介、主营业务、行业等（用于搜索消歧）" rows={2} maxLength={500} showCount />
          </Form.Item>
          <Form.Item name="jd_text" label="岗位描述 (JD)">
            <Input.TextArea rows={4} placeholder="粘贴招聘岗位描述，用于生成个性化面试报告" maxLength={5000} showCount />
          </Form.Item>
          <Form.Item name="hr_name" label="HR姓名">
            <Input placeholder="请输入HR姓名" maxLength={50} />
          </Form.Item>
          <Form.Item name="hr_phone" label="HR电话">
            <Input placeholder="请输入HR电话" maxLength={20} />
          </Form.Item>
          <Form.Item name="hr_email" label="HR邮箱">
            <Input placeholder="请输入HR邮箱" maxLength={100} />
          </Form.Item>
          <Form.Item name="address_type" label="地址类型" initialValue="offline">
            <Select>
              <Select.Option value="offline">线下（实体地址）</Select.Option>
              <Select.Option value="online">线上（视频面试）</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item noStyle shouldUpdate={(prev, cur) => prev.address_type !== cur.address_type}>
            {({ getFieldValue }) =>
              getFieldValue('address_type') === 'online' ? (
                <Form.Item name="video_link" label="视频链接">
                  <Input placeholder="如 https://meeting.tencent.com/xxx" maxLength={500} />
                </Form.Item>
              ) : (
                <Form.Item name="interview_address" label="面试地址">
                  <Input placeholder="请输入面试地址" maxLength={200} />
                </Form.Item>
              )
            }
          </Form.Item>
          <Form.Item name="interview_round" label="面试阶段">
            <Select placeholder="选择面试阶段" showSearch allowClear>
              <Select.Option value="一面">一面</Select.Option>
              <Select.Option value="二面">二面</Select.Option>
              <Select.Option value="三面">三面</Select.Option>
              <Select.Option value="技术面">技术面</Select.Option>
              <Select.Option value="HR面">HR面</Select.Option>
              <Select.Option value="部门主管面">部门主管面</Select.Option>
              <Select.Option value="Boss面">Boss面</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item name="interview_time" label="面试时间" rules={[{ required: true, message: '请选择面试时间' }]}>
            <DatePicker
              showTime={{ format: 'HH:mm', minuteStep: 1 }}
              format="YYYY-MM-DD HH:mm"
              style={{ width: '100%' }}
              disabledDate={(current: Dayjs | null) => {
                if (!current) return false;
                return current.isBefore(dayjs().startOf('day'), 'day');
              }}
              disabledTime={(current: Dayjs | null) => {
                if (!current || !current.isSame(dayjs(), 'day')) return {};
                const now = dayjs();
                return {
                  disabledHours: () => Array.from({ length: now.hour() }, (_, i) => i),
                  disabledMinutes: (hour: number) => {
                    if (hour === now.hour()) {
                      return Array.from({ length: now.minute() }, (_, i) => i);
                    }
                    return [];
                  },
                };
              }}
            />
          </Form.Item>
          <Form.Item name="result" label="面试结果">
            <Select placeholder="选择面试结果" allowClear>
              <Select.Option value="成功">成功</Select.Option>
              <Select.Option value="失败">失败</Select.Option>
              <Select.Option value="offer">offer</Select.Option>
            </Select>
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={`面试报告预览 - ${previewCompanyName}`}
        open={previewVisible}
        onCancel={() => setPreviewVisible(false)}
        width={900}
        footer={[
          <Button key="close" onClick={() => setPreviewVisible(false)}>关闭</Button>,
          <Button key="download-pdf" type="primary" icon={<DownloadOutlined />} onClick={handleDownloadFromPreview} disabled={previewGuideId === null}>
            下载PDF
          </Button>,
        ]}
        style={{ top: 20 }}
      >
        <Spin spinning={previewLoading}>
          <div style={{ maxHeight: '70vh', overflow: 'auto', background: '#fff' }}>
            <iframe
              srcDoc={previewHtml}
              style={{ width: '100%', height: '70vh', border: 'none' }}
              title="报告预览"
            />
          </div>
        </Spin>
      </Modal>

      <ApplicantProfileModal open={profileModalOpen} onClose={() => setProfileModalOpen(false)} />
    </div>
  );
}
