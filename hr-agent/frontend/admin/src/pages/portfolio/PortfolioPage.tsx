import React, { useState, useEffect, useMemo } from 'react';
import { Switch, Button, message, Tooltip } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import type { PortfolioConfig, KnowledgeData, StyleOption } from '../../api/portfolio';
import { 
  getPortfolioConfig, 
  savePortfolioConfig,
  getPortfolioPreview,
  getStyles,
  getPortfolioShowStatus,
  togglePortfolioShow,
  rebuildPortfolio,
  getPortfolioBuildStatus,
} from '../../api/portfolio';
import { StyleSelector } from './components/StyleSelector';
import { BlockEditor } from './components/BlockEditor';
import { LivePreview } from './components/LivePreview';
import { ExportPanel } from './components/ExportPanel';

const THEME_BLOCKS: Record<string, { id: string; name: string }[]> = {
  editorial: [
    { id: 'hero', name: '首页封面' },
    { id: 'about', name: '关于我' },
    { id: 'work', name: '精选项目' },
    { id: 'experience', name: '工作经历' },
    { id: 'contact', name: '联系方式' },
  ],
  developer: [
    { id: 'hero', name: '首页封面' },
    { id: 'projects', name: '项目展示' },
    { id: 'experience', name: '工作经历' },
    { id: 'stack', name: '技术栈' },
    { id: 'contact', name: '关于我' },
  ],
  creative: [
    { id: 'hero', name: '首页封面' },
    { id: 'work', name: '精选作品' },
    { id: 'experience', name: '工作经历' },
    { id: 'about', name: '关于我' },
    { id: 'contact', name: '联系方式' },
  ],
  personal: [
    { id: 'hero', name: '首页封面' },
    { id: 'about', name: '关于我' },
    { id: 'work', name: '精选项目' },
    { id: 'experience', name: '工作/教育经历' },
    { id: 'contact', name: '联系方式' },
  ],
};

export const PortfolioPage: React.FC = () => {
  const [config, setConfig] = useState<PortfolioConfig | null>(null);
  const [knowledge, setKnowledge] = useState<KnowledgeData | null>(null);
  const [styles, setStyles] = useState<StyleOption[]>([]);
  const [portfolioShow, setPortfolioShow] = useState(false);
  const [loading, setLoading] = useState(true);
  const [rebuildLoading, setRebuildLoading] = useState(false);
  const [buildStatus, setBuildStatus] = useState<{ built: boolean; built_at: string | null }>({ built: false, built_at: null });

  const fetchData = async () => {
    setLoading(true);
    try {
      const [configData, previewData, stylesData, statusData, buildStatusData] = await Promise.all([
        getPortfolioConfig(),
        getPortfolioPreview(),
        getStyles(),
        getPortfolioShowStatus(),
        getPortfolioBuildStatus(),
      ]);
      setConfig(configData);
      setKnowledge(previewData.knowledge);
      setStyles(stylesData.styles);
      setPortfolioShow(statusData.portfolio_show);
      setBuildStatus(buildStatusData);
    } catch (error) {
      console.error('Failed to fetch data:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleTogglePortfolioShow = async () => {
    const result = await togglePortfolioShow();
    setPortfolioShow(result.portfolio_show);
  };

  const handleStyleChange = async (style: string) => {
    if (!config) return;
    const updated = await savePortfolioConfig({ ...config, style });
    setConfig(updated);
  };

  const handleReorderBlocks = async (fromIndex: number, toIndex: number) => {
    if (!config) return;
    const newOrder = [...config.blocks_order];
    const [removed] = newOrder.splice(fromIndex, 1);
    newOrder.splice(toIndex, 0, removed);
    const updated = await savePortfolioConfig({ ...config, blocks_order: newOrder });
    setConfig(updated);
  };

  const handleToggleBlock = async (blockId: string) => {
    if (!config) return;
    const newHidden = config.blocks_hidden.includes(blockId)
      ? config.blocks_hidden.filter(id => id !== blockId)
      : [...config.blocks_hidden, blockId];
    const updated = await savePortfolioConfig({ ...config, blocks_hidden: newHidden });
    setConfig(updated);
  };

  const handleRebuild = async () => {
    setRebuildLoading(true);
    try {
      const result = await rebuildPortfolio();
      message.success(`重构完成！共处理 ${result.items} 个经历/项目`);
      await fetchData();
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '重构失败');
    } finally {
      setRebuildLoading(false);
    }
  };

  const blocks = useMemo(() => {
    if (!config) return [];
    const themeBlocks = THEME_BLOCKS[config.style] || [];
    return themeBlocks.map(block => ({
      ...block,
      visible: !config.blocks_hidden.includes(block.id),
    }));
  }, [config]);

  if (loading || !config || !knowledge) {
    return <div className="loading">加载中...</div>;
  }

  const buildTime = buildStatus.built_at
    ? new Date(buildStatus.built_at).toLocaleString('zh-CN')
    : '尚未构建';

  return (
    <div className="portfolio-page">
        <div className="page-header">
          <h1>个人主页配置</h1>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
            <Tooltip title="从知识库读取内容，重新构建个人主页（含 LLM 浓缩处理）">
              <Button
                icon={<ReloadOutlined spin={rebuildLoading} />}
                loading={rebuildLoading}
                onClick={handleRebuild}
              >
                重构个人主页
              </Button>
            </Tooltip>
            <span style={{ fontSize: 12, color: 'var(--admin-text-secondary)' }}>
              上次构建：{buildTime}
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--admin-text-secondary)', fontSize: 13 }}>
              <Switch checked={portfolioShow} onChange={handleTogglePortfolioShow} />
              访客端显示
            </span>
            <ExportPanel style={config.style} />
          </div>
        </div>
        <div className="page-content">
          <div className="sidebar">
            <StyleSelector styles={styles} selected={config.style} onChange={handleStyleChange} />
            <BlockEditor 
              blocks={blocks} 
              onReorder={handleReorderBlocks} 
              onToggleVisibility={handleToggleBlock} 
            />
          </div>
        <div className="main-content">
          <LivePreview config={config} knowledge={knowledge} />
        </div>
      </div>
    </div>
  );
};
