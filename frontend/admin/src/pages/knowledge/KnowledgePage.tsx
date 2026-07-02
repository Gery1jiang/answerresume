import dayjs from 'dayjs';
import 'dayjs/locale/zh-cn';
dayjs.locale('zh-cn');
import { useState, useEffect, useCallback } from 'react';
import {
  Tabs, Card, Form, Input, Button, message, Upload, Table, Modal, Space, Tag, Select, InputNumber, DatePicker, Checkbox,
} from 'antd';
import {
  UploadOutlined, DeleteOutlined, ClearOutlined, ReloadOutlined, PlusOutlined, EyeOutlined, ThunderboltOutlined,
} from '@ant-design/icons';
import api from '../../api';
import {
  getKnowledgeStructured, saveKnowledgeStructured,
  rebuildVector, getAppendixInfo, getAppendixRecords, deleteAppendixRecord,
  clearAppendix, uploadAppendix, clearFaqAnswers,
} from '../../api/knowledge';

const { TextArea } = Input;

// ============================================================
// Single-record forms: personal_info, skills
// ============================================================

const SEED_PERSONAL = {
  name: '江汉辉', age: 31, city: '杭州', email: 'cnredink@163.com',
  phone: '15880382392', github: 'Gery1jiang', personal_website: 'https://gery1jiang.github.io',
  wechat_name: 'wysdx12345', wechat_qr: '',
  work_years: 5, current_status: '离职-一周内到岗', target_position: '产品经理',
  expected_location: '杭州', start_date: '一周内', salary_expectation: '15K-25K',
  job_tags: 'B端产品\nAI产品\n政务大数据\n智慧政务\n全生命周期产品管理',
  self_intro: '5年B端AI产品经验，从人工智能训练师起步成长为独立负责产品线的产品经理。擅长对话机器人、政务大数据、情指行一体化等方向，主导过从0到1的项目落地并实现千万级创收。',
};

const SEED_FAQ = [
  { question: '期望薪资是多少？', answer: '基于我5年B端AI及政务大数据产品经验，主导过多个百万到千万级项目并具备全生命周期管理能力，期望月薪在15K-25K之间，具体可根据岗位职责、公司薪酬结构和福利待遇综合协商确定。' },
  { question: '核心优势是什么？', answer: '第一，具备从0到1的完整产品落地能力——以交警智慧政务项目为例，5个月内完成立项到上线，服务30万群众、192万次咨询；第二，跨领域融合能力，覆盖AI对话机器人、政法大数据、数据中台等多个方向，能快速理解不同业务场景的核心需求；第三，千万级项目管理能力，熟悉政务数字化从售前到交付全流程。' },
  { question: '离职原因是什么？', answer: '寻求更好的职业发展机会，希望在政务大数据和AI产品方向有更深入的实践。' },
  { question: '为什么从上一家公司离职？', answer: '寻求更好的职业发展机会，希望在政务大数据和AI产品方向有更深入的实践。' },
  { question: '为什么选择我们公司？', answer: '贵公司在政务数字化和AI领域的布局与我的项目经验高度匹配，我过往在交警智慧政务、省情指行、数据中台等方向的经验可以直接复用，希望能借助我的产品能力帮助公司在政务赛道取得更大突破。' },
  { question: '你对加班怎么看？', answer: '项目关键期可以接受高强度加班，过往经历中交警智慧政务项目5个月内从立项到全渠道上线就是高强度推进的成果。同时我也注重高效规划，减少无效加班。' },
  { question: '职业规划是什么？', answer: '未来3-5年深耕政务大数据+AI方向，从产品负责人向解决方案专家方向成长，希望能主导更多千万级政务数字化项目。' },
  { question: '带过团队吗？', answer: '带过5-8人产品团队，同时协调过前端、后端、算法、测试等多职能团队。具备多方协作和项目推进经验。' },
  { question: '核心项目经验是什么？', answer: '主导过交警智慧政务（服务30万群众、192万次咨询）、省情指行一体化平台（大模型智能派警、多源系统融合）、远程视频取证平台（区块链存证、覆盖700+群众400+案件）、数据中台（多委办局全域数据治理、自动化治理闭环）等多个政务数字化项目，合同总额超千万。' },
  { question: '你做过的成功AI产品？', answer: '成功交付多个AI+政务产品：交警AI对话机器人（服务30万群众、192万次咨询）、省情指行一体化平台的AI智能派警（警情流转缩短60%）、远程视频取证的区块链存证体系、数据中台自动化数据治理闭环（替代传统人工校对模式，大幅缩减人力成本与工作周期）。' },
  { question: '你擅长什么产品方向？', answer: '专注B端和G端产品，尤其擅长政务数字化、AI对话机器人、数据治理中台方向。能快速理解业务需求并转化为可落地的产品方案，熟悉政务数字化从售前方案到交付验收的全流程。' },
  { question: '你做过产品从0到1吗？', answer: '做过。交警智慧政务项目就是典型案例——5个月内从立项到全渠道上线，成为公司首款to G对话机器人产品，上线1年累计服务用户超30万，咨询量达192万余次，成为浙里办等省级AI咨询项目标杆案例。' },
  { question: '你如何看待AI技术的发展？', answer: '作为AI产品经理，我持续关注大模型和AI Agent的演进趋势。在省情指行项目中已实践大模型智能派警，在数据中台中应用自动化治理能力。我认为AI的价值在于切实解决业务痛点，而不是为了技术而技术。' },
  { question: '最快多久到岗？', answer: '离职状态，一个月内可以到岗。' },
  { question: '你期望的工作环境？', answer: '希望加入技术驱动、产品导向的团队，有清晰的业务方向和足够的资源支持，能真正发挥我的产品能力和项目经验。' },
];

function PersonalInfoForm({ data, onSave, loading }: { data: any; onSave: (v: any) => void; loading: boolean }) {
  const [form] = Form.useForm();

  useEffect(() => {
    form.setFieldsValue({
      name: data?.name ?? '',
      age: data?.age ?? '',
      city: data?.city ?? '',
      email: data?.email ?? '',
      phone: data?.phone ?? '',
      github: data?.github ?? '',
      personal_website: data?.personal_website ?? '',
      wechat_name: data?.wechat_name ?? '',
      wechat_qr: data?.wechat_qr ?? '',
      work_years: data?.work_years ?? '',
      current_status: data?.current_status ?? '',
      target_position: data?.target_position ?? '',
      expected_location: data?.expected_location ?? '',
      start_date: data?.start_date ?? '',
      salary_expectation: data?.salary_expectation ?? '',
      job_tags: data?.job_tags?.join('\n') ?? '',
      self_intro: data?.self_intro ?? '',
    });
  }, [data, form, onSave]);

  return (
    <Form form={form} layout="vertical" onFinish={(v) => {
      onSave({
        name: v.name,
        age: v.age,
        city: v.city,
        email: v.email,
        phone: v.phone,
        github: v.github,
        personal_website: v.personal_website,
        wechat_name: v.wechat_name,
        wechat_qr: v.wechat_qr,
        work_years: v.work_years,
        current_status: v.current_status,
        target_position: v.target_position,
        expected_location: v.expected_location,
        start_date: v.start_date,
        salary_expectation: v.salary_expectation,
        job_tags: v.job_tags ? v.job_tags.split('\n').filter(Boolean).map((s: string) => s.trim()) : [],
        self_intro: v.self_intro,
      });
    }}>
      <Form.Item name="name" label="姓名" rules={[{ required: true, message: '请输入姓名' }, { max: 50, message: '姓名不超过50字' }]}><Input /></Form.Item>
      <Form.Item name="age" label="年龄" rules={[{ type: 'number', min: 0, max: 150, message: '年龄范围0-150' }]}><InputNumber style={{ width: '100%' }} min={0} max={150} /></Form.Item>
      <Form.Item name="city" label="所在城市" rules={[{ max: 50, message: '不超过50字' }]}><Input /></Form.Item>
      <Form.Item name="email" label="邮箱" rules={[{ type: 'email', message: '邮箱格式不正确' }]}><Input /></Form.Item>
      <Form.Item name="phone" label="电话" rules={[{ pattern: /^1[3-9]\d{9}$/, message: '手机号格式不正确（11位）' }]}><Input maxLength={11} /></Form.Item>
      <Form.Item name="github" label="GitHub" rules={[{ type: 'url', message: '请输入正确的URL' }]}><Input /></Form.Item>
      <Form.Item name="personal_website" label="个人网站" rules={[{ type: 'url', message: '请输入正确的URL' }]}><Input placeholder="https://" /></Form.Item>
      <Form.Item name="wechat_name" label="微信昵称"><Input placeholder="用于主页展示" /></Form.Item>
      <Form.Item name="wechat_qr" label="微信二维码图片">
        <Input placeholder="图片URL或上传二维码图片" />
      </Form.Item>
      <Form.Item label="上传二维码">
        <Upload
          accept="image/*"
          showUploadList={false}
          customRequest={async ({ file, onSuccess, onError }) => {
            try {
              const formData = new FormData();
              formData.append('file', file as Blob);
              const resp = await api.post('/admin/upload/qrcode', formData, {
                headers: { 'Content-Type': 'multipart/form-data' },
              });
              form.setFieldsValue({ wechat_qr: resp.data.url });
              onSuccess?.(resp.data);
              message.success('二维码上传成功');
            } catch (e: any) {
              onError?.(e);
              message.error('上传失败: ' + (e?.message || '未知错误'));
            }
          }}
        >
          <Button icon={<UploadOutlined />}>选择图片上传</Button>
        </Upload>
      </Form.Item>
      <Form.Item name="work_years" label="工作年限" rules={[{ type: 'number', min: 0, max: 60, message: '范围0-60年' }]}><InputNumber style={{ width: '100%' }} min={0} max={60} /></Form.Item>
      <Form.Item name="current_status" label="当前状态" rules={[{ max: 100, message: '不超过100字' }]}><Input /></Form.Item>
      <Form.Item name="target_position" label="意向岗位" rules={[{ max: 100, message: '不超过100字' }]}><Input /></Form.Item>
      <Form.Item name="expected_location" label="期望工作地点" rules={[{ max: 100, message: '不超过100字' }]}><Input /></Form.Item>
      <Form.Item name="start_date" label="到岗时间" rules={[{ max: 100, message: '不超过100字' }]}><Input placeholder="如：一个月内" /></Form.Item>
      <Form.Item name="salary_expectation" label="薪资期望范围" rules={[{ max: 100, message: '不超过100字' }]}><Input /></Form.Item>
      <Form.Item name="job_tags" label="职业标签（每行一个）" rules={[{ max: 500, message: '不超过500字' }]}><TextArea rows={5} maxLength={500} showCount /></Form.Item>
      <Form.Item name="self_intro" label="个人简介" rules={[{ max: 2000, message: '不超过2000字' }]}><TextArea rows={8} maxLength={2000} showCount /></Form.Item>
      <Button type="primary" htmlType="submit" loading={loading}>保存</Button>
    </Form>
  );
}

function SkillsForm({ data, onSave, loading }: { data: any; onSave: (v: any) => void; loading: boolean }) {
  const [sections, setSections] = useState<any[]>([]);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingIdx, setEditingIdx] = useState<number | null>(null);
  const [title, setTitle] = useState('');
  const [itemsText, setItemsText] = useState('');

  useEffect(() => {
    // Load from either new format (skill_sections) or legacy formats
    const secs = data?.skill_sections || [];
    if (secs.length > 0) {
      setSections(secs);
    } else {
      // Build from legacy formats for migration
      const legacy: any[] = [];
      const catLabels: Record<string, string> = { hard_skills: '硬技能', soft_skills: '软技能', tool_skills: '工具平台' };
      for (const [key, label] of Object.entries(catLabels)) {
        const items = data?.[key] || [];
        if (items.length > 0) {
          legacy.push({ title: label, items: items.map((t: string) => ({ name: t, desc: '' })) });
        }
      }
      if (legacy.length > 0) setSections(legacy);
    }
  }, [data]);

  const itemsToText = (items: any[]) => items.map((i: any) => {
    const name = i.name || '';
    const desc = i.desc || '';
    return desc ? `${name}：${desc}` : name;
  }).join('\n');

  const textToItems = (text: string) => text.split('\n').filter(Boolean).map((line) => {
    const idx = line.indexOf('：');
    if (idx > 0) {
      return { name: line.slice(0, idx).trim(), desc: line.slice(idx + 1).trim() };
    }
    return { name: line.trim(), desc: '' };
  });

  const openAdd = () => {
    setEditingIdx(null);
    setTitle('');
    setItemsText('');
    setModalOpen(true);
  };

  const openEdit = (idx: number) => {
    setEditingIdx(idx);
    const sec = sections[idx];
    setTitle(sec.title || '');
    setItemsText(itemsToText(sec.items || []));
    setModalOpen(true);
  };

  const handleOk = () => {
    if (!title.trim()) { message.warning('请输入技能分类标题'); return; }
    const newSections = [...sections];
    const newSec = { title: title.trim(), items: textToItems(itemsText) };
    if (editingIdx !== null) {
      newSections[editingIdx] = newSec;
    } else {
      newSections.push(newSec);
    }
    setSections(newSections);
    setModalOpen(false);
    onSave({ skill_sections: newSections });
  };

  const handleDelete = (idx: number) => {
    Modal.confirm({
      title: '确认删除此技能分类？',
      onOk: () => {
        const newSections = sections.filter((_, i) => i !== idx);
        setSections(newSections);
        onSave({ skill_sections: newSections });
      },
    });
  };

  const handleMove = (from: number, to: number) => {
    const newSections = [...sections];
    const [moved] = newSections.splice(from, 1);
    newSections.splice(to, 0, moved);
    setSections(newSections);
    onSave({ skill_sections: newSections });
  };

  return (
    <div>
      <Button icon={<PlusOutlined />} onClick={openAdd} style={{ marginBottom: 12 }} type="dashed">
        添加技能分类
      </Button>
      {sections.length === 0 && <Tag>暂无数据</Tag>}
      {sections.map((sec, idx) => (
        <Card key={idx} size="small" style={{ marginBottom: 8 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div style={{ flex: 1 }}>
              <Tag color="blue">{sec.title || '未命名分类'}</Tag>
              <span style={{ marginLeft: 8, color: '#888', fontSize: 13 }}>{(sec.items || []).length} 项</span>
            </div>
            <Space>
              <Button size="small" onClick={() => openEdit(idx)}>编辑</Button>
              <Button size="small" danger onClick={() => handleDelete(idx)}>删除</Button>
              {idx > 0 && <Button size="small" onClick={() => handleMove(idx, idx - 1)}>↑</Button>}
              {idx < sections.length - 1 && <Button size="small" onClick={() => handleMove(idx, idx + 1)}>↓</Button>}
            </Space>
          </div>
        </Card>
      ))}
      <Modal
        title={editingIdx !== null ? '编辑技能分类' : '添加技能分类'}
        open={modalOpen}
        onOk={handleOk}
        onCancel={() => setModalOpen(false)}
        confirmLoading={loading}
      >
        <Form layout="vertical">
          <Form.Item label="分类标题" required>
            <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="如：产品能力、工具与平台" maxLength={100} />
          </Form.Item>
          <Form.Item label="技能条目（每行一个，格式：名称：描述）">
            <TextArea rows={8} value={itemsText} onChange={(e) => setItemsText(e.target.value)}
              placeholder={"需求分析：多角色需求访谈、用户痛点诊断、Kano模型\n产品设计：功能规划、信息架构、系统架构设计"}
              maxLength={5000} showCount />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}

// ============================================================
// Multi-record forms: education, work_experience, projects, faq
// ============================================================

interface FieldDef {
  name: string;
  label: string;
  type?: 'textarea' | 'dateRange' | 'select';
  rules?: any[];
  maxLength?: number;
  rows?: number;
  extra?: { extractFrom?: string; btnText?: string };
}

interface RecordFormProps {
  fields: FieldDef[];
  listKey: string;
  data: any;
  onSave: (v: any) => void;
  loading: boolean;
  selectOptions?: Record<string, { label: string; value: string }[]>;
}

function DateRangeInput({ value, onChange }: any) {
  const hasEnd = value?.[1] && dayjs(value[1]).isValid();
  const isOngoing = !hasEnd && !!value?.[0];
  const rangeVal = value?.[0] ? value : undefined;
  return (
    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
      <DatePicker.RangePicker
        picker="month"
        format="YYYY-MM"
        style={{ flex: 1 }}
        value={rangeVal}
        onChange={(dates) => { onChange?.(dates); }}
      />
      <Checkbox checked={isOngoing} onChange={(e) => {
        if (e.target.checked && rangeVal) {
          onChange?.([rangeVal[0], null]);
        }
      }}>至今</Checkbox>
    </div>
  );
}

function RecordListForm({ fields, listKey, data, onSave, loading, selectOptions }: RecordFormProps) {
  const [items, setItems] = useState<any[]>([]);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingIdx, setEditingIdx] = useState<number | null>(null);
  const [form] = Form.useForm();

  useEffect(() => {
    setItems(Array.isArray(data?.[listKey]) ? data[listKey] : []);
  }, [data, listKey]);

  // Find dateRange fields
  const dateRangeFields = fields.filter(f => f.type === 'dateRange');
  const otherFields = fields.filter(f => f.type !== 'dateRange');

  const openAdd = () => {
    setEditingIdx(null);
    form.resetFields();
    setModalOpen(true);
  };

  const openEdit = (idx: number) => {
    setEditingIdx(idx);
    const item = items[idx];
    const vals: any = {};
    for (const f of fields) {
      if (f.type === 'dateRange') {
        if (item[f.name] && item[f.name] !== '-') {
          const parts = item[f.name].split(' - ');
          if (parts.length >= 2 && parts[0]) {
            const start = dayjs(parts[0].replace(/\./g, '-') + '-01');
            const end = parts[1] === '至今' ? null : dayjs(parts[1].replace(/\./g, '-') + '-01');
            vals[f.name] = [start, end || null];
          }
        }
      } else {
        vals[f.name] = item[f.name];
      }
    }
    form.setFieldsValue(vals);
    setModalOpen(true);
  };

  const handleOk = () => {
    form.validateFields().then((vals) => {
      const newVals: any = {};
      for (const f of fields) {
        if (f.type === 'dateRange') {
          const range = vals[f.name];
          if (!range || !range[0]) {
            newVals[f.name] = '';
          } else {
            const start = dayjs(range[0]).format('YYYY.MM');
            const end = range[1] && dayjs(range[1]).isValid() ? dayjs(range[1]).format('YYYY.MM') : '至今';
            newVals[f.name] = `${start} - ${end}`;
          }
        } else {
          newVals[f.name] = vals[f.name];
        }
      }
      const newItems = [...items];
      if (editingIdx !== null) {
        newItems[editingIdx] = newVals;
      } else {
        newItems.push(newVals);
      }
      setItems(newItems);
      setModalOpen(false);
      onSave({ [listKey]: newItems });
    });
  };

  const handleDelete = (idx: number) => {
    Modal.confirm({
      title: '确认删除此项？',
      onOk: () => {
        const newItems = items.filter((_, i) => i !== idx);
        setItems(newItems);
        onSave({ [listKey]: newItems });
      },
    });
  };

  const handleExtract = (f: FieldDef) => {
    const desc = form.getFieldValue(f.extra?.extractFrom || '');
    if (!desc) { message.warning('请先填写项目描述'); return; }
    // Split by common delimiters and filter meaningful terms
    const words = desc.split(/[,，、\s\n；;。.()（）【】\[\]{}]+/).filter((w: string) => w.length >= 2);
    // Match: English terms, Chinese tech terms, versions, symbols
    const techTerms = [...new Set(words.filter((w: string) =>
      /[A-Za-z]/.test(w) ||                     // English letters (Python, Java, API)
      /^[A-Za-z0-9+#./]+$/.test(w) ||           // Version numbers, tech names
      /^(人工智能|机器学习|深度学习|数据分析|数据挖掘|自然语言处理|知识图谱|计算机视觉|推荐系统|搜索引擎|云计算|大数据|微服务|容器化|云原生|DevOps|敏捷开发|项目管理|需求分析|产品设计|用户研究|用户增长|数据驱动|AB测试|商业分析|市场调研|竞品分析|策略规划|团队管理|跨部门协作)$/.test(w)
    ))] as string[];
    form.setFieldsValue({ [f.name]: techTerms.join('\n') });
    message.success(`已从描述中提取 ${techTerms.length} 个关键词`);
  };

  return (
    <div>
      <Button icon={<PlusOutlined />} onClick={openAdd} style={{ marginBottom: 12 }} type="dashed">
        添加
      </Button>
      {items.length === 0 && <Tag>暂无数据</Tag>}
      {items.map((item, idx) => (
        <Card key={idx} size="small" style={{ marginBottom: 8 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div style={{ flex: 1 }}>
              {fields.map((f) => (
                <div key={f.name} style={{ marginBottom: 4 }}>
                  <Tag>{f.label}</Tag> {item[f.name] || '-'}
                </div>
              ))}
            </div>
            <Space>
              <Button size="small" onClick={() => openEdit(idx)}>编辑</Button>
              <Button size="small" danger onClick={() => handleDelete(idx)}>删除</Button>
            </Space>
          </div>
        </Card>
      ))}
      <Modal
        title={editingIdx !== null ? '编辑' : '添加'}
        open={modalOpen}
        onOk={handleOk}
        onCancel={() => setModalOpen(false)}
        confirmLoading={loading}
      >
        <Form form={form} layout="vertical">
          {dateRangeFields.map((f) => (
            <Form.Item key={f.name} name={f.name} label={f.label} rules={f.rules}>
              <DateRangeInput />
            </Form.Item>
          ))}
          {otherFields.map((f) => (
            <Form.Item key={f.name} name={f.name} label={f.label} rules={f.rules}>
              {f.type === 'select' ? (
                <Select options={selectOptions?.[f.name]} allowClear placeholder="请选择" />
              ) : f.type === 'textarea' ? (
                <TextArea rows={f.rows || 3} maxLength={f.maxLength} showCount={!!f.maxLength} />
              ) : (
                <Input maxLength={f.maxLength} />
              )}
            </Form.Item>
          ))}
          {otherFields.filter(f => f.extra).map(f => (
            <div key={`ext-${f.name}`} style={{ marginTop: -12, marginBottom: 16 }}>
              <Button size="small" type="dashed" icon={<ThunderboltOutlined />}
                onClick={() => handleExtract(f)}>
                {f.extra!.btnText || '自动提取'}
              </Button>
            </div>
          ))}
        </Form>
      </Modal>
    </div>
  );
}

// ============================================================
// Knowledge Page
// ============================================================

export default function KnowledgePage() {
  const [activeTab, setActiveTab] = useState('personal_info');
  const [formData, setFormData] = useState<any>({});
  const [workData, setWorkData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [rebuilding, setRebuilding] = useState(false);
  const [appendixInfo, setAppendixInfo] = useState<any>(null);
  const [records, setRecords] = useState<any[]>([]);
  const [expandedRecord, setExpandedRecord] = useState<number | null>(null);

  const loadData = useCallback(async (cat: string) => {
    setLoading(true);
    try {
      const res = await getKnowledgeStructured(cat);
      setFormData(res.data || {});
      // Also load work experience to populate company options for projects
      if (cat === 'projects') {
        const workRes = await getKnowledgeStructured('work_experience').catch(() => null);
        setWorkData(workRes?.data || null);
      } else {
        setWorkData(null);
      }
    } catch {
      setFormData({});
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (activeTab === 'appendix') {
      loadAppendix();
    } else {
      loadData(activeTab);
    }
  }, [activeTab, loadData]);

  const handleSave = async (data: any) => {
    setLoading(true);
    try {
      await saveKnowledgeStructured(activeTab, data);
      message.success('保存成功，向量库已更新');
      loadData(activeTab);
    } catch {
      message.error('保存失败');
    } finally {
      setLoading(false);
    }
  };

  const handleRebuild = async () => {
    setRebuilding(true);
    try {
      await rebuildVector();
      message.success('向量库重建完成');
    } catch { message.error('重建失败'); }
    finally { setRebuilding(false); }
  };

  const loadAppendix = async () => {
    const [info, rec] = await Promise.all([
      getAppendixInfo().catch(() => null),
      getAppendixRecords().catch(() => ({ records: [] })),
    ]);
    setAppendixInfo(info);
    setRecords(Array.isArray(rec) ? rec : (rec?.records || []));
  };

  const [uploadFiles, setUploadFiles] = useState<any[]>([]);

  const handleUploadFiles = async () => {
    if (uploadFiles.length === 0) { message.warning('请先选择文件'); return; }
    try {
      const formData = new FormData();
      uploadFiles.forEach((f) => formData.append('files', f.originFileObj || f));
      await api.post('/admin/appendix/upload', formData);
      message.success(`成功上传 ${uploadFiles.length} 个文件`);
      setUploadFiles([]);
      loadAppendix();
    } catch { message.error('上传失败'); }
  };

  const handleDeleteRecord = (id: number) => {
    Modal.confirm({
      title: '删除此记录？关联的向量数据也将清除。',
      onOk: async () => {
        await deleteAppendixRecord(id);
        message.success('已删除');
        loadAppendix();
      },
    });
  };

  const handleClearAll = () => {
    Modal.confirm({
      title: '清空所有附录知识库？此操作不可恢复。',
      onOk: async () => {
        await clearAppendix();
        message.success('已清空');
        loadAppendix();
      },
    });
  };

  const renderForm = () => {
    if (activeTab === 'personal_info') {
      return <PersonalInfoForm data={formData} onSave={handleSave} loading={loading} />;
    }
    if (activeTab === 'skills') {
      return <SkillsForm data={formData} onSave={handleSave} loading={loading} />;
    }
    if (activeTab === 'education') {
      return (
        <RecordListForm
          fields={[
            { name: 'school', label: '学校名称', rules: [{ required: true, message: '请输入学校名称' }, { max: 100, message: '不超过100字' }], maxLength: 100 },
            { name: 'degree', label: '学历专业', rules: [{ max: 100, message: '不超过100字' }], maxLength: 100 },
            { name: 'period', label: '就读时间', type: 'dateRange' },
            { name: 'major_courses', label: '主修课程', rules: [{ max: 500, message: '不超过500字' }], maxLength: 500 },
            { name: 'honors', label: '在校荣誉', type: 'textarea', rows: 4, rules: [{ max: 1000, message: '不超过1000字' }], maxLength: 1000 },
          ]}
          listKey="education_list"
          data={formData}
          onSave={handleSave}
          loading={loading}
        />
      );
    }
    if (activeTab === 'work_experience') {
      return (
        <RecordListForm
          fields={[
            { name: 'company', label: '公司名称', rules: [{ required: true, message: '请输入公司名称' }, { max: 100, message: '不超过100字' }], maxLength: 100 },
            { name: 'position', label: '职位', rules: [{ required: true, message: '请输入职位' }, { max: 100, message: '不超过100字' }], maxLength: 100 },
            { name: 'period', label: '工作时间', type: 'dateRange' },
            { name: 'description', label: '工作描述', type: 'textarea', rows: 8, rules: [{ max: 5000, message: '不超过5000字' }], maxLength: 5000 },
          ]}
          listKey="work_list"
          data={formData}
          onSave={handleSave}
          loading={loading}
        />
      );
    }
    if (activeTab === 'projects') {
      const workList: any[] = workData?.work_list || [];
      const companyNames = workList.map((w: any) => w.company).filter((c: string) => c);
      const companies = [...new Set(companyNames)] as string[];
      return (
        <RecordListForm
          fields={[
            { name: 'company', label: '所属公司', type: 'select' },
            { name: 'name', label: '项目名称', rules: [{ required: true, message: '请输入项目名称' }, { max: 200, message: '不超过200字' }], maxLength: 200 },
            { name: 'role', label: '角色', rules: [{ max: 100, message: '不超过100字' }], maxLength: 100 },
            { name: 'period', label: '项目时间', type: 'dateRange' },
            { name: 'tech_stack', label: '技能栈', type: 'textarea', rows: 2, rules: [{ max: 500, message: '不超过500字' }], maxLength: 500, extra: { extractFrom: 'description', btnText: '从项目描述提取关键词' } },
            { name: 'description', label: '项目描述', type: 'textarea', rows: 10, rules: [{ max: 5000, message: '不超过5000字' }], maxLength: 5000 },
          ]}
          selectOptions={{ company: companies.map((c: string) => ({ label: c, value: c })) }}
          listKey="project_list"
          data={formData}
          onSave={handleSave}
          loading={loading}
        />
      );
    }
    if (activeTab === 'faq') {
      return (
        <div>
          <div style={{ marginBottom: 8 }}>
            <Button icon={<DeleteOutlined />} onClick={async () => {
              try {
                await clearFaqAnswers();
                message.success('已清除所有回答，保留问题');
                loadData('faq');
              } catch { message.error('操作失败'); }
            }}>
              清除所有回答
            </Button>
          </div>
          <RecordListForm
            fields={[
              { name: 'question', label: '问题', type: 'textarea', rows: 4, rules: [{ required: true, message: '请输入问题' }, { max: 500, message: '不超过500字' }], maxLength: 500 },
              { name: 'answer', label: '回答', type: 'textarea', rows: 6, rules: [{ required: true, message: '请输入回答' }, { max: 2000, message: '不超过2000字' }], maxLength: 2000 },
            ]}
            listKey="faq_list"
            data={formData}
            onSave={handleSave}
            loading={loading}
          />
        </div>
      );
    }
    return null;
  };

  const appendixColumns = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    { title: '文件名', dataIndex: 'filename', ellipsis: true },
    {
      title: '文件明细', width: 100,
      render: (_: any, record: any) => (
        <Button type="link" size="small" icon={<EyeOutlined />}
          onClick={() => setExpandedRecord(expandedRecord === record.id ? null : record.id)}>
          {expandedRecord === record.id ? '收起' : '查看'}
        </Button>
      ),
    },
    {
      title: '操作', width: 80,
      render: (_: any, record: any) => (
        <Button type="link" danger size="small" icon={<DeleteOutlined />}
          onClick={() => handleDeleteRecord(record.id)} />
      ),
    },
  ];

  const tabItems = [
    { key: 'personal_info', label: '个人资料', children: renderForm() },
    { key: 'education', label: '教育经历', children: renderForm() },
    { key: 'work_experience', label: '工作经历', children: renderForm() },
    { key: 'projects', label: '项目经历', children: renderForm() },
    { key: 'skills', label: '技能标签', children: renderForm() },
    { key: 'faq', label: '高频问答', children: renderForm() },
    {
      key: 'appendix',
      label: '附录知识库',
      children: (
        <div>
          <Card size="small" style={{ marginBottom: 16 }}>
            <Space direction="vertical" style={{ width: '100%' }}>
              <Upload
                multiple
                accept=".md,.txt"
                fileList={uploadFiles}
                beforeUpload={(file) => { setUploadFiles(prev => [...prev, file]); return false; }}
                onRemove={(file) => { setUploadFiles(prev => prev.filter(f => f.uid !== file.uid)); }}
              >
                <Button icon={<UploadOutlined />}>选择 .md 文件</Button>
              </Upload>
              {uploadFiles.length > 0 && (
                <Button type="primary" onClick={handleUploadFiles} style={{ marginTop: 8 }}>
                  上传 {uploadFiles.length} 个文件
                </Button>
              )}
              {appendixInfo && (
                <div>
                  <Tag>文档片段总数: {appendixInfo.count || 0}（含主知识库）</Tag>
                </div>
              )}
            </Space>
          </Card>

          <Table
            dataSource={records}
            rowKey="id"
            size="small"
            pagination={{ pageSize: 10 }}
            columns={appendixColumns}
            expandable={{
              expandedRowKeys: expandedRecord ? [expandedRecord] : [],
              onExpand: (expanded: boolean, record: any) => setExpandedRecord(expanded ? record.id : null),
              expandedRowRender: (record: any) => {
                const files = record.files || record.file_names || [];
                return (
                  <div>
                    <Tag>上传时间: {record.time || record.created_at || '-'}</Tag>
                    <Tag>片段数: {record.chunk_count || 0}</Tag>
                    <div style={{ marginTop: 8 }}>
                      {files.length > 0 ? files.map((f: string, i: number) => (
                        <div key={i} style={{ padding: '2px 0' }}>📄 {f}</div>
                      )) : <Tag>无文件明细</Tag>}
                    </div>
                  </div>
                );
              },
            }}
          />
          {records.length > 0 && (
            <div style={{ marginTop: 12 }}>
              <Button danger icon={<ClearOutlined />} onClick={handleClearAll}>
                清空所有附录
              </Button>
            </div>
          )}
        </div>
      ),
    },
  ];

  return (
    <div>
      <div style={{ marginBottom: 12, textAlign: 'right' }}>
        <Button icon={<ReloadOutlined />} onClick={handleRebuild} loading={rebuilding}>
          重建向量库
        </Button>
      </div>
      <Tabs activeKey={activeTab} onChange={setActiveTab} items={tabItems} />
    </div>
  );
}
