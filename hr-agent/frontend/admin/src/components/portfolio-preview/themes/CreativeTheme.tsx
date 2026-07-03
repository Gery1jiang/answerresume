import React from 'react';
import type { KnowledgeData, PortfolioConfig } from '../../../api/portfolio';
import { useScrollNavigation } from '../hooks/useScrollNavigation';

interface CreativeThemeProps {
  knowledge: KnowledgeData;
  config: PortfolioConfig;
}

const SECTIONS = [
  { id: 'hero', label: 'Home' },
  { id: 'work', label: 'Work' },
  { id: 'experience', label: 'Experience' },
  { id: 'about', label: 'About' },
  { id: 'contact', label: 'Contact' },
];

export const CreativeTheme: React.FC<CreativeThemeProps> = ({ knowledge }) => {
  const info = (knowledge.personal_info || {}) as Record<string, any>;
  const work = (knowledge.work_experience?.work_list || []) as any[];
  const projects = (knowledge.projects?.project_list || []) as any[];
  const skillSections = knowledge.skills?.skill_sections || [];
  const skills: Record<string, string[]> = skillSections.length > 0
    ? Object.fromEntries(skillSections.map(s => [
        s.title,
        s.items.map(item => item.desc ? `${item.name}：${item.desc}` : item.name)
      ]))
    : (knowledge.skills?.skill_groups || {}) as Record<string, string[]>;
  const educations = (knowledge.education?.education_list || []) as any[];
  const { currentSection, registerSection, goToSection } = useScrollNavigation(SECTIONS.length);

  return (
    <div className="creative-theme">
      <style>{`
        .creative-theme {
          font-family: 'DM Sans', sans-serif;
          background-color: #0F0F0F;
          color: #FFFFFF;
          height: 100%;
          display: flex;
          flex-direction: column;
        }
        .creative-nav {
          flex-shrink: 0;
          display: flex;
          justify-content: flex-end;
          gap: 28px;
          padding: 32px 40px;
          font-family: 'DM Mono', monospace;
          font-size: 12px;
          background: #0F0F0F;
          color: #FFF;
        }
        .creative-sections {
          flex: 1;
          overflow-y: auto;
          scroll-behavior: smooth;
          scrollbar-width: none;
          -ms-overflow-style: none;
        }
        .creative-sections::-webkit-scrollbar {
          display: none;
        }
        .creative-sections .section {
          min-height: 100%;
          display: flex;
          align-items: center;
          justify-content: center;
        }
        .creative-sections .section-light {
          background: #F2F2F0;
          color: #0F0F0F;
        }
        .creative-sections .section-dark {
          background: #0F0F0F;
          color: #FFF;
        }
        .creative-sections .section-inner {
          max-width: 1100px;
          width: 100%;
          padding: 80px 40px;
        }
        .creative-nav .nav-btn {
          background: none; border: none; color: #888;
          cursor: pointer; font-family: inherit; font-size: inherit;
          padding: 0; transition: color 0.2s;
        }
        .creative-nav .nav-btn:hover,
        .creative-nav .nav-btn.active { color: #FFF; }
        .creative-section-label {
          font-family: 'DM Mono', monospace;
          font-size: 12px; color: #666; margin-bottom: 40px;
        }

        /* Hero - dark section */
        .cr-hero-wrap {
          width: 100%; height: 100vh;
          display: flex; flex-direction: column;
          justify-content: center; padding: 40px;
        }
        .cr-hero-name {
          font-size: 100px; font-weight: 300;
          letter-spacing: -0.03em; margin-bottom: 16px;
        }
        .cr-hero-role { font-size: 20px; font-weight: 300; color: #999; margin-bottom: 64px; }
        .cr-hero-teaser {
          display: grid; grid-template-columns: 1fr 1fr; gap: 16px;
        }
        .cr-hero-teaser-item {
          height: 280px; background: #1A1A1A; position: relative; overflow: hidden;
        }
        .cr-hero-teaser-item:hover .cr-teaser-overlay { opacity: 1; }
        .cr-teaser-overlay {
          position: absolute; inset: 0;
          background: rgba(0,0,0,0.8);
          display: flex; flex-direction: column; justify-content: flex-end;
          padding: 24px; opacity: 0; transition: opacity 0.3s;
        }

        /* Work section - light section */
        .cr-work-grid {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: 24px;
        }
        .cr-work-card {
          background: #E8E5E0;
          border-radius: 12px;
          padding: 40px;
          position: relative;
          overflow: hidden;
          transition: transform 0.2s;
        }
        .cr-work-card:hover {
          transform: translateY(-2px);
        }
        .cr-work-card-name {
          font-size: 24px;
          font-weight: 400;
          margin-bottom: 8px;
          color: #0F0F0F;
        }
        .cr-work-card-role {
          font-family: 'DM Mono', monospace;
          font-size: 12px;
          color: #666;
          margin-bottom: 16px;
        }
        .cr-work-card-desc {
          font-size: 14px;
          line-height: 1.7;
          color: #444;
          margin-bottom: 20px;
        }
        .cr-work-card-tech {
          display: flex;
          flex-wrap: wrap;
          gap: 6px;
        }
        .cr-work-chip {
          font-family: 'DM Mono', monospace;
          font-size: 11px;
          color: #555;
          background: rgba(15,15,15,0.06);
          border: 1px solid rgba(15,15,15,0.12);
          border-radius: 4px;
          padding: 3px 8px;
        }

        /* Experience section - dark section */
        .cr-exp-timeline {
          border-top: 1px solid #222;
        }
        .cr-exp-item {
          padding: 32px 0;
          border-bottom: 1px solid #222;
        }
        .cr-exp-header {
          display: flex;
          justify-content: space-between;
          align-items: baseline;
          margin-bottom: 12px;
        }
        .cr-exp-company {
          font-size: 18px;
          font-weight: 500;
        }
        .cr-exp-role {
          font-size: 14px;
          color: #999;
          margin-left: 12px;
        }
        .cr-exp-date {
          font-family: 'DM Mono', monospace;
          font-size: 12px;
          color: #666;
          white-space: nowrap;
        }
        .cr-exp-desc {
          font-size: 14px;
          line-height: 1.7;
          color: #CCC;
        }
        .cr-edu-label {
          font-family: 'DM Mono', monospace;
          font-size: 11px;
          color: #666;
          text-transform: uppercase;
          letter-spacing: 0.1em;
          margin-top: 32px;
          margin-bottom: 16px;
        }
        .cr-edu-item {
          padding: 20px 0;
          border-bottom: 1px solid #222;
        }
        .cr-edu-header {
          display: flex;
          justify-content: space-between;
          align-items: baseline;
        }
        .cr-edu-school {
          font-size: 16px;
          font-weight: 500;
        }
        .cr-edu-degree {
          font-size: 13px;
          color: #999;
          margin-left: 12px;
        }
        .cr-edu-date {
          font-family: 'DM Mono', monospace;
          font-size: 12px;
          color: #666;
          white-space: nowrap;
        }

        /* Skills section - light section */
        .cr-skills-grid {
          display: flex;
          flex-direction: column;
          gap: 32px;
        }
        .cr-skill-group {
          margin-bottom: 0;
        }
        .cr-skill-group-title {
          font-family: 'DM Mono', monospace;
          font-size: 11px;
          font-weight: 400;
          color: #666;
          text-transform: uppercase;
          letter-spacing: 0.1em;
          margin-bottom: 12px;
        }
        .cr-skill-tags {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
        }
        .cr-skill-tag {
          font-size: 13px;
          color: #444;
          background: rgba(15,15,15,0.05);
          border: 1px solid rgba(15,15,15,0.1);
          border-radius: 6px;
          padding: 6px 14px;
          display: inline-block;
        }

        /* About - dark section */
        .cr-about-wrap { display: flex; gap: 48px; align-items: center; }
        .cr-about-portrait { width: 240px; height: 240px; border-radius: 50%; background: #333; flex-shrink: 0; }
        .cr-about-right { flex: 1; }
        .cr-about-right h2 { font-size: 28px; margin-bottom: 8px; }
        .cr-about-role { color: #999; margin-bottom: 24px; font-family: 'DM Mono', monospace; font-size: 13px; }
        .cr-about-right p { font-size: 15px; line-height: 1.8; margin-bottom: 16px; color: #CCC; }
        .cr-about-thumbs { display: flex; gap: 12px; margin-top: 24px; }
        .cr-about-thumb { width: 100px; height: 100px; background: #333; border-radius: 8px; }
        .cr-about-skills-sidebar {
          margin-top: 32px;
          padding-top: 24px;
          border-top: 1px solid #222;
        }
        .cr-about-skills-sidebar h4 {
          font-family: 'DM Mono', monospace;
          font-size: 11px;
          color: #666;
          text-transform: uppercase;
          letter-spacing: 0.1em;
          margin-bottom: 16px;
        }
        .cr-about-skill-group {
          margin-bottom: 16px;
        }
        .cr-about-skill-title {
          font-family: 'DM Mono', monospace;
          font-size: 11px;
          color: #888;
          margin-bottom: 6px;
        }
        .cr-about-skill-tags {
          display: flex;
          flex-wrap: wrap;
          gap: 6px;
        }
        .cr-about-skill-tag {
          font-size: 12px;
          color: #AAA;
          background: rgba(255,255,255,0.06);
          border: 1px solid rgba(255,255,255,0.1);
          border-radius: 4px;
          padding: 3px 10px;
          display: inline-block;
        }

        /* Contact - dark section */
        .cr-contact-wrap { text-align: center; }
        .cr-contact-heading { font-size: 70px; font-weight: 300; margin-bottom: 32px; }
        .cr-contact-email {
          font-size: 22px; color: #FFF; text-decoration: none;
          display: inline-block; margin-bottom: 48px;
          border-bottom: 1px solid rgba(255,255,255,0.3); padding-bottom: 2px;
          transition: border-color 0.2s;
        }
        .cr-contact-email:hover { border-color: #FFF; }
        .cr-contact-links { display: flex; flex-direction: column; align-items: center; gap: 16px; }
        .cr-contact-link { font-size: 18px; color: #999; text-decoration: none; transition: color 0.2s; border-bottom: 1px solid transparent; }
        .cr-contact-link:hover { color: #FFF; border-bottom-color: rgba(255,255,255,0.3); }
        .cr-contact-wechat { position: relative; }
        .cr-wechat-qr-popup {
          position: absolute; bottom: calc(100% + 12px); left: 50%; transform: translateX(-50%);
          background: #1A1A1A; border: 1px solid #333; border-radius: 8px;
          padding: 12px; box-shadow: 0 8px 32px rgba(0,0,0,0.6);
          opacity: 0; pointer-events: none; transition: opacity 0.2s;
          z-index: 10;
        }
        .cr-contact-wechat:hover .cr-wechat-qr-popup { opacity: 1; pointer-events: auto; }
        .cr-wechat-qr-popup::after {
          content: ''; position: absolute; top: 100%; left: 50%; transform: translateX(-50%);
          border: 6px solid transparent; border-top-color: #333;
        }
        .cr-wechat-qr-img { width: 160px; height: 160px; display: block; border-radius: 4px; }

        /* Fallback empty state */
        .cr-empty-state {
          font-family: 'DM Mono', monospace;
          font-size: 13px;
          color: #555;
          text-align: center;
          padding: 40px 0;
        }
      `}</style>

      <nav className="creative-nav">
        {SECTIONS.map((s, i) => (
          <button
            key={s.id}
            className={`nav-btn ${i === currentSection ? 'active' : ''}`}
            onClick={() => goToSection(i)}
          >
            {s.label}
          </button>
        ))}
      </nav>

      <div className="creative-sections">
      {/* Section 0: Hero (dark) */}
      <section className="section section-dark" ref={(el) => registerSection(0, el)}>
        <div className="cr-hero-wrap">
          <h1 className="cr-hero-name">{info.name || 'Your Name'}</h1>
        </div>
      </section>

      {/* Section 1: Work / Projects (light) */}
      <section className="section section-light" ref={(el) => registerSection(1, el)}>
        <div className="section-inner">
          <div className="creative-section-label">Selected work</div>
          {projects.length > 0 ? (
            <div className="cr-work-grid">
              {projects.map((p, i) => (
                <div key={i} className="cr-work-card">
                  <h3 className="cr-work-card-name">{p.name}</h3>
                  <p className="cr-work-card-role">{p.role || ''}{p.period ? ` · ${p.period}` : ''}</p>
                  <p className="cr-work-card-desc">{p.description}</p>
                  {p.tech_stack && p.tech_stack.length > 0 && (
                    <div className="cr-work-card-tech">
                      {(typeof p.tech_stack === 'string'
                        ? p.tech_stack.split(',').map((s: string) => s.trim()).filter(Boolean)
                        : Array.isArray(p.tech_stack) ? p.tech_stack : []
                      ).map((tech: string, idx: number) => (
                        <span key={idx} className="cr-work-chip">{tech}</span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="cr-empty-state">No projects listed yet</div>
          )}
        </div>
      </section>

      {/* Section 2: Experience + Education (dark) */}
      <section className="section section-dark" ref={(el) => registerSection(2, el)}>
        <div className="section-inner">
          <div className="creative-section-label">Experience</div>
          {work.length > 0 && (
            <div className="cr-exp-timeline">
              {work.map((exp, i) => (
                <div key={i} className="cr-exp-item">
                  <div className="cr-exp-header">
                    <div>
                      <span className="cr-exp-company">{exp.company}</span>
                      <span className="cr-exp-role">{exp.position}</span>
                    </div>
                    <span className="cr-exp-date">{exp.period}</span>
                  </div>
                  {exp.description && (
                    <div className="cr-exp-desc">{exp.description}</div>
                  )}
                </div>
              ))}
            </div>
          )}
          {educations.length > 0 && (
            <>
              <div className="cr-edu-label">Education</div>
              {educations.map((edu, i) => (
                <div key={`edu-${i}`} className="cr-edu-item">
                  <div className="cr-edu-header">
                    <div>
                      <span className="cr-edu-school">{edu.school}</span>
                      <span className="cr-edu-degree">{edu.degree}{edu.major ? ` · ${edu.major}` : ''}</span>
                    </div>
                    <span className="cr-edu-date">{edu.period}</span>
                  </div>
                </div>
              ))}
            </>
          )}
          {work.length === 0 && educations.length === 0 && (
            <div className="cr-empty-state">No experience listed yet</div>
          )}
        </div>
      </section>

      {/* Section 3: About (light) */}
      <section className="section section-light" ref={(el) => registerSection(3, el)}>
        <div className="section-inner">
          <div className="cr-about-wrap">
            <div className="cr-about-portrait" />
            <div className="cr-about-right">
              <h2>{info.name || 'Your Name'}</h2>
              <p className="cr-about-role">{info.target_position || 'Creative Professional'}</p>
              <p>{info.self_intro || 'A passionate creative professional dedicated to crafting meaningful digital experiences that bridge the gap between aesthetics and functionality.'}</p>
              <p>I believe great design is invisible — it removes friction, guides attention, and makes complex things feel simple. Every pixel should have purpose.</p>
              {Object.keys(skills).length > 0 && (
                <div className="cr-about-skills-sidebar">
                  <h4>Core Skills</h4>
                  {Object.entries(skills).slice(0, 3).map(([group, items]) => (
                    <div key={group} className="cr-about-skill-group">
                      <div className="cr-about-skill-title">{group}</div>
                      <div className="cr-about-skill-tags">
                        {(items || []).slice(0, 5).map((skill: string, idx: number) => (
                          <span key={idx} className="cr-about-skill-tag">{skill}</span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* Section 4: Contact (dark) */}
      <section className="section section-dark" ref={(el) => registerSection(4, el)}>
        <div className="cr-contact-wrap">
          <h2 className="cr-contact-heading">Get in touch</h2>
          <a className="cr-contact-email" href={`mailto:${info.email || ''}`}>
            {info.email || 'your@email.com'}
          </a>
          <div className="cr-contact-links">
            {info.phone && (
              <a className="cr-contact-link" href={`tel:${info.phone}`}>
                {info.phone}
              </a>
            )}
            {info.github && (
              <a className="cr-contact-link" href={info.github} target="_blank" rel="noopener noreferrer">
                GitHub
              </a>
            )}
            <span className="cr-contact-wechat">
              <span className="cr-contact-link">{info.wechat_name || '微信'}</span>
              {info.wechat_qr && (
                <div className="cr-wechat-qr-popup">
                  <img src={info.wechat_qr} alt="WeChat QR" className="cr-wechat-qr-img" />
                </div>
              )}
            </span>
          </div>
        </div>
      </section>
      </div>
    </div>
  );
};
