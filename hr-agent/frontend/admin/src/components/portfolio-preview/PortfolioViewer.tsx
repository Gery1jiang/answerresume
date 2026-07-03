import React from 'react';
import type { PortfolioConfig, KnowledgeData } from '../../api/portfolio';
import { EditorialTheme } from './themes/EditorialTheme';
import { DeveloperTheme } from './themes/DeveloperTheme';
import { CreativeTheme } from './themes/CreativeTheme';
import { PersonalBrandTheme } from './themes/PersonalBrandTheme';

interface PortfolioViewerProps {
  config: PortfolioConfig;
  knowledge: KnowledgeData;
}

const THEMES: Record<string, React.FC<any>> = {
  editorial: EditorialTheme,
  developer: DeveloperTheme,
  creative: CreativeTheme,
  personal: PersonalBrandTheme,
};

export const PortfolioViewer: React.FC<PortfolioViewerProps> = ({ config, knowledge }) => {
  const currentTheme = config.style || 'editorial';
  const ThemeComponent = THEMES[currentTheme];

  return (
    <div className="portfolio-viewer-content">
      {ThemeComponent && <ThemeComponent knowledge={knowledge} config={config} />}
    </div>
  );
};
