import React from 'react';
import type { KnowledgeData, PortfolioConfig } from '../../../api/portfolio';
import { useScrollNavigation } from '../hooks/useScrollNavigation';
import { PortfolioNav, type NavSection } from '../components/PortfolioNav';

interface DeveloperThemeProps {
  knowledge: KnowledgeData;
  config: PortfolioConfig;
}

const SECTIONS: NavSection[] = [
  { id: 'hero', label: 'Home' },
  { id: 'projects', label: 'Projects' },
  { id: 'experience', label: 'Exp' },
  { id: 'stack', label: 'Stack' },
  { id: 'contact', label: 'About' },
];

export const DeveloperTheme: React.FC<DeveloperThemeProps> = ({ knowledge }) => {
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
  const skillNames: string[] = skillSections.length > 0
    ? skillSections.flatMap(s => s.items.map(item => item.name))
    : Object.values(knowledge.skills?.skill_groups || {}).flat();
  const educations = (knowledge.education?.education_list || []) as any[];
  const { currentSection, registerSection, goToSection } = useScrollNavigation(SECTIONS.length);

  return (
    <div className="developer-theme">
      <style>{`
        .developer-theme {
          font-family: 'Inter', sans-serif;
          background-color: #0A0A0A;
          color: #FFFFFF;
          height: 100%;
          display: flex;
          flex-direction: column;
        }
        .developer-nav {
          flex-shrink: 0;
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 20px 40px;
          background: #0A0A0A;
          font-family: 'JetBrains Mono', monospace;
        }
        .developer-sections {
          flex: 1;
          overflow-y: auto;
          scroll-behavior: smooth;
          scrollbar-width: none;
          -ms-overflow-style: none;
        }
        .developer-sections::-webkit-scrollbar {
          display: none;
        }
        .developer-sections .section {
          min-height: 100%;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 80px 60px;
        }
        .developer-sections .section-inner {
          max-width: 960px;
          width: 100%;
        }
        .developer-nav .nav-left {
          font-size: 16px;
        }
        .developer-nav .nav-links {
          display: flex;
          gap: 24px;
        }
        .developer-nav .nav-btn {
          background: none;
          border: none;
          color: #555;
          cursor: pointer;
          font-family: inherit;
          font-size: 12px;
          padding: 0;
          transition: color 0.2s;
        }
        .developer-nav .nav-btn:hover,
        .developer-nav .nav-btn.active {
          color: #FFF;
        }

        /* Terminal Hero */
        .dev-hero { flex-direction: column; text-align: center; }
        .dev-hero-greeting {
          font-family: 'JetBrains Mono', monospace;
          font-size: 18px; color: #888; margin-bottom: 20px;
        }
        .dev-hero-cursor {
          display: inline-block; width: 10px; height: 20px;
          background: #3DD68C; margin-left: 4px;
          animation: dev-blink 1s infinite;
        }
        @keyframes dev-blink { 0%,50% { opacity:1; } 51%,100% { opacity:0; } }
        .dev-hero-name { font-size: 52px; font-weight: 700; letter-spacing: -0.02em; margin-bottom: 12px; }
        .dev-hero-role { font-size: 22px; color: #AAA; margin-bottom: 24px; }
        .dev-hero-badge {
          display: inline-flex; align-items: center; gap: 8px;
          font-family: 'JetBrains Mono', monospace; font-size: 12px; color: #888;
        }
        .dev-hero-dot { width: 8px; height: 8px; background: #3DD68C; border-radius: 50%; animation: dev-blink 2s infinite; }

        /* Section label */
        .dev-section-label {
          font-family: 'JetBrains Mono', monospace;
          font-size: 11px; color: #555; text-transform: uppercase;
          letter-spacing: 0.1em; margin-bottom: 40px;
        }

        /* Projects Grid */
        .dev-projects { display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; }
        .dev-project-card {
          background: #111; border: 1px solid #222; padding: 24px;
          transition: border-color 0.2s;
        }
        .dev-project-card:hover { border-color: #333; }
        .dev-project-name { font-family: 'JetBrains Mono', monospace; font-size: 16px; margin-bottom: 8px; }
        .dev-project-desc { font-size: 13px; color: #888; line-height: 1.6; margin-bottom: 16px; }
        .dev-project-chips { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; }
        .dev-project-chip {
          font-family: 'JetBrains Mono', monospace; font-size: 11px;
          color: #888; background: #1A1A1A; padding: 3px 8px; border: 1px solid #222;
        }
        .dev-project-links { display: flex; gap: 12px; font-family: 'JetBrains Mono', monospace; font-size: 12px; }
        .dev-project-links a { color: #4D9DE0; text-decoration: none; }

        /* Tech Stack */
        .dev-stack-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 24px; }
        .dev-stack-cat h4 { font-family: 'JetBrains Mono', monospace; font-size: 11px; color: #555; margin-bottom: 16px; text-transform: uppercase; }
        .dev-stack-chips { display: flex; flex-direction: column; gap: 6px; }
        .dev-stack-chip {
          font-family: 'JetBrains Mono', monospace; font-size: 12px;
          color: #AAA; background: #111; border: 1px solid #222;
          padding: 4px 10px; display: inline-block; width: fit-content;
        }

        /* Experience + Education */
        .dev-timeline { border-top: 1px solid #1A1A1A; }
        .dev-timeline-item { padding: 28px 0; border-bottom: 1px solid #1A1A1A; }
        .dev-timeline-header { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 8px; }
        .dev-timeline-company { font-size: 15px; font-weight: 600; }
        .dev-timeline-role { color: #AAA; font-size: 13px; margin-left: 6px; }
        .dev-timeline-date { font-family: 'JetBrains Mono', monospace; font-size: 12px; color: #555; }
        .dev-timeline-desc { font-size: 13px; color: #888; line-height: 1.6; }
        .dev-edu-block { margin-top: 32px; }
        .dev-edu-header { font-family: 'JetBrains Mono', monospace; font-size: 11px; color: #3DD68C; margin-bottom: 12px; }

        /* About + Contact */
        .dev-about-wrap { display: flex; gap: 64px; align-items: flex-start; }
        .dev-about-main { flex: 2; }
        .dev-about-main p { font-size: 15px; line-height: 1.8; color: #CCC; margin-bottom: 16px; }
        .dev-interest-chip {
          display: inline-block; font-family: 'JetBrains Mono', monospace;
          font-size: 12px; color: #888; background: #111; border: 1px solid #222;
          padding: 6px 14px; margin: 4px 6px 4px 0;
        }
        .dev-contact-links { margin-top: 32px; }
        .dev-contact-links a {
          display: block; font-family: 'JetBrains Mono', monospace;
          font-size: 14px; color: #4D9DE0; text-decoration: none; margin-bottom: 12px;
        }
        .dev-contact-grid { display: flex; flex-wrap: wrap; gap: 24px; margin-top: 32px; }
        .dev-contact-item {
          display: flex; align-items: center; gap: 8px;
          font-family: 'JetBrains Mono', monospace; font-size: 13px;
        }
        .dev-contact-item a { color: #4D9DE0; text-decoration: none; }
        .dev-contact-item span { color: #888; }
        .dev-wechat-wrap { position: relative; display: inline-block; cursor: pointer; }
        .dev-wechat-popup { display: none; position: absolute; bottom: 100%; left: 50%; transform: translateX(-50%); margin-bottom: 8px; z-index: 100; background: #1A1A1A; padding: 8px; border-radius: 8px; border: 1px solid #333; }
        .dev-wechat-wrap:hover .dev-wechat-popup { display: block; }
        .dev-wechat-popup img { width: 150px; height: 150px; border-radius: 4px; }
        .dev-wechat-popup::after { content: ''; position: absolute; top: 100%; left: 50%; transform: translateX(-50%); border: 6px solid transparent; border-top-color: #1A1A1A; }
      `}</style>

      <nav className="developer-nav">
        <span className="nav-left">{info.name || 'Li Chen'}</span>
        <div className="nav-links">
          {SECTIONS.map((s, i) => (
            <button
              key={s.id}
              className={`nav-btn ${i === currentSection ? 'active' : ''}`}
              onClick={() => goToSection(i)}
            >
              {s.label}
            </button>
          ))}
        </div>
      </nav>

      <div className="developer-sections">
      {/* Section 1: Terminal Hero */}
      <section className="section dev-hero" ref={(el) => registerSection(0, el)}>
        <div>
          <p className="dev-hero-greeting">
            {'>'} Hello, I'm {info.name || 'Li Chen'}
            <span className="dev-hero-cursor" />
          </p>
          <h1 className="dev-hero-name">{info.target_position || 'Full-Stack Engineer'}</h1>
          <p className="dev-hero-role">
            {skillNames.slice(0, 3).join(' / ') || 'React / Go / Kubernetes'}
          </p>
          <div className="dev-hero-badge">
            <span className="dev-hero-dot" />
            <span>{info.city || 'Shanghai'} · Open to new roles</span>
          </div>
        </div>
      </section>

      {/* Section 2: Featured Projects */}
      <section className="section" ref={(el) => registerSection(1, el)}>
        <div className="section-inner">
          <div className="dev-section-label">Featured Projects</div>
          <div className="dev-projects">
            {projects.slice(0, 4).map((p, i) => (
              <div key={i} className="dev-project-card">
                <div className="dev-project-name">{p.name}</div>
                <div className="dev-project-desc">{p.description}</div>
                <div className="dev-project-chips">
                  {(p.tech_stack || '').split(/[,，\/]/).map((t: string, j: number) => (
                    <span key={j} className="dev-project-chip">{t.trim()}</span>
                  ))}
                </div>
                <div className="dev-project-links">
                  <a href="#">GitHub</a>
                  <a href="#">Live</a>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Section 3: Experience + Education */}
      <section className="section" ref={(el) => registerSection(2, el)}>
        <div className="section-inner">
          <div className="dev-section-label">Experience</div>
          <div className="dev-timeline">
            {work.map((exp, i) => (
              <div key={i} className="dev-timeline-item">
                <div className="dev-timeline-header">
                  <div>
                    <span className="dev-timeline-company">{exp.company}</span>
                    <span className="dev-timeline-role">{exp.position}</span>
                  </div>
                  <span className="dev-timeline-date">{exp.period}</span>
                </div>
                <div className="dev-timeline-desc">{exp.description}</div>
              </div>
            ))}
            {educations.length > 0 && (
              <div className="dev-edu-block">
                <div className="dev-edu-header">Education</div>
                {educations.map((edu, i) => (
                  <div key={`edu-${i}`} className="dev-timeline-item" style={{padding: '16px 0'}}>
                    <div className="dev-timeline-header">
                      <div>
                        <span className="dev-timeline-company" style={{fontSize: 14}}>{edu.school}</span>
                        <span className="dev-timeline-role">{edu.degree} · {edu.major}</span>
                      </div>
                      <span className="dev-timeline-date">{edu.period}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </section>

      {/* Section 4: Tech Stack */}
      <section className="section" ref={(el) => registerSection(3, el)}>
        <div className="section-inner">
          <div className="dev-section-label">Tech Stack</div>
          <div className="dev-stack-grid">
            {Object.entries(skills).length > 0 ? (
              Object.entries(skills).slice(0, 4).map(([cat, items]) => (
                <div key={cat} className="dev-stack-cat">
                  <h4>{cat}</h4>
                  <div className="dev-stack-chips">
                    {items.slice(0, 8).map((s: string, j: number) => (
                      <span key={j} className="dev-stack-chip">{s}</span>
                    ))}
                  </div>
                </div>
              ))
            ) : (
              <>
                {['Languages', 'Frameworks', 'Infrastructure', 'Tools'].map(cat => (
                  <div key={cat} className="dev-stack-cat">
                    <h4>{cat}</h4>
                    <div className="dev-stack-chips">
                      {['TypeScript', 'Python', 'Go', 'Rust'].slice(0, 4).map((s, j) => (
                        <span key={j} className="dev-stack-chip">{s}</span>
                      ))}
                    </div>
                  </div>
                ))}
              </>
            )}
          </div>
        </div>
      </section>

      {/* Section 5: About + Contact */}
      <section className="section" ref={(el) => registerSection(4, el)}>
        <div className="section-inner">
          <div className="dev-section-label">About</div>
          <div className="dev-about-wrap">
            <div className="dev-about-main">
              <p>{info.self_intro || 'Engineer focused on building reliable, scalable systems. Passionate about developer tools, API design, and cloud infrastructure.'}</p>
              <p>I care about clean architecture, good test coverage, and products that respect their users' time. Outside work I contribute to open source and experiment with side projects.</p>
              <div>
                <span className="dev-interest-chip">Open Source</span>
                <span className="dev-interest-chip">CLI Tools</span>
                <span className="dev-interest-chip">Cloud Native</span>
              </div>
              <div className="dev-contact-grid">
                {info.email && (
                  <div className="dev-contact-item">
                    <span>Email</span>
                    <a href={`mailto:${info.email}`}>{info.email}</a>
                  </div>
                )}
                {info.phone && (
                  <div className="dev-contact-item">
                    <span>Phone</span>
                    <a href={`tel:${info.phone}`}>{info.phone}</a>
                  </div>
                )}
                {info.github && (
                  <div className="dev-contact-item">
                    <span>GitHub</span>
                    <a href={info.github} target="_blank" rel="noopener noreferrer">{info.github.replace(/^https?:\/\//, '')}</a>
                  </div>
                )}
                <div className="dev-contact-item">
                  <span>WeChat</span>
                  {info.wechat_qr ? (
                    <div className="dev-wechat-wrap">
                      <span style={{ color: '#4D9DE0' }}>{info.wechat_name || '微信'}</span>
                      <div className="dev-wechat-popup">
                        <img src={info.wechat_qr} alt="WeChat QR" />
                      </div>
                    </div>
                  ) : (
                    <span style={{ color: '#CCC' }}>{info.wechat_name || '微信'}</span>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>
      </div>
    </div>
  );
};
