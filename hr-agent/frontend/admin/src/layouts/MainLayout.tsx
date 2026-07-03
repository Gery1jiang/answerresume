import { useState } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { Layout, Menu, Dropdown, Avatar, Space } from 'antd';
import {
  RobotOutlined,
  FileTextOutlined,
  BookOutlined,
  RadarChartOutlined,
  BarChartOutlined,
  SettingOutlined,
  HomeOutlined,
  LogoutOutlined,
  ScheduleOutlined,
  TeamOutlined,
  UserOutlined,
  LaptopOutlined,
  LockOutlined,
} from '@ant-design/icons';
import { clearToken, getStoredRole } from '../api';

const { Sider, Content } = Layout;

const userMenuItems = [
  { key: '/agent', icon: <RobotOutlined />, label: 'Agent' },
  { key: '/resume', icon: <FileTextOutlined />, label: '简历' },
  { key: '/portfolio', icon: <HomeOutlined />, label: '个人主页' },
  { key: '/jobs', icon: <RadarChartOutlined />, label: '岗位雷达' },
  { key: '/interview-guide', icon: <ScheduleOutlined />, label: '面试宝典' },
  { key: '/knowledge', icon: <BookOutlined />, label: '知识库' },
  { key: '/statistics', icon: <BarChartOutlined />, label: '数据统计' },
  { type: 'divider' as const },
  { key: '/my-config', icon: <UserOutlined />, label: '个人配置' },
  { key: '/access-settings', icon: <LockOutlined />, label: '访问设置' },
];

const adminMenuItems = [
  { key: '/admin/users', icon: <TeamOutlined />, label: '用户管理' },
  { key: '/admin/usage', icon: <BarChartOutlined />, label: '用量总览' },
  { key: '/config/service', icon: <SettingOutlined />, label: '管理端配置' },
  { key: '/config/visitor', icon: <LaptopOutlined />, label: '访客端配置' },
  { key: '/config/prompt', icon: <BookOutlined />, label: '提示词管理' },
  { type: 'divider' as const },
  { key: '/my-config', icon: <UserOutlined />, label: '个人设置' },
];

export default function MainLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const role = getStoredRole();

  const displayName = localStorage.getItem('display_name') || localStorage.getItem('username') || '用户';
  const username = localStorage.getItem('username') || '';

  const menuItems = role === 'super_admin' ? adminMenuItems : userMenuItems;

  const handleLogout = () => {
    clearToken();
    localStorage.removeItem('user_role');
    localStorage.removeItem('user_id');
    localStorage.removeItem('username');
    localStorage.removeItem('display_name');
    navigate('/login');
  };

  const userDropdownItems = [
    {
      key: 'profile',
      icon: <UserOutlined />,
      label: '个人配置',
      onClick: () => navigate('/my-config'),
    },
    { type: 'divider' as const },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: '退出登录',
      onClick: handleLogout,
      danger: true,
    },
  ];

  return (
    <Layout style={{ height: '100vh', overflow: 'hidden' }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        style={{
          background: 'var(--admin-sidebar-bg)',
          borderRight: '1px solid var(--admin-border)',
          transition: 'background 0.35s ease, border-color 0.3s ease',
        }}
      >
        <div style={{
          height: 56,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 8,
          borderBottom: '1px solid var(--admin-border)',
          padding: '0 16px',
          transition: 'border-color 0.3s ease',
        }}>
          <RobotOutlined style={{ fontSize: 22, color: 'var(--admin-accent)' }} />
          {!collapsed && <span style={{ fontWeight: 600, color: 'var(--admin-text)' }}>AS Agent</span>}
        </div>
        <Menu
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
          style={{ borderInlineEnd: 'none' }}
        />
      </Sider>
      <Layout style={{ overflow: 'hidden' }}>
        <Content style={{
          padding: '16px 24px',
          background: 'transparent',
          overflow: 'auto',
        }}>
          <div style={{
            display: 'flex',
            justifyContent: 'flex-end',
            marginBottom: 8,
            alignItems: 'center',
          }}>
            <Dropdown menu={{ items: userDropdownItems }} trigger={['hover']}>
              <Space style={{ cursor: 'pointer', color: 'var(--admin-text)', padding: '4px 8px', borderRadius: 6, transition: 'background 0.2s' }}
                onMouseEnter={e => (e.currentTarget.style.background = 'var(--admin-hover-bg)')}
                onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
              >
                <Avatar size={28} style={{ backgroundColor: 'var(--admin-accent)', verticalAlign: 'middle' }}>
                  {displayName.charAt(0).toUpperCase()}
                </Avatar>
                <span style={{ fontSize: 14, lineHeight: '28px' }}>{displayName}</span>
              </Space>
            </Dropdown>
          </div>
          <div className="page-enter">
            <Outlet />
          </div>
        </Content>
      </Layout>
    </Layout>
  );
}
