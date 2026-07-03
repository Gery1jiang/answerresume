import { useState, useEffect } from 'react';
import { Card, Form, Input, Button, message, Radio } from 'antd';
import { SunOutlined, MoonOutlined, LaptopOutlined } from '@ant-design/icons';
import {
  getMyConfig, updateMyConfig, changePassword, getMyProfile, updateMyProfile,
} from '../../api/config';

export default function MyConfigPage() {
  const [pwdForm] = Form.useForm();
  const [profileForm] = Form.useForm();
  const [savingProfile, setSavingProfile] = useState(false);

  const [themeMode, setThemeMode] = useState<'system' | 'light' | 'dark'>(() => {
    return (localStorage.getItem('admin_theme_mode') as any) || 'system';
  });

  useEffect(() => {
    loadProfile();
  }, []);

  const loadProfile = async () => {
    try {
      const profile = await getMyProfile();
      profileForm.setFieldsValue({
        display_name: profile.display_name,
        email: profile.email,
      });
    } catch {}
  };

  const onThemeModeChange = (m: 'system' | 'light' | 'dark') => {
    setThemeMode(m);
    localStorage.setItem('admin_theme_mode', m);
    window.location.reload();
  };

  const changePwd = async (values: { old_password: string; new_password: string }) => {
    try {
      await changePassword(values.old_password, values.new_password);
      message.success('密码已修改');
      pwdForm.resetFields();
    } catch (e: any) {
      message.error(e.response?.data?.detail || '修改失败');
    }
  };

  const saveProfile = async (values: { display_name: string; email: string }) => {
    setSavingProfile(true);
    try {
      await updateMyProfile(values);
      localStorage.setItem('display_name', values.display_name);
      message.success('个人信息已更新');
    } catch (e: any) {
      message.error(e.response?.data?.detail || '保存失败');
    } finally {
      setSavingProfile(false);
    }
  };

  return (
    <div>
      <div style={{ fontSize: 18, fontWeight: 600, color: 'var(--admin-text)', marginBottom: 16 }}>个人设置</div>
      <Card title="主题设置" size="small" style={{ marginBottom: 16, maxWidth: 600 }}>
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontWeight: 600, color: 'var(--admin-text)', marginBottom: 4 }}>外观模式</div>
          <div style={{ fontSize: 13, color: 'var(--admin-text-muted)', marginBottom: 12 }}>选择管理后台的显示主题，可选择跟随系统自动切换</div>
          <Radio.Group
            value={themeMode}
            onChange={(e) => onThemeModeChange(e.target.value)}
            optionType="button"
            buttonStyle="solid"
            size="large"
          >
            <Radio.Button value="system"><LaptopOutlined /> 跟随系统</Radio.Button>
            <Radio.Button value="light"><SunOutlined /> 浅色</Radio.Button>
            <Radio.Button value="dark"><MoonOutlined /> 深色</Radio.Button>
          </Radio.Group>
        </div>
      </Card>
      <Card title="个人信息" size="small" style={{ marginBottom: 16, maxWidth: 600 }}>
        <Form form={profileForm} layout="vertical" onFinish={saveProfile}>
          <Form.Item name="display_name" label="显示名称" rules={[{ required: true, message: '请输入显示名称' }]}>
            <Input maxLength={50} />
          </Form.Item>
          <Form.Item name="email" label="邮箱" rules={[
            { required: true, message: '请输入邮箱' },
            { type: 'email', message: '请输入有效邮箱地址' },
          ]}>
            <Input maxLength={100} />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={savingProfile}>保存</Button>
        </Form>
      </Card>
      <Card title="修改密码" size="small" style={{ maxWidth: 400 }}>
        <Form form={pwdForm} layout="vertical" onFinish={changePwd}>
          <Form.Item name="old_password" label="旧密码" rules={[{ required: true }]}>
            <Input.Password />
          </Form.Item>
          <Form.Item name="new_password" label="新密码" rules={[{ required: true, min: 6 }]}>
            <Input.Password />
          </Form.Item>
          <Form.Item name="confirm_password" label="确认新密码" rules={[
            { required: true },
            ({ getFieldValue }) => ({
              validator(_, v) {
                if (!v || getFieldValue('new_password') === v) return Promise.resolve();
                return Promise.reject(new Error('两次密码不一致'));
              },
            }),
          ]}>
            <Input.Password />
          </Form.Item>
          <Button type="primary" htmlType="submit">确认修改</Button>
        </Form>
      </Card>
    </div>
  );
}
