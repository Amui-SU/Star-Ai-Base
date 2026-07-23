import type { ReactNode } from "react";

export type ApiCredentialEditorTab = "basic" | "request";

type ApiCredentialEditorShellProps = {
  title: string;
  subtitle?: string;
  activeTab: ApiCredentialEditorTab;
  showRequestTab: boolean;
  saving: boolean;
  onBack?: () => void;
  onClose: () => void;
  onTabChange: (tab: ApiCredentialEditorTab) => void;
  basicContent: ReactNode;
  requestContent?: ReactNode;
  footer: ReactNode;
};

const BASIC_PANEL_ID = "api-credential-basic-panel";
const REQUEST_PANEL_ID = "api-credential-request-panel";

export function ApiCredentialEditorShell({
  title,
  subtitle,
  activeTab,
  showRequestTab,
  saving,
  onBack,
  onClose,
  onTabChange,
  basicContent,
  requestContent,
  footer,
}: ApiCredentialEditorShellProps) {
  const showingRequest = showRequestTab && activeTab === "request";

  return (
    <div className="api-credential-editor">
      <header className="api-credential-editor-header">
        <div className="api-credential-editor-heading">
          {onBack ? (
            <button
              className="api-credential-editor-back"
              type="button"
              aria-label="返回密钥列表"
              disabled={saving}
              onClick={onBack}
            >
              返回密钥列表
            </button>
          ) : null}
          <h2>{title}</h2>
          {subtitle ? <p>{subtitle}</p> : null}
        </div>
        <button
          className="api-credential-editor-close"
          type="button"
          aria-label="关闭"
          disabled={saving}
          onClick={onClose}
        >
          ×
        </button>
      </header>

      <div className="api-credential-editor-tabs" role="tablist">
        <button
          id="api-credential-basic-tab"
          type="button"
          role="tab"
          aria-selected={!showingRequest}
          aria-controls={BASIC_PANEL_ID}
          onClick={() => onTabChange("basic")}
        >
          基础配置
        </button>
        {showRequestTab ? (
          <button
            id="api-credential-request-tab"
            type="button"
            role="tab"
            aria-selected={showingRequest}
            aria-controls={REQUEST_PANEL_ID}
            onClick={() => onTabChange("request")}
          >
            请求配置
          </button>
        ) : null}
      </div>

      <div className="api-credential-editor-body">
        <div
          id={showingRequest ? REQUEST_PANEL_ID : BASIC_PANEL_ID}
          role="tabpanel"
          aria-labelledby={
            showingRequest
              ? "api-credential-request-tab"
              : "api-credential-basic-tab"
          }
        >
          {showingRequest ? requestContent : basicContent}
        </div>
      </div>

      <footer className="api-credential-editor-footer">{footer}</footer>
    </div>
  );
}
