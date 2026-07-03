import React from 'react';
import type { KnowledgeData, PortfolioConfig } from '../../../api/portfolio';
import { useScrollNavigation } from '../hooks/useScrollNavigation';

interface PersonalBrandThemeProps {
  knowledge: KnowledgeData;
  config: PortfolioConfig;
}

const SECTIONS = [
  { id: 'hero', label: 'Home' },
  { id: 'about', label: 'About' },
  { id: 'work', label: 'Work' },
  { id: 'experience', label: 'Experience' },
  { id: 'contact', label: 'Contact' },
];

export const PersonalBrandTheme: React.FC<PersonalBrandThemeProps> = ({ knowledge }) => {
  const info = (knowledge.personal_info || {}) as Record<string, any>;
  const work = (knowledge.work_experience?.work_list || []) as any[];
  const projects = (knowledge.projects?.project_list || []) as any[];
  const educations = (knowledge.education?.education_list || []) as any[];
  const skillSections = knowledge.skills?.skill_sections || [];
  const skills: Record<string, string[]> = skillSections.length > 0
    ? Object.fromEntries(skillSections.map(s => [
        s.title,
        s.items.map(item => item.desc ? `${item.name}：${item.desc}` : item.name)
      ]))
    : (knowledge.skills?.skill_groups || {}) as Record<string, string[]>;
  const { currentSection, registerSection, goToSection } = useScrollNavigation(SECTIONS.length);

  return (
    <div className="personal-brand-theme">
      <style>{`
        .personal-brand-theme {
          font-family: 'Inter', sans-serif;
          background-color: #FEFDF9;
          color: #1A1A1A;
          height: 100%;
          display: flex;
          flex-direction: column;
        }
        .personal-nav {
          flex-shrink: 0;
          display: flex;
          justify-content: flex-end;
          gap: 28px;
          padding: 24px 40px;
          font-size: 14px;
          background: #FEFDF9;
        }
        .personal-sections {
          flex: 1;
          overflow-y: auto;
          scroll-behavior: smooth;
          scrollbar-width: none;
          -ms-overflow-style: none;
        }
        .personal-sections::-webkit-scrollbar {
          display: none;
        }
        .personal-sections .section {
          min-height: 100%;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 80px 40px;
        }
        .personal-sections .section-inner {
          max-width: 680px;
          width: 100%;
        }
        .personal-nav .nav-btn {
          background: none; border: none; color: #999;
          cursor: pointer; font-family: inherit; font-size: inherit;
          padding: 0; transition: color 0.2s;
        }
        .personal-nav .nav-btn:hover,
        .personal-nav .nav-btn.active { color: #C4502A; }

        /* Hero */
        .pb-hero-wrap {
          display: flex; gap: 48px; align-items: center;
        }
        .pb-hero-left { flex: 1; }
        .pb-hero-name {
          font-family: 'Lora', serif;
          font-size: 52px; font-weight: 400; margin-bottom: 16px;
        }
        .pb-hero-role {
          font-size: 22px; color: #333; margin-bottom: 24px; line-height: 1.5;
        }
        .pb-hero-badge {
          display: inline-flex; align-items: center; gap: 8px; font-size: 14px; color: #666;
        }
        .pb-hero-dot {
          width: 8px; height: 8px; background: #3DD68C; border-radius: 50%;
          animation: pb-pulse 2s infinite;
        }
        @keyframes pb-pulse { 0%,100% { opacity:1; } 50% { opacity:0.5; } }
        .pb-hero-portrait {
          width: 160px; height: 160px; border-radius: 50%;
          background: #EEE5D8; flex-shrink: 0;
        }

        /* Section label for personal brand */
        .pb-section-title {
          font-family: 'Lora', serif;
          font-size: 32px; margin-bottom: 32px;
        }
        .pb-body-text { font-size: 16px; line-height: 1.75; color: #333; }
        .pb-body-text p { margin-bottom: 20px; }

        /* Pull quote */
        .pb-pull-quote {
          font-family: 'Lora', serif; font-style: italic;
          font-size: 22px; text-align: center;
          margin: 56px 0; line-height: 1.6; color: #666;
        }

        /* Selected Work (narrative blocks) */
        .pb-work-entry { padding: 32px 0; border-bottom: 1px solid #E8E4D8; }
        .pb-work-header { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 8px; }
        .pb-work-name { font-size: 18px; font-weight: 600; font-family: 'Lora', serif; }
        .pb-work-year { font-size: 14px; color: #999; }
        .pb-work-role { font-size: 14px; color: #666; margin-bottom: 12px; }
        .pb-work-story { font-size: 15px; line-height: 1.7; color: #333; margin-bottom: 12px; }
        .pb-work-metric { font-size: 14px; color: #C4502A; margin-bottom: 8px; }
        .pb-work-link a {
          font-size: 14px; color: #C4502A; text-decoration: none;
          border-bottom: 1px solid transparent; transition: border-color 0.2s;
        }
        .pb-work-link a:hover { border-bottom-color: #C4502A; }

        /* Experience Timeline */
        .pb-exp-timeline {
          position: relative;
          padding-left: 28px;
          margin-bottom: 40px;
        }
        .pb-exp-timeline::before {
          content: '';
          position: absolute;
          left: 5px;
          top: 8px;
          bottom: 0;
          width: 2px;
          background: #E8E4D8;
        }
        .pb-exp-group-title {
          font-family: 'Lora', serif;
          font-size: 22px;
          margin-bottom: 24px;
          color: #1A1A1A;
        }
        .pb-exp-entry {
          position: relative;
          margin-bottom: 28px;
          padding-bottom: 28px;
          border-bottom: 1px solid #F0EDE6;
        }
        .pb-exp-entry:last-child {
          border-bottom: none;
          margin-bottom: 0;
          padding-bottom: 0;
        }
        .pb-exp-dot {
          position: absolute;
          left: -27px;
          top: 6px;
          width: 12px;
          height: 12px;
          border-radius: 50%;
          background: #C4502A;
          border: 2px solid #FEFDF9;
          box-shadow: 0 0 0 2px #C4502A;
        }
        .pb-exp-header {
          display: flex;
          justify-content: space-between;
          align-items: baseline;
          margin-bottom: 4px;
        }
        .pb-exp-title {
          font-size: 16px;
          font-weight: 600;
          font-family: 'Lora', serif;
          color: #1A1A1A;
        }
        .pb-exp-period {
          font-size: 13px;
          color: #999;
          flex-shrink: 0;
          margin-left: 12px;
        }
        .pb-exp-subtitle {
          font-size: 14px;
          color: #666;
          margin-bottom: 8px;
        }
        .pb-exp-desc {
          font-size: 14px;
          line-height: 1.7;
          color: #444;
        }
        .pb-exp-edu {
          margin-top: 40px;
        }

        /* About + Skills sidebar */
        .pb-about-layout { display: flex; gap: 48px; }
        .pb-about-main { flex: 1.3; }
        .pb-about-main p { font-size: 15px; line-height: 1.8; color: #333; margin-bottom: 16px; }
        .pb-about-main p:first-child { font-family: 'Lora', serif; font-size: 18px; }
        .pb-looking-for h4 {
          font-family: 'Lora', serif; font-size: 18px; margin: 24px 0 12px;
        }
        .pb-about-sidebar { flex: 1; }
        .pb-about-sidebar h4 { font-size: 14px; font-weight: 600; margin-bottom: 16px; }

        /* Skill tags */
        .pb-skills-group {
          margin-bottom: 20px;
        }
        .pb-skills-category {
          font-size: 12px;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          color: #999;
          margin-bottom: 8px;
        }
        .pb-skills-tags {
          display: flex;
          flex-wrap: wrap;
          gap: 6px;
        }
        .pb-skill-tag {
          display: inline-block;
          padding: 4px 12px;
          font-size: 13px;
          color: #C4502A;
          background: #FDF5F0;
          border: 1px solid #F2D5C8;
          border-radius: 20px;
          line-height: 1.4;
        }

        /* Contact */
        .pb-contact-heading { font-family: 'Lora', serif; font-size: 28px; margin-bottom: 16px; }
        .pb-contact-sub { font-size: 15px; line-height: 1.7; color: #666; margin-bottom: 32px; }
        .pb-contact-email { font-size: 22px; color: #C4502A; text-decoration: none; display: inline-block; margin-bottom: 40px; }
        .pb-contact-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; max-width: 480px; }
        .pb-contact-item { border-top: 1px solid #E8E4D8; padding-top: 12px; }
        .pb-contact-label { font-size: 14px; font-weight: 600; }
        .pb-contact-value { font-size: 13px; color: #999; }
        .pb-contact-value a { color: #C4502A; text-decoration: none; }
        .pb-contact-value a:hover { text-decoration: underline; }

        /* WeChat QR popup */
        .pb-wechat-wrap { position: relative; display: inline-block; cursor: pointer; }
        .pb-wechat-popup { display: none; position: absolute; bottom: 100%; left: 50%; transform: translateX(-50%); margin-bottom: 8px; z-index: 100; background: #FFF; padding: 8px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
        .pb-wechat-wrap:hover .pb-wechat-popup { display: block; }
        .pb-wechat-popup img { width: 150px; height: 150px; border-radius: 4px; }
        .pb-wechat-popup::after { content: ''; position: absolute; top: 100%; left: 50%; transform: translateX(-50%); border: 6px solid transparent; border-top-color: #FFF; }
      `}</style>

      <nav className="personal-nav">
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

      <div className="personal-sections">
      {/* Section 0: Hero */}
      <section className="section" ref={(el) => registerSection(0, el)}>
        <div className="pb-hero-wrap" style={{maxWidth: 800}}>
          <div className="pb-hero-left">
            <h1 className="pb-hero-name">{info.name || 'Wang Fang'}</h1>
            <p className="pb-hero-role">
              {info.target_position || "I help early-stage teams build the things people keep coming back to."}
            </p>
            <div className="pb-hero-badge">
              <span className="pb-hero-dot" />
              <span>{info.city || 'Shanghai'} · Open to opportunities</span>
            </div>
          </div>
          <div className="pb-hero-portrait" />
        </div>
      </section>

      {/* Section 1: About + Skills */}
      <section className="section" ref={(el) => registerSection(1, el)}>
        <div className="section-inner" style={{maxWidth: 800}}>
          <div className="pb-about-layout">
            <div className="pb-about-main">
              <p>{info.self_intro || 'Growth and community professional with 5+ years in product-led growth. I specialize in building communities that drive user retention and activation.'}</p>
              <p>I approach problems with first-principles thinking and a bias toward action. My work combines data analysis with deep empathy for user needs — understanding both the "what" and the "why" behind user behavior.</p>
            </div>
            <div className="pb-about-sidebar">
              <h4>Skills</h4>
              {Object.keys(skills).length > 0 ? (
                Object.entries(skills).map(([category, tagList]) => (
                  <div key={category} className="pb-skills-group">
                    <div className="pb-skills-category">{category}</div>
                    <div className="pb-skills-tags">
                      {(tagList as string[]).map((tag, idx) => (
                        <span key={idx} className="pb-skill-tag">{tag}</span>
                      ))}
                    </div>
                  </div>
                ))
              ) : (
                <p className="pb-body-text">No skills listed</p>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* Section 2: Selected Work */}
      <section className="section" ref={(el) => registerSection(2, el)}>
        <div className="section-inner">
          <h2 className="pb-section-title">Selected work</h2>
          {projects.slice(0, 4).map((p, i) => (
            <div key={i} className="pb-work-entry">
              <div className="pb-work-header">
                <span className="pb-work-name">{p.name}</span>
                <span className="pb-work-year">{p.period || '2024'}</span>
              </div>
              <div className="pb-work-role">{p.role}</div>
              <div className="pb-work-story">{p.description}</div>
              {p.tech_stack && <div className="pb-work-metric">{p.tech_stack}</div>}
              <div className="pb-work-link"><a href="#">→ Learn more</a></div>
            </div>
          ))}
          {projects.length === 0 && (
            <>
              <div className="pb-work-entry">
                <div className="pb-work-header"><span className="pb-work-name">Community Growth Program</span><span className="pb-work-year">2024</span></div>
                <div className="pb-work-role">Growth Lead</div>
                <div className="pb-work-story">Built a referral program from scratch that drove 300+ qualified leads in 3 months</div>
                <div className="pb-work-metric">30% of new sign-ups came from referrals</div>
              </div>
              <div className="pb-work-entry">
                <div className="pb-work-header"><span className="pb-work-name">User Retention Revamp</span><span className="pb-work-year">2023</span></div>
                <div className="pb-work-role">Product Growth Manager</div>
                <div className="pb-work-story">Redesigned the onboarding flow and implemented behavioral email triggers</div>
                <div className="pb-work-metric">D30 retention improved from 22% to 41%</div>
              </div>
            </>
          )}
        </div>
      </section>

      {/* Section 3: Experience (Work History + Education) */}
      <section className="section" ref={(el) => registerSection(3, el)}>
        <div className="section-inner" style={{maxWidth: 800}}>
          <h2 className="pb-section-title">Experience</h2>

          {work.length > 0 && (
            <div className="pb-exp-timeline">
              <div className="pb-exp-group-title">Work</div>
              {work.map((w, i) => (
                <div key={i} className="pb-exp-entry">
                  <div className="pb-exp-dot" />
                  <div className="pb-exp-header">
                    <span className="pb-exp-title">{w.position}{w.company ? ` · ${w.company}` : ''}</span>
                    {w.period && <span className="pb-exp-period">{w.period}</span>}
                  </div>
                  {w.description && <div className="pb-exp-desc">{w.description}</div>}
                </div>
              ))}
            </div>
          )}

          {educations.length > 0 && (
            <div className="pb-exp-timeline pb-exp-edu">
              <div className="pb-exp-group-title">Education</div>
              {educations.map((e, i) => (
                <div key={i} className="pb-exp-entry">
                  <div className="pb-exp-dot" />
                  <div className="pb-exp-header">
                    <span className="pb-exp-title">{e.school}</span>
                    {e.period && <span className="pb-exp-period">{e.period}</span>}
                  </div>
                  {(e.degree || e.major) && (
                    <div className="pb-exp-subtitle">
                      {[e.degree, e.major].filter(Boolean).join(' · ')}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {work.length === 0 && educations.length === 0 && (
            <p className="pb-body-text">No experience data available yet.</p>
          )}
        </div>
      </section>



      {/* Section 4: Contact */}
      <section className="section" ref={(el) => registerSection(4, el)}>
        <div className="section-inner" style={{textAlign: 'left'}}>
          <h2 className="pb-contact-heading">Find me</h2>
          <p className="pb-contact-sub">
            I'd love to hear from you — whether it's a role, a project, or just a conversation.
          </p>
          <a className="pb-contact-email" href={`mailto:${info.email || 'wangfang@email.com'}`}>
            {info.email || 'wangfang@email.com'}
          </a>
          <div className="pb-contact-grid">
            {info.phone && (
              <div className="pb-contact-item">
                <div className="pb-contact-label">Phone</div>
                <div className="pb-contact-value">
                  <a href={`tel:${info.phone}`}>{info.phone}</a>
                </div>
              </div>
            )}
            {info.github && (
              <div className="pb-contact-item">
                <div className="pb-contact-label">GitHub</div>
                <div className="pb-contact-value">
                  <a href={info.github.startsWith('http') ? info.github : `https://github.com/${info.github}`} target="_blank" rel="noopener noreferrer">
                    {info.github}
                  </a>
                </div>
              </div>
            )}
            <div className="pb-contact-item">
              <div className="pb-contact-label">WeChat</div>
              <div className="pb-contact-value">
                {info.wechat_qr ? (
                  <span className="pb-wechat-wrap">
                    <span>{info.wechat_name || '微信'}</span>
                    <span className="pb-wechat-popup">
                      <img src={info.wechat_qr} alt="WeChat QR Code" />
                    </span>
                  </span>
                ) : (
                  <span>{info.wechat_name || '微信'}</span>
                )}
              </div>
            </div>
          </div>
        </div>
      </section>
      </div>
    </div>
  );
};
