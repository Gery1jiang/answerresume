import React, { useState } from 'react';
import { exportPortfolioHTML } from '../../../api/portfolio';

interface ExportPanelProps {
  style: string;
}

export const ExportPanel: React.FC<ExportPanelProps> = ({ style }) => {
  const [loading, setLoading] = useState(false);

  const handleExport = async () => {
    setLoading(true);
    try {
      const html = await exportPortfolioHTML(style);
      const blob = new Blob([html], { type: 'text/html' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'portfolio.html';
      a.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Export failed:', error);
    } finally {
      setLoading(false);
    }
  };

  const handlePreview = async () => {
    setLoading(true);
    try {
      const html = await exportPortfolioHTML(style);
      const blob = new Blob([html], { type: 'text/html' });
      const url = URL.createObjectURL(blob);
      window.open(url, '_blank');
    } catch (error) {
      console.error('Preview failed:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="export-panel">
      <button className="export-btn" onClick={handleExport} disabled={loading}>
        {loading ? '导出中...' : '📥 导出 HTML'}
      </button>
      <button className="preview-btn" onClick={handlePreview} disabled={loading}>
        🔗 在新窗口预览
      </button>
    </div>
  );
};