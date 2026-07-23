"use client";

import ApiAccountsPanelView from "@/components/api-accounts/ApiAccountsPanelView";
import { useApiAccountsPanel } from "@/components/api-accounts/useApiAccountsPanel";
import ModalShell from "@/components/ui/ModalShell";

interface Props {
  open: boolean;
  onClose: () => void;
  onChanged?: () => void;
}

export default function ApiAccountsPanel({ open, onClose, onChanged }: Props) {
  const {
    accounts,
    activeTab,
    busyId,
    createAccount,
    editAccount,
    editing,
    error,
    form,
    isSearchProvider,
    loadAccounts,
    loading,
    notice,
    removeAccount,
    returnToList,
    saveAccount,
    saving,
    selectedPreset,
    selectedTemplate,
    selectProvider,
    setDefault,
    setForm,
    setActiveTab,
    setThinkingError,
    thinkingError,
    validateAccount,
    view,
  } = useApiAccountsPanel({ open, onChanged });

  if (!open) return null;

  return (
    <ModalShell cardClassName="api-accounts-panel" onClose={onClose}>
      <ApiAccountsPanelView
        accounts={accounts}
        activeTab={activeTab}
        busyId={busyId}
        editing={editing}
        error={error}
        form={form}
        isSearchProvider={isSearchProvider}
        loading={loading}
        notice={notice}
        saving={saving}
        selectedPreset={selectedPreset}
        selectedTemplate={selectedTemplate}
        thinkingError={thinkingError}
        view={view}
        setForm={setForm}
        onClose={onClose}
        onCreateAccount={createAccount}
        onEditAccount={editAccount}
        onRefreshAccounts={() => void loadAccounts()}
        onRemoveAccount={(account) => void removeAccount(account)}
        onReturnToList={returnToList}
        onSaveAccount={() => void saveAccount()}
        onSelectProvider={selectProvider}
        onSetDefault={(account) => void setDefault(account)}
        onTabChange={setActiveTab}
        onThinkingErrorChange={setThinkingError}
        onValidateAccount={(account) => void validateAccount(account)}
      />
    </ModalShell>
  );
}
