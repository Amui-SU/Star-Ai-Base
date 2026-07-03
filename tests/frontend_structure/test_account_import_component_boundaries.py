from .helpers import get_project_root


def test_api_accounts_panel_uses_state_hook():
    project_root = get_project_root()
    panel_source = (
        project_root / "frontend" / "components" / "ApiAccountsPanel.tsx"
    ).read_text(encoding="utf-8")
    hook_file = (
        project_root
        / "frontend"
        / "components"
        / "api-accounts"
        / "useApiAccountsPanel.ts"
    )

    assert hook_file.exists()
    hook_source = hook_file.read_text(encoding="utf-8")
    assert "export function useApiAccountsPanel" in hook_source
    assert "@/components/api-accounts/useApiAccountsPanel" in panel_source
    assert "apiAccountApi." not in panel_source
    assert "const loadAccounts" not in panel_source
    assert "const saveAccount" not in panel_source
    assert "const setDefault" not in panel_source
    assert "const validateAccount" not in panel_source
    assert "const removeAccount" not in panel_source
    assert "const selectProvider" not in panel_source
    assert "const editAccount" not in panel_source
    assert "const resetForm" not in panel_source


def test_api_accounts_panel_view_is_extracted():
    project_root = get_project_root()
    panel_source = (
        project_root / "frontend" / "components" / "ApiAccountsPanel.tsx"
    ).read_text(encoding="utf-8")
    view = (
        project_root
        / "frontend"
        / "components"
        / "api-accounts"
        / "ApiAccountsPanelView.tsx"
    )
    account_list = (
        project_root
        / "frontend"
        / "components"
        / "api-accounts"
        / "ApiAccountsList.tsx"
    )
    account_form = (
        project_root / "frontend" / "components" / "api-accounts" / "ApiAccountForm.tsx"
    )

    assert view.exists()
    assert account_list.exists()
    assert account_form.exists()
    assert "@/components/api-accounts/ApiAccountsPanelView" in panel_source
    assert "PROVIDER_PRESETS" not in panel_source
    assert "api-accounts-layout" not in panel_source
    assert "api-accounts-list" not in panel_source
    assert "api-account-form" not in panel_source
    assert "api-account-row" not in panel_source
    assert "api-account-field" not in panel_source


def test_common_modals_use_shared_shell():
    project_root = get_project_root()
    modal_shell = project_root / "frontend" / "components" / "ui" / "ModalShell.tsx"

    assert modal_shell.exists()
    for relative_path in [
        "frontend/components/AdminUsersPanel.tsx",
        "frontend/components/ApiAccountsPanel.tsx",
        "frontend/components/ImportModal.tsx",
        "frontend/components/LocalConnectionSettings.tsx",
        "frontend/components/OrganizePreviewModal.tsx",
        "frontend/components/user-menu/UserMenuLanQrModal.tsx",
        "frontend/components/chat/ModelConfigModal.tsx",
        "frontend/components/chat/WebSearchConfigModal.tsx",
    ]:
        source = (project_root / relative_path).read_text(encoding="utf-8")
        assert "@/components/ui/ModalShell" in source
        assert 'className="modal-backdrop' not in source


def test_import_modal_uses_state_hook():
    project_root = get_project_root()
    modal_source = (
        project_root / "frontend" / "components" / "ImportModal.tsx"
    ).read_text(encoding="utf-8")
    hook_file = (
        project_root / "frontend" / "components" / "import-modal" / "useImportModal.ts"
    )

    assert hook_file.exists()
    hook_source = hook_file.read_text(encoding="utf-8")
    assert "export function useImportModal" in hook_source
    assert "@/components/import-modal/useImportModal" in modal_source
    assert "importApi." not in modal_source
    assert "sourceBindingApi." not in modal_source
    assert "const getQR" not in modal_source
    assert "const submitUrl" not in modal_source
    assert "const submitLocalVideo" not in modal_source
    assert "MAX_QR_POLL_ATTEMPTS" not in modal_source
    assert "setInterval(" not in modal_source
    assert "clearInterval(" not in modal_source


def test_user_menu_state_and_qr_modal_are_extracted():
    project_root = get_project_root()
    user_menu = (project_root / "frontend" / "components" / "UserMenu.tsx").read_text(
        encoding="utf-8"
    )

    for relative_path in [
        "frontend/components/user-menu/useUserMenuState.ts",
        "frontend/components/user-menu/UserMenuLanQrModal.tsx",
    ]:
        assert (project_root / relative_path).exists()

    assert "@/components/user-menu/useUserMenuState" in user_menu
    assert "@/components/user-menu/UserMenuLanQrModal" in user_menu
    assert "localConnectionApi." not in user_menu
    assert "systemAuthApi." not in user_menu
    assert "ModalShell" not in user_menu
    assert "local-connection-qr-card" not in user_menu
    assert "const saveDisplayName" not in user_menu
