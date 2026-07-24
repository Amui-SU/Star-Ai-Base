import type { ApiAccountSection } from "./types";

const labels: Record<ApiAccountSection, string> = {
  identity: "基本信息",
  connection: "连接设置",
  models: "模型映射",
  request: "请求配置",
  json: "配置 JSON",
};

export default function ApiAccountSectionNav({
  sections,
  active,
  onSelect,
}: {
  sections: ApiAccountSection[];
  active: ApiAccountSection;
  onSelect: (section: ApiAccountSection) => void;
}) {
  return (
    <nav className="api-account-section-nav" aria-label="配置分区">
      {sections.map((section) => (
        <button
          type="button"
          key={section}
          className={active === section ? "active" : ""}
          onClick={() => {
            onSelect(section);
            const element = document.getElementById(
              `api-account-section-${section}`,
            );
            element?.scrollIntoView?.({ behavior: "smooth" });
            element?.querySelector("summary")?.focus();
          }}
        >
          {labels[section]}
        </button>
      ))}
    </nav>
  );
}

export function ApiAccountSection({
  section,
  title,
  open,
  onOpen,
  children,
}: {
  section: ApiAccountSection;
  title: string;
  open: boolean;
  onOpen: () => void;
  children: React.ReactNode;
}) {
  return (
    <details
      id={`api-account-section-${section}`}
      className="api-account-workspace-section"
      open={open}
      onToggle={(event) => {
        if (event.currentTarget.open) onOpen();
      }}
    >
      <summary tabIndex={-1}>{title}</summary>
      <div className="api-account-section-body">{children}</div>
    </details>
  );
}
