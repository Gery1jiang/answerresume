import { useState, useEffect, Fragment } from 'react';
import { Table, Button, Modal, Form, Input, Select, Switch, Tag, message, Space, Popconfirm } from 'antd';
import { PlusOutlined, ReloadOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import api from '../../api';

interface User {
  id: string;
  username: string;
  email: string;
  role: string;
  is_active: boolean;
  created_at: string | null;
}

export default function UserManagePage() {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [createForm] = Form.useForm();
  const [editForm] = Form.useForm();

  const fetchUsers = async () => {
    setLoading(true);
    try {
      const res = await api.get<{ users: User[]; total: number }>('/api/auth/users');
      setUsers(res.data.users);
    } catch { message.error('加载用户列表失败'); }
    finally { setLoading(false); }
  };

  useEffect(() => { fetchUsers(); }, []);

  const handleCreate = async () => {
    try {
      const values = await createForm.validateFields();
      await api.post('/api/auth/users', values);
      message.success('用户创建成功');
      setCreateOpen(false);
      createForm.resetFields();
      fetchUsers();
    } catch (err: any) {
      if (err.message) message.error(err.message);
    }
  };

  const handleEdit = async () => {
    if (!editingUser) return;
    try {
      const values = await editForm.validateFields();
      await api.put(`/api/auth/users/${editingUser.id}`, values);
      message.success('用户更新成功');
      setEditOpen(false);
      setEditingUser(null);
      fetchUsers();
    } catch (err: any) {
      if (err.message) message.error(err.message);
    }
  };

  const handleDelete = async (user: User) => {
    try {
      await api.delete(`/api/auth/users/${user.id}`);
      message.success('用户已删除');
      fetchUsers();
    } catch { message.error('删除失败'); }
  };

  const handleToggleActive = async (user: User) => {
    try {
      await api.put(`/api/auth/users/${user.id}`, { is_active: !user.is_active });
      message.success(user.is_active ? '已禁用' : '已启用');
      fetchUsers();
    } catch { message.error('操作失败'); }
  };

  const openEdit = (user: User) => {
    setEditingUser(user);
    editForm.setFieldsValue({ role: user.role, is_active: user.is_active });
    setEditOpen(true);
  };

  const columns = [
    {
      title: '用户名',
      dataIndex: 'username',
      key: 'username',
    },
    {
      title: '邮箱',
      dataIndex: 'email',
      key: 'email',
    },
    {
      title: '角色',
      dataIndex: 'role',
      key: 'role',
      render: (role: string) => (
        <Tag color={role === 'super_admin' ? 'gold' : 'blue'}>
          {role === 'super_admin' ? '超级管理员' : '普通用户'}
        </Tag>
      ),
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      render: (_: boolean, record: User) => (
        <Switch checked={record.is_active} onChange={() => handleToggleActive(record)}
          checkedChildren="启用" unCheckedChildren="禁用" />
      ),
    },
    {
      title: '注册时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (t: string | null) => t ? new Date(t).toLocaleString('zh-CN') : '-',
    },
    {
      title: '操作',
      key: 'action',
      render: (_: unknown, record: User) => (
        <Space>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => openEdit(record)}>编辑</Button>
          <Popconfirm title="确定删除该用户？" onConfirm={() => handleDelete(record)} okText="删除" cancelText="取消">
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <Fragment>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h2 style={{ margin: 0 }}>用户管理</h2>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={fetchUsers} loading={loading}>刷新</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>新建用户</Button>
        </Space>
      </div>
      <Table dataSource={users} columns={columns} rowKey="id" loading={loading}
        pagination={{ pageSize: 20 }} />

      {/* Create Modal */}
      <Modal title="新建用户" open={createOpen} onOk={handleCreate} onCancel={() => { setCreateOpen(false); createForm.resetFields(); }}
        okText="创建" cancelText="取消">
        <Form form={createForm} layout="vertical">
          <Form.Item name="username" label="用户名" rules={[{ required: true, message: '请输入用户名' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="email" label="邮箱" rules={[{ required: true, type: 'email', message: '请输入有效邮箱' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="password" label="密码" rules={[{ required: true, min: 6, message: '密码至少6位' }]}>
            <Input.Password />
          </Form.Item>
          <Form.Item name="role" label="角色" initialValue="user">
            <Select options={[
              { label: '普通用户', value: 'user' },
              { label: '超级管理员', value: 'super_admin' },
            ]} />
          </Form.Item>
        </Form>
      </Modal>

      {/* Edit Modal */}
      <Modal title="编辑用户" open={editOpen} onOk={handleEdit} onCancel={() => { setEditOpen(false); setEditingUser(null); }}
        okText="保存" cancelText="取消">
        <Form form={editForm} layout="vertical">
          <Form.Item name="role" label="角色">
            <Select options={[
              { label: '普通用户', value: 'user' },
              { label: '超级管理员', value: 'super_admin' },
            ]} />
          </Form.Item>
          <Form.Item name="is_active" label="状态" valuePropName="checked">
            <Switch checkedChildren="启用" unCheckedChildren="禁用" />
          </Form.Item>
        </Form>
      </Modal>
    </Fragment>
  );
}
