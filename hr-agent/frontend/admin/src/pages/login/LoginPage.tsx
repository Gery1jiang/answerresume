import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Form, Input, Button, Card, message } from 'antd';
import { UserOutlined, LockOutlined, RobotOutlined } from '@ant-design/icons';
import { login } from '../../api/auth';

export default function LoginPage() {
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const onFinish = async (values: { username: string; password: string }) => {
    setLoading(true);
    try {
      await login(values);
      message.success('登录成功！');
      navigate('/');
    } catch (e: any) {
      message.error(e.response?.data?.detail || '登录失败');
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
      {/* Ambient Background Effect */}
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
          animation: 'fadeIn 2s ease-out'
        }} 
      />
      
      <div style={{ position: 'relative', zIndex: 1 }}>
        <Card 
          className="backdrop-blur" 
          style={{ 
            width: 400, 
            background: 'var(--admin-bg-card)', 
            border: '1px solid var(--admin-border)',
            boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
            backdropFilter: 'blur(12px)',
            transition: 'all 0.3s ease'
          }}
        >
          <div style={{ textAlign: 'center', marginBottom: 24 }}>
            <RobotOutlined style={{ fontSize: 48, color: 'var(--admin-accent)' }} />
            <h2 style={{ marginTop: 12, color: 'var(--admin-text)' }}>AS Agent 管理后台</h2>
          </div>
          <Form onFinish={onFinish} size="large">
            <Form.Item name="username" rules={[{ required: true, message: '请输入用户名' }, { max: 50, message: '用户名不超过50字' }]}>
              <Input prefix={<UserOutlined />} placeholder="用户名/邮箱" maxLength={50} />
            </Form.Item>
            <Form.Item name="password" rules={[{ required: true, message: '请输入密码' }, { min: 6, message: '密码至少6位' }]}>
              <Input.Password prefix={<LockOutlined />} placeholder="密码" maxLength={50} />
            </Form.Item>
            <Form.Item>
              <Button 
                type="primary" 
                htmlType="submit" 
                loading={loading} 
                block
                style={{
                  background: 'var(--admin-accent)',
                  borderColor: 'var(--admin-accent)',
                  transition: 'all 0.3s ease'
                }}
              >
                登录
              </Button>
            </Form.Item>
          </Form>
          <div style={{ textAlign: 'center', marginTop: 8 }}>
            <span style={{ color: 'var(--admin-text-muted)' }}>没有账号？</span>
            <Link to="/register">去注册</Link>
          </div>
        </Card>
      </div>
    </div>
  );
}
