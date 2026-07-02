import React from 'react';
import type { KnowledgeData } from '../../../api/portfolio';

interface HeroBlockProps {
  knowledge: KnowledgeData;
}

export const HeroBlock: React.FC<HeroBlockProps> = ({ knowledge }) => {
  const info = (knowledge.personal_info || {}) as Record<string, any>;
  return (
    <section className="portfolio-section hero">
      <div className="hero-content">
        <h1>{info.name || '姓名'}</h1>
        <p className="title">{info.target_position || '求职意向'}</p>
        <p className="intro">{info.self_intro || ''}</p>
        <div className="tags">
          {info.job_tags?.map((tag: string, i: number) => (
            <span key={i} className="tag">{tag}</span>
          ))}
        </div>
      </div>
    </section>
  );
};