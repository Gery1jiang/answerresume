import React from 'react';

export interface NavSection {
  id: string;
  label: string;
}

interface PortfolioNavProps {
  sections: NavSection[];
  currentSection: number;
  onNavigate: (index: number) => void;
  className?: string;
  style?: React.CSSProperties;
}

export const PortfolioNav: React.FC<PortfolioNavProps> = ({
  sections,
  currentSection,
  onNavigate,
  className = '',
  style,
}) => {
  return (
    <nav className={`portfolio-top-nav ${className}`} style={style}>
      {sections.map((s, i) => (
        <button
          key={s.id}
          className={`nav-btn ${i === currentSection ? 'active' : ''}`}
          onClick={() => onNavigate(i)}
        >
          {s.label}
        </button>
      ))}
    </nav>
  );
};
