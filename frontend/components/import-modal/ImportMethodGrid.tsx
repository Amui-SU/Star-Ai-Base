import type { ImportMethod } from "@/lib/api";

interface ImportMethodGridProps {
  methods: ImportMethod[];
  onOpenMethod: (method: ImportMethod) => void;
}

export default function ImportMethodGrid({
  methods,
  onOpenMethod,
}: ImportMethodGridProps) {
  return (
    <div className="import-method-grid">
      {methods.map((method) => (
        <button
          key={method.id}
          type="button"
          className={`import-method-card ${
            method.status !== "available" ? "disabled" : ""
          }`}
          onClick={() => onOpenMethod(method)}
          disabled={
            method.status !== "available" && method.id !== "bilibili_favorites"
          }
        >
          <span className="import-method-kicker">
            {method.level === 2 ? "二级绑定" : "直接导入"}
          </span>
          <span className="import-method-title">{method.label}</span>
          <span className="import-method-copy">{method.description}</span>
          {method.status !== "available" && (
            <span className="import-method-status">待接入</span>
          )}
        </button>
      ))}
    </div>
  );
}
