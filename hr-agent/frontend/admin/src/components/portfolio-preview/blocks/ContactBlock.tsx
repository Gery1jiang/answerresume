import React from 'react';
import type { KnowledgeData, PortfolioConfig } from '../../../api/portfolio';

interface ContactBlockProps {
  knowledge: KnowledgeData;
  config: PortfolioConfig;
}

export const ContactBlock: React.FC<ContactBlockProps> = ({ knowledge, config }) => {
  const info = (knowledge.personal_info || {}) as Record<string, any>;
  const enabled = config.contact_enabled;
  
  const contacts = [];
  if (enabled.email && info.email) {
    contacts.push(<a key="email" href={`mailto:${info.email}`}>{info.email}</a>);
  }
  if (enabled.phone && info.phone) {
    contacts.push(<a key="phone" href={`tel:${info.phone}`}>{info.phone}</a>);
  }
  if (enabled.github && info.github) {
    contacts.push(<a key="github" href={info.github} target="_blank">GitHub</a>);
  }
  if (enabled.wechat && info.wechat) {
    contacts.push(<span key="wechat">{info.wechat}</span>);
  }

  return (
    <section className="portfolio-section contact">
      <div className="container">
        <h2>联系方式</h2>
        <div className="contact-list">{contacts}</div>
      </div>
    </section>
  );
};