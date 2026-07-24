import type { ApiAccount } from "@/lib/api";
import ApiAccountsList from "./ApiAccountsList";

interface Props {
  accounts: ApiAccount[];
  busyId: number | null;
  error: string;
  loading: boolean;
  notice: string;
  onClose: () => void;
  onCreateAccount: () => void;
  onEditAccount: (account: ApiAccount) => void;
  onRefreshAccounts: () => void;
  onRemoveAccount: (account: ApiAccount) => void;
  onSetDefault: (account: ApiAccount) => void;
  onValidateAccount: (account: ApiAccount) => void;
}

export default function ApiAccountsPanelView(props: Props) {
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
          onClick={props.onClose}
          aria-label="关闭 AI 服务密钥管理"
        >
          ×
        </button>
      </div>
      {props.notice || props.error ? (
        <div
          className={`api-account-message ${props.error ? "error" : ""}`}
          role="status"
        >
          {props.error || props.notice}
        </div>
      ) : null}
      <ApiAccountsList
        accounts={props.accounts}
        busyId={props.busyId}
        loading={props.loading}
        onCreate={props.onCreateAccount}
        onEdit={props.onEditAccount}
        onRefresh={props.onRefreshAccounts}
        onRemove={props.onRemoveAccount}
        onSetDefault={props.onSetDefault}
        onValidate={props.onValidateAccount}
      />
    </div>
  );
}
