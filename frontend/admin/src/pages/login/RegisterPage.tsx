import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Form, Input, Button, Card, message } from 'antd';
import { UserOutlined, MailOutlined, LockOutlined, RobotOutlined, SmileOutlined } from '@ant-design/icons';
import { register } from '../../api/auth';

export default function RegisterPage() {
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const onFinish = async (values: { username: string; display_name?: string; email: string; password: string }) => {
    setLoading(true);
    try {
      await register(values);
      message.success('注册成功！');
      navigate('/');
    } catch (e: any) {
      message.error(e.response?.data?.detail || '注册失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        height: '100vh',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        background: 'var(--admin-bg)',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          width: 600,
          height: 600,
          background: 'radial-gradient(circle, rgba(99,102,241,0.08) 0%, transparent 70%)',
          pointerEvents: 'none',
          borderRadius: '50%',
        }}
      />

      <div style={{ position: 'relative', zIndex: 1 }}>
        <Card
          style={{
            width: 420,
            background: 'var(--admin-bg-card)',
            border: '1px solid var(--admin-border)',
            boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
          }}
        >
          <div style={{ textAlign: 'center', marginBottom: 24 }}>
            <RobotOutlined style={{ fontSize: 48, color: 'var(--admin-accent)' }} />
            <h2 style={{ marginTop: 12, color: 'var(--admin-text)' }}>注册 AS Agent</h2>
          </div>
          <Form onFinish={onFinish} size="large" layout="vertical">
            <Form.Item
              name="username"
              label="登录ID"
              rules={[
                { required: true, message: '请输入登录ID' },
                { min: 2, max: 50, message: '2-50个字符' },
                { pattern: /^[a-zA-Z0-9_]+$/, message: '只能包含字母、数字和下划线' },
              ]}
            >
              <Input prefix={<UserOutlined />} placeholder="登录ID（字母数字）" maxLength={50} />
            </Form.Item>
            <Form.Item
              name="display_name"
              label="显示名称"
            >
              <Input prefix={<SmileOutlined />} placeholder="显示名称（可选，默认同登录ID）" maxLength={50} />
            </Form.Item>
            <Form.Item
              name="email"
              label="邮箱"
              rules={[
                { required: true, message: '请输入邮箱' },
                { type: 'email', message: '请输入有效的邮箱地址' },
              ]}
            >
              <Input prefix={<MailOutlined />} placeholder="邮箱" />
            </Form.Item>
            <Form.Item
              name="password"
              label="密码"
              rules={[
                { required: true, message: '请输入密码' },
                { min: 6, message: '密码至少6位' },
              ]}
            >
              <Input.Password prefix={<LockOutlined />} placeholder="密码" />
            </Form.Item>
            <Form.Item>
              <Button type="primary" htmlType="submit" loading={loading} block>
                注册
              </Button>
            </Form.Item>
            <div style={{ textAlign: 'center' }}>
              <span style={{ color: 'var(--admin-text-muted)' }}>已有账号？</span>
              <Link to="/login">去登录</Link>
            </div>
          </Form>
        </Card>
      </div>
    </div>
  );
}
