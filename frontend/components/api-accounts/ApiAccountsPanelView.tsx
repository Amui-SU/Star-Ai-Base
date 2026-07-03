import type { Dispatch, SetStateAction } from "react";

import type { ApiAccount } from "@/lib/api";
import type { ProviderPreset } from "@/lib/providers";
import ApiAccountForm from "@/components/api-accounts/ApiAccountForm";
import ApiAccountsList from "@/components/api-accounts/ApiAccountsList";

interface ApiAccountFormState {
  accountId: number | null;
  provider: string;
  displayName: string;
  apiKey: string;
  baseUrl: string;
  model: string;
  enabled: boolean;
  isDefault: boolean;
}

interface ApiAccountsPanelViewProps {
  accounts: ApiAccount[];
  busyId: number | null;
  editing: boolean;
  error: string;
  form: ApiAccountFormState;
  isSearchProvider: boolean;
  loading: boolean;
  notice: string;
  saving: boolean;
  selectedPreset: ProviderPreset;
  setForm: Dispatch<SetStateAction<ApiAccountFormState>>;
  onClose: () => void;
  onEditAccount: (account: ApiAccount) => void;
  onRefreshAccounts: () => void;
  onRemoveAccount: (account: ApiAccount) => void;
  onResetForm: () => void;
  onSaveAccount: () => void;
  onSelectProvider: (provider: string) => void;
  onSetDefault: (account: ApiAccount) => void;
  onValidateAccount: (account: ApiAccount) => void;
}

export default function ApiAccountsPanelView({
  accounts,
  busyId,
  editing,
  error,
  form,
  isSearchProvider,
  loading,
  notice,
  saving,
  selectedPreset,
  setForm,
  onClose,
  onEditAccount,
  onRefreshAccounts,
  onRemoveAccount,
  onResetForm,
  onSaveAccount,
  onSelectProvider,
  onSetDefault,
  onValidateAccount,
}: ApiAccountsPanelViewProps) {
  return (
    <>
      <div className="provider-config-head">
        <div className="provider-config-title-block">
          <div className="provider-config-title">AI 服务密钥</div>
          <div className="provider-config-subtitle">
            每个用户独立保存第三方模型或搜索服务 Key，Key
            只写入后端，不会在前端回显。
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

      <div className="api-accounts-layout">
        <ApiAccountsList
          accounts={accounts}
          busyId={busyId}
          formAccountId={form.accountId}
          loading={loading}
          onEdit={onEditAccount}
          onRefresh={onRefreshAccounts}
          onRemove={onRemoveAccount}
          onSetDefault={onSetDefault}
          onValidate={onValidateAccount}
        />
        <ApiAccountForm
          editing={editing}
          error={error}
          form={form}
          isSearchProvider={isSearchProvider}
          notice={notice}
          saving={saving}
          selectedPreset={selectedPreset}
          setForm={setForm}
          onClose={onClose}
          onResetForm={onResetForm}
          onSave={onSaveAccount}
          onSelectProvider={onSelectProvider}
        />
      </div>
    </>
  );
}
