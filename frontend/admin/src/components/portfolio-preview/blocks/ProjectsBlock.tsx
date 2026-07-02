import React from 'react';
import type { KnowledgeData } from '../../../api/portfolio';

interface ProjectsBlockProps {
  knowledge: KnowledgeData;
}

export const ProjectsBlock: React.FC<ProjectsBlockProps> = ({ knowledge }) => {
  const projects = (knowledge.projects?.project_list || []) as any[];
  return (
    <section className="portfolio-section projects">
      <div className="container">
        <h2>项目经历</h2>
        <div className="projects-grid">
          {projects.map((project, i) => (
            <div key={i} className="project-card">
              <h3>{project.name}</h3>
              <p className="role">角色: {project.role}</p>
              <p className="tech">技术栈: {project.tech_stack}</p>
              <p className="description">{project.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};