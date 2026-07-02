import React from 'react';

interface Block {
  id: string;
  name: string;
  visible: boolean;
}

interface BlockEditorProps {
  blocks: Block[];
  onReorder: (fromIndex: number, toIndex: number) => void;
  onToggleVisibility: (id: string) => void;
}

export const BlockEditor: React.FC<BlockEditorProps> = ({ blocks, onReorder, onToggleVisibility }) => {
  const handleDragStart = (e: React.DragEvent, index: number) => {
    e.dataTransfer.setData('index', String(index));
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const handleDrop = (e: React.DragEvent, toIndex: number) => {
    const fromIndex = Number(e.dataTransfer.getData('index'));
    if (fromIndex !== toIndex) {
      onReorder(fromIndex, toIndex);
    }
  };

  return (
    <div className="block-editor">
      <h3>区块管理</h3>
      <div className="block-list">
        {blocks.map((block, index) => (
          <div
            key={block.id}
            className={`block-item ${!block.visible ? 'hidden' : ''}`}
            draggable
            onDragStart={(e) => handleDragStart(e, index)}
            onDragOver={handleDragOver}
            onDrop={(e) => handleDrop(e, index)}
          >
            <span className="drag-handle">⋮⋮</span>
            <span className="block-name">{block.name}</span>
            <button
              className={`visibility-btn ${block.visible ? 'visible' : 'hidden'}`}
              onClick={() => onToggleVisibility(block.id)}
            >
              {block.visible ? '隐藏' : '显示'}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
};