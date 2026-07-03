import React from 'react';
import type { PortfolioConfig, KnowledgeData } from '../../../api/portfolio';
import { PortfolioViewer } from '../../../components/portfolio-preview/PortfolioViewer';

interface LivePreviewProps {
  config: PortfolioConfig;
  knowledge: KnowledgeData;
}

export const LivePreview: React.FC<LivePreviewProps> = ({ config, knowledge }) => {
  return (
    <div className="live-preview">
      <div className="preview-container">
        <PortfolioViewer config={config} knowledge={knowledge} />
      </div>
    </div>
  );
};