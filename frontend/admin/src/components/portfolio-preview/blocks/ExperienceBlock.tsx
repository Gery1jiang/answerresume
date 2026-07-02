import React from 'react';
import type { KnowledgeData } from '../../../api/portfolio';

interface ExperienceBlockProps {
  knowledge: KnowledgeData;
}

export const ExperienceBlock: React.FC<ExperienceBlockProps> = ({ knowledge }) => {
  const experiences = (knowledge.work_experience?.work_list || []) as any[];
  return (
    <section className="portfolio-section experience">
      <div className="container">
        <h2>工作经历</h2>
        <div className="timeline">
          {experiences.map((exp, i) => (
            <div key={i} className="timeline-item">
              <div className="timeline-date">{exp.period}</div>
              <div className="timeline-content">
                <h3>{exp.company}</h3>
                <p className="position">{exp.position}</p>
                <p className="description">{exp.description}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};