import React from 'react';

interface ThemeTabProps {
  currentTheme: string;
  onChange: (theme: string) => void;
}

export const ThemeTab: React.FC<ThemeTabProps> = ({ currentTheme, onChange }) => {
  const themes = [
    { id: 'editorial', name: '杂志风', desc: 'Editorial' },
    { id: 'developer', name: '工程师风', desc: 'Developer' },
    { id: 'creative', name: '创意人风', desc: 'Creative' },
    { id: 'personal', name: '个人品牌风', desc: 'Personal Brand' },
  ];

  return (
    <div className="theme-tabs">
      {themes.map((theme) => (
        <button
          key={theme.id}
          className={`theme-tab ${currentTheme === theme.id ? 'active' : ''}`}
          onClick={() => onChange(theme.id)}
        >
          <span className="theme-name">{theme.name}</span>
          <span className="theme-desc">{theme.desc}</span>
        </button>
      ))}
    </div>
  );
};
