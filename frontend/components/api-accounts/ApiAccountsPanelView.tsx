import type { Dispatch, SetStateAction } from "react";

import type { ApiAccount } from "@/lib/api";
import type { ProviderPreset } from "@/lib/providers";
import type { ThinkingConfig } from "@/lib/thinkingConfig";
import ApiAccountForm from "./ApiAccountForm";
import ApiAccountsList from "./ApiAccountsList";
import type {
  ApiAccountEditorTab,
  ApiAccountFormState,
  ApiAccountsPanelView as PanelView,
} from "./types";

interface ApiAccountsPanelViewProps {
  accounts: ApiAccount[];
  activeTab: ApiAccountEditorTab;
  busyId: number | null;
  editing: boolean;
  error: string;
  form: ApiAccountFormState;
  isSearchProvider: boolean;
  loading: boolean;
  notice: string;
  saving: boolean;
  selectedPreset: ProviderPreset;
  selectedTemplate: ThinkingConfig;
  thinkingError: string;
  view: PanelView;
  setForm: Dispatch<SetStateAction<ApiAccountFormState>>;
  onClose: () => void;
  onCreateAccount: () => void;
  onEditAccount: (account: ApiAccount) => void;
  onRefreshAccounts: () => void;
  onRemoveAccount: (account: ApiAccount) => void;
  onReturnToList: () => void;
  onSaveAccount: () => void;
  onSelectProvider: (provider: string) => void;
  onSetDefault: (account: ApiAccount) => void;
  onTabChange: (tab: ApiAccountEditorTab) => void;
  onThinkingErrorChange: (error: string) => void;
  onValidateAccount: (account: ApiAccount) => void;
}

export default function ApiAccountsPanelView({
  accounts,
  activeTab,
  busyId,
  editing,
  error,
  form,
  isSearchProvider,
  loading,
  notice,
  saving,
  selectedPreset,
  selectedTemplate,
  thinkingError,
  view,
  setForm,
  onClose,
  onCreateAccount,
  onEditAccount,
  onRefreshAccounts,
  onRemoveAccount,
  onReturnToList,
  onSaveAccount,
  onSelectProvider,
  onSetDefault,
  onTabChange,
  onThinkingErrorChange,
  onValidateAccount,
}: ApiAccountsPanelViewProps) {
  if (view !== "list") {
    return (
      <ApiAccountForm
        activeTab={activeTab}
        editing={editing}
        error={error}
        form={form}
        isSearchProvider={isSearchProvider}
        saving={saving}
        selectedPreset={selectedPreset}
        selectedTemplate={selectedTemplate}
        thinkingError={thinkingError}
        setForm={setForm}
        onBack={onReturnToList}
        onClose={onClose}
        onSave={onSaveAccount}
        onSelectProvider={onSelectProvider}
        onTabChange={onTabChange}
        onThinkingErrorChange={onThinkingErrorChange}
      />
    );
  }

  return (
    <div className="api-accounts-list-view">
      <div className="provider-config-head">
        <div className="provider-config-title-block">
          <div className="provider-config-title">AI 服务密钥</div>
          <div className="provider-config-subtitle">
            管理个人模型与搜索服务凭据，API Key 不会在前端回显。
          </div>
        </div>
        <button
          type="button"
          className="provider-config-close"
          onClick={onClose}
          aria-label="关闭 AI 服务密钥管理"
        >
          x
        </button>
      </div>

      {notice || error ? (
        <div
          className={`api-account-message ${error ? "error" : ""}`}
          role="status"
        >
          {error || notice}
        </div>
      ) : null}

      <ApiAccountsList
        accounts={accounts}
        busyId={busyId}
        loading={loading}
        onCreate={onCreateAccount}
        onEdit={onEditAccount}
        onRefresh={onRefreshAccounts}
        onRemove={onRemoveAccount}
        onSetDefault={onSetDefault}
        onValidate={onValidateAccount}
      />
    </div>
  );
}
