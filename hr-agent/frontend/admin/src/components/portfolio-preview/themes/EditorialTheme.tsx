import React from 'react';
import type { KnowledgeData, PortfolioConfig } from '../../../api/portfolio';
import { useScrollNavigation } from '../hooks/useScrollNavigation';
import { PortfolioNav, type NavSection } from '../components/PortfolioNav';

interface EditorialThemeProps {
  knowledge: KnowledgeData;
  config: PortfolioConfig;
}

const SECTIONS: NavSection[] = [
  { id: 'hero', label: 'Home' },
  { id: 'about', label: 'About' },
  { id: 'work', label: 'Work' },
  { id: 'experience', label: 'Experience' },
  { id: 'contact', label: 'Contact' },
];

export const EditorialTheme: React.FC<EditorialThemeProps> = ({ knowledge }) => {
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
    <div className="editorial-theme">
      <style>{`
        .editorial-theme {
          font-family: 'Playfair Display', 'Times New Roman', serif;
          background-color: #FAFAF8;
          color: #1A1A1A;
          height: 100%;
          display: flex;
          flex-direction: column;
        }
        .editorial-nav {
          flex-shrink: 0;
          display: flex;
          justify-content: flex-end;
          gap: 32px;
          padding: 24px 40px;
          font-family: 'Inter', sans-serif;
          font-size: 13px;
          letter-spacing: 0.05em;
          text-transform: uppercase;
          background: #FAFAF8;
        }
        .editorial-sections {
          flex: 1;
          overflow-y: auto;
          scroll-behavior: smooth;
          scrollbar-width: none;
          -ms-overflow-style: none;
        }
        .editorial-sections::-webkit-scrollbar {
          display: none;
        }
        .editorial-sections .section {
          min-height: 100%;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 80px 40px;
        }
        .editorial-sections .section-inner {
          max-width: 900px;
          width: 100%;
        }
        .editorial-nav .nav-btn {
          background: none;
          border: none;
          color: #999;
          cursor: pointer;
          font-family: inherit;
          font-size: inherit;
          letter-spacing: inherit;
          text-transform: inherit;
          padding: 0;
          transition: color 0.2s;
        }
        .editorial-nav .nav-btn:hover,
        .editorial-nav .nav-btn.active {
          color: #C4502A;
        }
        .editorial-section-label {
          font-family: 'JetBrains Mono', monospace;
          font-size: 11px;
          letter-spacing: 0.1em;
          text-transform: uppercase;
          color: #999;
          margin-bottom: 40px;
        }

        /* Hero */
        .ed-hero { text-align: center; flex-direction: column; }
        .ed-hero-name { font-size: 64px; font-weight: 400; margin-bottom: 16px; }
        .ed-hero-role { font-family: 'Inter', sans-serif; font-size: 22px; color: #333; margin-bottom: 24px; }
        .ed-hero-badge { display: inline-flex; align-items: center; gap: 8px; font-family: 'Inter', sans-serif; font-size: 13px; color: #666; }
        .ed-hero-dot { width: 8px; height: 8px; background: #C4502A; border-radius: 50%; }

        /* Work grid */
        .ed-work-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 24px; }
        .ed-work-card { border: 1px solid #E8E6E1; padding: 24px; transition: transform 0.2s; }
        .ed-work-card:hover { transform: translateY(-2px); }
        .ed-work-meta { font-family: 'Inter', sans-serif; font-size: 12px; color: #999; margin-bottom: 12px; }
        .ed-work-title { font-family: 'Inter', sans-serif; font-size: 20px; font-weight: 500; margin-bottom: 12px; }
        .ed-work-desc { font-family: 'Inter', sans-serif; font-size: 14px; color: #666; line-height: 1.6; margin-bottom: 12px; }
        .ed-work-link { font-family: 'Inter', sans-serif; font-size: 14px; color: #C4502A; text-decoration: none; }

        /* About + Life two-column */
        .ed-about-layout { display: flex; gap: 64px; }
        .ed-about-main { flex: 3; }
        .ed-about-main p { font-family: 'Inter', sans-serif; font-size: 16px; line-height: 1.8; color: #333; margin-bottom: 20px; }
        .ed-about-main p:first-child { font-size: 18px; }
        .ed-about-sidebar { flex: 2; }
        .ed-about-sidebar h4 { font-family: 'Inter', sans-serif; font-size: 14px; font-weight: 600; margin-bottom: 16px; color: #1A1A1A; }
        .ed-life-item { display: flex; gap: 12px; margin-bottom: 16px; align-items: center; }
        .ed-life-placeholder { width: 48px; height: 48px; background: #E8E6E1; border-radius: 4px; flex-shrink: 0; }
        .ed-life-text { font-family: 'Inter', sans-serif; font-size: 13px; color: #666; line-height: 1.4; }

        /* Experience */
        .ed-timeline { border-top: 1px solid #E8E6E1; }
        .ed-timeline-item { padding: 32px 0; border-bottom: 1px solid #E8E6E1; }
        .ed-timeline-header { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 12px; }
        .ed-timeline-company { font-family: 'Inter', sans-serif; font-size: 18px; font-weight: 600; }
        .ed-timeline-role { font-family: 'Inter', sans-serif; font-size: 15px; color: #666; margin-left: 8px; }
        .ed-timeline-date { font-family: 'Inter', sans-serif; font-size: 14px; color: #999; white-space: nowrap; }
        .ed-timeline-desc { font-family: 'Inter', sans-serif; font-size: 14px; color: #333; line-height: 1.7; }

        /* Education within Experience */
        .ed-edu-label { font-family: 'Inter', sans-serif; font-size: 12px; color: #C4502A; text-transform: uppercase; letter-spacing: 0.05em; margin-top: 24px; margin-bottom: 12px; }
        .ed-edu-item { font-family: 'Inter', sans-serif; font-size: 14px; color: #666; display: flex; gap: 16px; margin-bottom: 8px; }

        /* Contact */
        .ed-contact { text-align: center; flex-direction: column; }
        .ed-contact-heading { font-size: 48px; font-weight: 400; margin-bottom: 16px; }
        .ed-contact-text { font-family: 'Inter', sans-serif; font-size: 16px; color: #666; max-width: 480px; line-height: 1.6; margin-bottom: 32px; }
        .ed-contact-email { font-family: 'Inter', sans-serif; font-size: 24px; color: #C4502A; text-decoration: none; display: block; margin-bottom: 32px; }
        .ed-contact-socials { display: flex; gap: 24px; justify-content: center; font-family: 'Inter', sans-serif; font-size: 14px; }
        .ed-contact-socials a { color: #999; text-decoration: none; }
        .ed-contact-socials a:hover { color: #C4502A; }

        /* Skills sidebar */
        .ed-skill-group { margin-bottom: 20px; }
        .ed-skill-group-title { font-family: 'Inter', sans-serif; font-size: 12px; font-weight: 600; color: #1A1A1A; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px; }
        .ed-skill-tags { display: inline-flex; flex-wrap: wrap; gap: 6px; }
        .ed-skill-tag { font-family: 'Inter', sans-serif; font-size: 12px; color: #555; background: #F0EEE8; border-radius: 4px; padding: 4px 10px; display: inline-block; }

        /* Contact links */
        .ed-contact-links { display: flex; flex-direction: column; align-items: center; gap: 12px; margin-bottom: 32px; }
        .ed-contact-link { font-family: 'Inter', sans-serif; font-size: 15px; color: #666; text-decoration: none; display: inline-flex; align-items: center; gap: 8px; transition: color 0.2s; }
        .ed-contact-link:hover { color: #C4502A; }
        .ed-contact-icon { font-size: 16px; color: #999; }

        /* WeChat QR tooltip */
        .wechat-wrapper { position: relative; display: inline-block; cursor: pointer; }
        .wechat-qr-popup { display: none; position: absolute; bottom: 100%; left: 50%; transform: translateX(-50%); margin-bottom: 8px; z-index: 100; background: #fff; padding: 8px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
        .wechat-wrapper:hover .wechat-qr-popup { display: block; }
        .wechat-qr-popup img { width: 150px; height: 150px; border-radius: 8px; display: block; }
        .wechat-qr-popup::after { content: ''; position: absolute; top: 100%; left: 50%; transform: translateX(-50%); border: 6px solid transparent; border-top-color: white; }
      `}</style>

      <nav className="editorial-nav">
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

      <div className="editorial-sections">
      {/* Section 1: Hero */}
      <section className="section ed-hero" ref={(el) => registerSection(0, el)}>
        <div className="section-inner">
          <h1 className="ed-hero-name">{info.name || 'Zhang Wei'}</h1>
          <p className="ed-hero-role">{info.target_position || 'Senior Product Manager'}</p>
          <div className="ed-hero-badge">
            <span className="ed-hero-dot" />
            <span>{info.city || 'Beijing'} · Open to opportunities</span>
          </div>
        </div>
      </section>

      {/* Section 2: About + Skills */}
      <section className="section" ref={(el) => registerSection(1, el)}>
        <div className="section-inner">
          <div className="editorial-section-label">About</div>
          <div className="ed-about-layout">
            <div className="ed-about-main">
              <p>{info.self_intro || 'Product manager with 5+ years experience in AI and B2B products, passionate about building solutions that users love.'}</p>
              <p>I believe great products come from deep user understanding and iterative delivery. My approach combines data-driven decision making with empathic design thinking.</p>
              <blockquote style={{
                fontStyle: 'italic', fontSize: '22px', color: '#666',
                textAlign: 'center', margin: '56px 0', lineHeight: '1.6'
              }}>
                "Good products are built from understanding, not assumptions."
              </blockquote>
              <p>Outside of work, I enjoy exploring new technologies, reading about behavioral economics, and contributing to product communities.</p>
            </div>
            <div className="ed-about-sidebar">
              <h4>Skills</h4>
              {Object.keys(skills).length > 0 ? (
                Object.entries(skills).map(([group, items]) => (
                  <div key={group} className="ed-skill-group">
                    <div className="ed-skill-group-title">{group}</div>
                    <div className="ed-skill-tags">
                      {(items || []).map((skill: string, idx: number) => (
                        <span key={idx} className="ed-skill-tag">{skill}</span>
                      ))}
                    </div>
                  </div>
                ))
              ) : (
                <div className="ed-life-text">No skills listed</div>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* Section 3: Selected Work */}
      <section className="section" ref={(el) => registerSection(2, el)}>
        <div className="section-inner">
          <div className="editorial-section-label">Selected work</div>
          <div className="ed-work-grid">
            {projects.slice(0, 4).map((p, i) => (
              <div key={i} className="ed-work-card">
                <div className="ed-work-meta">{p.period || '2024'} — {p.role || 'PM'}</div>
                <div className="ed-work-title">{p.name}</div>
                <div className="ed-work-desc">{p.description}</div>
                <a className="ed-work-link" href="#">→ Read more</a>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Section 4: Experience + Education */}
      <section className="section" ref={(el) => registerSection(3, el)}>
        <div className="section-inner">
          <div className="editorial-section-label">Experience</div>
          <div className="ed-timeline">
            {work.map((exp, i) => (
              <div key={i} className="ed-timeline-item">
                <div className="ed-timeline-header">
                  <div>
                    <span className="ed-timeline-company">{exp.company}</span>
                    <span className="ed-timeline-role">{exp.position}</span>
                  </div>
                  <span className="ed-timeline-date">{exp.period}</span>
                </div>
                <div className="ed-timeline-desc">{exp.description}</div>
              </div>
            ))}
            {educations.length > 0 && (
              <>
                <div className="ed-edu-label">Education</div>
                {educations.map((edu, i) => (
                  <div key={`edu-${i}`} className="ed-timeline-item" style={{ padding: '16px 0' }}>
                    <div className="ed-timeline-header">
                      <div>
                        <span className="ed-timeline-company" style={{ fontSize: 16 }}>{edu.school}</span>
                        <span className="ed-timeline-role">{edu.degree} · {edu.major}</span>
                      </div>
                      <span className="ed-timeline-date">{edu.period}</span>
                    </div>
                  </div>
                ))}
              </>
            )}
          </div>
        </div>
      </section>

      {/* Section 5: Contact */}
      <section className="section ed-contact" ref={(el) => registerSection(4, el)}>
        <div>
          <h2 className="ed-contact-heading">Let's talk.</h2>
          <p className="ed-contact-text">
            I'm currently exploring new opportunities. If you have a role, a project, or just a conversation — I'd love to connect.
          </p>
          <div className="ed-contact-links">
            {info.email && (
              <a className="ed-contact-link" href={`mailto:${info.email}`}>
                <span className="ed-contact-icon">✉</span>
                <span>{info.email}</span>
              </a>
            )}
            {info.phone && (
              <a className="ed-contact-link" href={`tel:${info.phone}`}>
                <span className="ed-contact-icon">☎</span>
                <span>{info.phone}</span>
              </a>
            )}
            {info.github && (
              <a className="ed-contact-link" href={info.github} target="_blank" rel="noopener noreferrer">
                <span className="ed-contact-icon">⟠</span>
                <span>GitHub</span>
              </a>
            )}
            <span className="wechat-wrapper">
              <span className="ed-contact-link">
                <span className="ed-contact-icon">✦</span>
                <span>{info.wechat_name || '微信'}</span>
              </span>
              {info.wechat_qr && (
                <span className="wechat-qr-popup">
                  <img src={info.wechat_qr} alt="WeChat QR Code" />
                </span>
              )}
            </span>
          </div>
        </div>
      </section>
      </div>
    </div>
  );
};
