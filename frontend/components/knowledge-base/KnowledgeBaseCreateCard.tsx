interface KnowledgeBaseCreateCardProps {
  disabled: boolean;
  newName: string;
  newDesc: string;
  onNameChange: (value: string) => void;
  onDescChange: (value: string) => void;
  onCreate: () => void;
}

export function KnowledgeBaseCreateCard({
  disabled,
  newName,
  newDesc,
  onNameChange,
  onDescChange,
  onCreate,
}: KnowledgeBaseCreateCardProps) {
  return (
    <div className="knowledge-create-card animate-[fadeIn_200ms_ease-out]">
      <div className="knowledge-create-head">
        <div>
          <div className="knowledge-create-title">新建知识库</div>
          <div className="knowledge-create-copy">
            为收藏夹资料准备一个独立的提问空间
          </div>
        </div>
      </div>
      <input
        type="text"
        value={newName}
        onChange={(event) => onNameChange(event.target.value)}
        placeholder="知识库名称"
        className="knowledge-create-input"
        onKeyDown={(event) => event.key === "Enter" && onCreate()}
      />
      <input
        type="text"
        value={newDesc}
        onChange={(event) => onDescChange(event.target.value)}
        placeholder="描述（可选）"
        className="knowledge-create-input"
        onKeyDown={(event) => event.key === "Enter" && onCreate()}
      />
      <button
        type="button"
        onClick={onCreate}
        disabled={disabled || !newName.trim()}
        className="knowledge-create-submit"
      >
        创建知识库
      </button>
    </div>
  );
}
