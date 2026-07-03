import { useState, useEffect } from 'react';
import { Card, Table, Statistic, Row, Col, Segmented, Spin } from 'antd';
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ComposedChart,
} from 'recharts';
import {
  fetchAllUsage, fetchAllDailyUsage,
  type AllUsageResponse, type DailyUsageItem,
} from '../../api/usage';

export default function UsagePage() {
  const [period, setPeriod] = useState<string>('all');
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<AllUsageResponse | null>(null);
  const [daily, setDaily] = useState<DailyUsageItem[]>([]);

  useEffect(() => {
    loadData();
  }, [period]);

  const loadData = async () => {
    setLoading(true);
    try {
      const [usageData, dailyData] = await Promise.all([
        fetchAllUsage(period),
        fetchAllDailyUsage(30),
      ]);
      setData(usageData);
      setDaily(dailyData);
    } catch (e) {
      console.error('Failed to load usage data', e);
    } finally {
      setLoading(false);
    }
  };

  const userColumns = [
    { title: '用户名', dataIndex: 'username', key: 'username', render: (v: string) => v || '-' },
    { title: 'Token 输入', dataIndex: 'total_input_tokens', key: 'input_tokens', render: (v: number) => v.toLocaleString() },
    { title: 'Token 输出', dataIndex: 'total_output_tokens', key: 'output_tokens', render: (v: number) => v.toLocaleString() },
    { title: 'Token 合计', dataIndex: 'total_tokens', key: 'total_tokens', render: (v: number) => v.toLocaleString() },
    { title: 'API 调用次数', dataIndex: 'total_api_calls', key: 'api_calls', render: (v: number) => v.toLocaleString() },
  ];

  return (
    <div style={{ padding: 24 }}>
      <Card>
        <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h2 style={{ margin: 0 }}>用量总览</h2>
          <Segmented
            value={period}
            onChange={(v) => setPeriod(v as string)}
            options={[
              { label: '今天', value: 'today' },
              { label: '近7天', value: '7d' },
              { label: '近30天', value: '30d' },
              { label: '全部', value: 'all' },
            ]}
          />
        </div>

        <Spin spinning={loading}>
          {data && (
            <>
              <Row gutter={16} style={{ marginBottom: 24 }}>
                <Col span={6}>
                  <Card><Statistic title="总 Token 消耗" value={data.summary.total_tokens} suffix="tokens" /></Card>
                </Col>
                <Col span={6}>
                  <Card><Statistic title="输入 Token" value={data.summary.total_input_tokens} suffix="tokens" /></Card>
                </Col>
                <Col span={6}>
                  <Card><Statistic title="输出 Token" value={data.summary.total_output_tokens} suffix="tokens" /></Card>
                </Col>
                <Col span={6}>
                  <Card><Statistic title="搜索 API 调用" value={data.summary.total_search_calls} /></Card>
                </Col>
              </Row>

              {daily.length > 0 && (
                <div style={{ marginBottom: 24 }}>
                  <h3>每日趋势（近30天）</h3>
                  <ResponsiveContainer width="100%" height={320}>
                    <ComposedChart data={daily}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="date" fontSize={12} />
                      <YAxis yAxisId="left" />
                      <YAxis yAxisId="right" orientation="right" />
                      <Tooltip />
                      <Legend />
                      <Bar yAxisId="left" dataKey="input_tokens" fill="#1890ff" name="输入 Token" barSize={20} />
                      <Bar yAxisId="left" dataKey="output_tokens" fill="#52c41a" name="输出 Token" barSize={20} />
                      <Line yAxisId="right" type="monotone" dataKey="search_calls" stroke="#faad14" name="搜索调用" strokeWidth={2} />
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
              )}

              <h3>各用户用量</h3>
              <Table
                dataSource={data.users}
                columns={userColumns}
                rowKey="user_id"
                pagination={false}
                style={{ marginBottom: 24 }}
              />
            </>
          )}
        </Spin>
      </Card>
    </div>
  );
}
