import React from 'react';
import type { StyleOption } from '../../../api/portfolio';

interface StyleSelectorProps {
  styles: StyleOption[];
  selected: string;
  onChange: (style: string) => void;
}

const renderPreview = (styleId: string) => {
  switch (styleId) {
    case 'editorial':
      return (
        <div style={{ width: '100%', height: 80, borderRadius: 8, background: '#FAFAF8', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', border: '1px solid #E8E8E6' }}>
          <span style={{ fontFamily: 'Georgia, serif', fontSize: 24, color: '#333' }}>Aa</span>
          <div style={{ width: 40, height: 3, background: '#C4502A', borderRadius: 2, marginTop: 6 }} />
        </div>
      );
    case 'developer':
      return (
        <div style={{ width: '100%', height: 80, borderRadius: 8, background: '#0A0A0A', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
          <span style={{ fontFamily: 'monospace', fontSize: 20, color: '#3DD68C' }}>{'>_'}</span>
          <div style={{ width: 40, height: 3, background: '#3DD68C', borderRadius: 2, marginTop: 6 }} />
        </div>
      );
    case 'creative':
      return (
        <div style={{ width: '100%', height: 80, borderRadius: 8, display: 'flex', overflow: 'hidden', border: '1px solid #E8E8E6' }}>
          <div style={{ flex: 1, background: '#0F0F0F', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <span style={{ fontFamily: 'sans-serif', fontSize: 16, color: '#F2F2F0', fontWeight: 700 }}>D</span>
          </div>
          <div style={{ flex: 1, background: '#F2F2F0', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <span style={{ fontFamily: 'sans-serif', fontSize: 16, color: '#0F0F0F', fontWeight: 700 }}>M</span>
          </div>
        </div>
      );
    case 'personal':
      return (
        <div style={{ width: '100%', height: 80, borderRadius: 8, background: '#FEFDF9', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', border: '1px solid #E8E8E6' }}>
          <span style={{ fontFamily: 'Georgia, serif', fontSize: 22, color: '#333', fontWeight: 700 }}>PB</span>
          <div style={{ width: 40, height: 3, background: '#C4502A', borderRadius: 2, marginTop: 6 }} />
        </div>
      );
    default:
      return <div style={{ width: '100%', height: 80, borderRadius: 8, background: '#f0f0f0' }} />;
  }
};

export const StyleSelector: React.FC<StyleSelectorProps> = ({ styles, selected, onChange }) => {
  return (
    <div className="style-selector">
      <h3>风格选择</h3>
      <div className="style-grid">
        {styles.map((style) => (
          <button
            key={style.id}
            className={`style-card ${selected === style.id ? 'selected' : ''}`}
            onClick={() => onChange(style.id)}
          >
            {renderPreview(style.id)}
            <div className="style-info">
              <span className="style-name">{style.name}</span>
              <span className="style-desc">{style.description}</span>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
};