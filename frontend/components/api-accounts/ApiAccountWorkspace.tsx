"use client";

import Image from "next/image";
import type { ApiAccount } from "@/lib/api";
import ApiAccountConnectionSection from "./ApiAccountConnectionSection";
import ApiAccountIdentitySection from "./ApiAccountIdentitySection";
import ApiAccountModelSection from "./ApiAccountModelSection";
import ApiAccountRequestSection from "./ApiAccountRequestSection";
import ApiAccountSectionNav, {
  ApiAccountSection,
} from "./ApiAccountSectionNav";
import AdvancedConfigEditor from "./AdvancedConfigEditor";
import type { ThinkingTemplates } from "./types";
import { useApiAccountWorkspace } from "./useApiAccountWorkspace";

interface Props {
  account: ApiAccount | null;
  templates: ThinkingTemplates;
  onBack: () => void;
  onClose: () => void;
  onSaved: () => void;
}

export default function ApiAccountWorkspace(props: Props) {
  const workspace = useApiAccountWorkspace(props);
  const sections = workspace.preset.sections;
  const title = workspace.editing ? "编辑 API 密钥" : "添加 API 密钥";
  return (
    <div
      className="api-account-workspace"
      role="dialog"
      aria-modal="true"
      aria-label={title}
    >
      <header className="api-account-workspace-header">
        <button
          type="button"
          className="api-account-workspace-back"
          aria-label="返回密钥列表"
          disabled={workspace.saving}
          onClick={workspace.back}
        >
          ←
        </button>
        {workspace.preset.logo ? (
          <Image src={workspace.preset.logo} alt="" width={36} height={36} />
        ) : (
          <span className="api-account-provider-mark">
            {workspace.preset.label.slice(0, 1)}
          </span>
        )}
        <div className="api-account-workspace-title">
          <h1>{workspace.draft.displayName || title}</h1>
          <span>
            {workspace.saving
              ? "保存中"
              : workspace.dirty
                ? "未保存"
                : "已保存"}
          </span>
        </div>
        <div className="api-account-workspace-actions">
          <button
            type="button"
            className="btn btn-outline"
            disabled={workspace.saving || workspace.validating}
            onClick={() => void workspace.validateDraft()}
          >
            {workspace.validating ? "测试中..." : "测试连接"}
          </button>
          <button
            type="button"
            className="btn btn-primary"
            disabled={workspace.saving || workspace.validating}
            onClick={() => void workspace.save()}
          >
            {workspace.saving ? "保存中..." : "保存配置"}
          </button>
          <button
            type="button"
            className="api-account-workspace-close"
            aria-label="关闭密钥管理"
            disabled={workspace.saving}
            onClick={workspace.close}
          >
            ×
          </button>
        </div>
      </header>
      <div className="api-account-workspace-layout">
        <ApiAccountSectionNav
          sections={sections}
          active={workspace.activeSection}
          onSelect={workspace.setActiveSection}
        />
        <main className="api-account-workspace-scroll">
          <div className="api-account-workspace-content">
            {workspace.error ? (
              <div className="api-account-message error" role="alert">
                {workspace.error}
              </div>
            ) : null}
            {workspace.validation ? (
              <div
                className={`api-account-validation ${workspace.validation.status}`}
                role="status"
              >
                {workspace.validation.http_status
                  ? `${workspace.validation.http_status} · `
                  : ""}
                {workspace.validation.latency_ms} ms ·{" "}
                {workspace.validation.message}
              </div>
            ) : null}
            <ApiAccountSection
              section="identity"
              title="基本信息"
              open={
                !workspace.isMobile || workspace.activeSection === "identity"
              }
              onOpen={() => workspace.openMobileSection("identity")}
            >
              <ApiAccountIdentitySection
                draft={workspace.draft}
                editing={workspace.editing}
                saving={workspace.saving}
                update={workspace.updateDraft}
                selectProvider={workspace.selectProvider}
              />
            </ApiAccountSection>
            <ApiAccountSection
              section="connection"
              title="连接设置"
              open={
                !workspace.isMobile || workspace.activeSection === "connection"
              }
              onOpen={() => workspace.openMobileSection("connection")}
            >
              <ApiAccountConnectionSection
                draft={workspace.draft}
                preset={workspace.preset}
                editing={workspace.editing}
                update={workspace.updateDraft}
              />
            </ApiAccountSection>
            {workspace.preset.kind === "llm" ? (
              <>
                <ApiAccountSection
                  section="models"
                  title="模型映射"
                  open={
                    !workspace.isMobile || workspace.activeSection === "models"
                  }
                  onOpen={() => workspace.openMobileSection("models")}
                >
                  <ApiAccountModelSection
                    draft={workspace.draft}
                    update={workspace.updateDraft}
                    updateAdvanced={workspace.updateAdvanced}
                  />
                </ApiAccountSection>
                <ApiAccountSection
                  section="request"
                  title="请求配置"
                  open={
                    !workspace.isMobile || workspace.activeSection === "request"
                  }
                  onOpen={() => workspace.openMobileSection("request")}
                >
                  <ApiAccountRequestSection
                    draft={workspace.draft}
                    template={props.templates[workspace.draft.provider] ?? {}}
                    update={workspace.updateDraft}
                    updateAdvanced={workspace.updateAdvanced}
                  />
                </ApiAccountSection>
                <ApiAccountSection
                  section="json"
                  title="配置 JSON"
                  open={
                    !workspace.isMobile || workspace.activeSection === "json"
                  }
                  onOpen={() => workspace.openMobileSection("json")}
                >
                  <AdvancedConfigEditor
                    raw={workspace.rawJson}
                    error={workspace.jsonError}
                    onRawChange={workspace.setRawJson}
                    onApply={workspace.applyJson}
                  />
                </ApiAccountSection>
              </>
            ) : null}
          </div>
        </main>
      </div>
      <footer className="api-account-mobile-actions">
        <button
          type="button"
          className="btn btn-outline"
          disabled={workspace.saving}
          onClick={workspace.back}
        >
          取消
        </button>
        <button
          type="button"
          className="btn btn-outline"
          disabled={workspace.saving || workspace.validating}
          onClick={() => void workspace.validateDraft()}
        >
          测试
        </button>
        <button
          type="button"
          className="btn btn-primary"
          disabled={workspace.saving || workspace.validating}
          onClick={() => void workspace.save()}
        >
          保存
        </button>
      </footer>
    </div>
  );
}
