import React from 'react';
import type { KnowledgeData } from '../../../api/portfolio';

interface AboutBlockProps {
  knowledge: KnowledgeData;
}

export const AboutBlock: React.FC<AboutBlockProps> = ({ knowledge }) => {
  const info = (knowledge.personal_info || {}) as Record<string, any>;
  return (
    <section className="portfolio-section about">
      <div className="container">
        <h2>关于我</h2>
        <p>{info.self_intro || '暂无简介'}</p>
      </div>
    </section>
  );
};