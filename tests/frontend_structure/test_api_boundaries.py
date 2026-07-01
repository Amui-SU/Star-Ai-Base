from .helpers import get_project_root


def test_frontend_api_delegates_client_and_system_auth_boundaries():
    project_root = get_project_root()
    api_file = project_root / "frontend" / "lib" / "api.ts"
    api_source = api_file.read_text(encoding="utf-8")

    for relative_path in [
        "frontend/lib/api/client.ts",
        "frontend/lib/api/systemAuth.ts",
        "frontend/lib/api/systemAuthTypes.ts",
    ]:
        assert (project_root / relative_path).exists()

    assert 'from "./api/client"' in api_source
    assert 'from "./api/systemAuth"' in api_source
    assert 'from "./api/systemAuthTypes"' in api_source
    assert "function withQuery" not in api_source
    assert "export async function request" not in api_source
    assert "export const systemAuthApi" not in api_source
    assert "clearLocalSessionToken" not in api_source
    assert "saveLocalSessionToken" not in api_source


def test_frontend_api_delegates_account_and_source_boundaries():
    project_root = get_project_root()
    api_file = project_root / "frontend" / "lib" / "api.ts"
    api_source = api_file.read_text(encoding="utf-8")

    for relative_path in [
        "frontend/lib/api/apiAccounts.ts",
        "frontend/lib/api/apiAccountTypes.ts",
        "frontend/lib/api/sourceBindings.ts",
        "frontend/lib/api/sourceTypes.ts",
    ]:
        assert (project_root / relative_path).exists()

    assert 'from "./api/apiAccounts"' in api_source
    assert 'from "./api/apiAccountTypes"' in api_source
    assert 'from "./api/sourceBindings"' in api_source
    assert 'from "./api/sourceTypes"' in api_source
    assert "export const apiAccountApi" not in api_source
    assert "export const sourceBindingApi" not in api_source
    assert "export interface ApiAccount" not in api_source
    assert "export interface SourceBinding" not in api_source
    assert "export interface FavoriteFolder" not in api_source
    assert "export interface Video" not in api_source


def test_frontend_api_delegates_import_favorites_and_legacy_boundaries():
    project_root = get_project_root()
    api_file = project_root / "frontend" / "lib" / "api.ts"
    api_source = api_file.read_text(encoding="utf-8")

    for relative_path in [
        "frontend/lib/api/imports.ts",
        "frontend/lib/api/importTypes.ts",
        "frontend/lib/api/legacyAuth.ts",
        "frontend/lib/api/favorites.ts",
        "frontend/lib/api/legacyKnowledge.ts",
        "frontend/lib/api/knowledgeTypes.ts",
    ]:
        assert (project_root / relative_path).exists()

    assert 'from "./api/imports"' in api_source
    assert 'from "./api/importTypes"' in api_source
    assert 'from "./api/legacyAuth"' in api_source
    assert 'from "./api/favorites"' in api_source
    assert 'from "./api/legacyKnowledge"' in api_source
    assert 'from "./api/knowledgeTypes"' in api_source
    assert "export const importApi" not in api_source
    assert "export const authApi" not in api_source
    assert "export const favoritesApi" not in api_source
    assert "export const knowledgeApi" not in api_source
    assert "export interface ImportMethod" not in api_source
    assert "export interface BuildStatus" not in api_source
    assert "export interface KnowledgeStats" not in api_source


def test_frontend_api_is_a_barrel_for_remaining_domain_modules():
    project_root = get_project_root()
    api_file = project_root / "frontend" / "lib" / "api.ts"
    api_source = api_file.read_text(encoding="utf-8")

    for relative_path in [
        "frontend/lib/api/chat.ts",
        "frontend/lib/api/chatHistory.ts",
        "frontend/lib/api/chatTypes.ts",
        "frontend/lib/api/knowledgeBases.ts",
        "frontend/lib/api/knowledgeBaseTypes.ts",
        "frontend/lib/api/localConnection.ts",
        "frontend/lib/api/localConnectionTypes.ts",
    ]:
        assert (project_root / relative_path).exists()

    assert 'from "./api/chat"' in api_source
    assert 'from "./api/chatHistory"' in api_source
    assert 'from "./api/chatTypes"' in api_source
    assert 'from "./api/knowledgeBases"' in api_source
    assert 'from "./api/knowledgeBaseTypes"' in api_source
    assert 'from "./api/localConnection"' in api_source
    assert 'from "./api/localConnectionTypes"' in api_source
    assert "export const " not in api_source
    assert "export interface " not in api_source
    assert "export type WebSearchProvider =" not in api_source
    assert "import { getApiBaseUrl, request }" not in api_source


def test_frontend_api_tests_are_split_by_domain():
    project_root = get_project_root()
    api_test = project_root / "frontend" / "lib" / "api.test.ts"
    focused_dir = project_root / "frontend" / "lib" / "api" / "__tests__"
    api_source = api_test.read_text(encoding="utf-8")

    focused_files = {
        "apiRuntime.test.ts": [
            "uses the saved native mobile API URL from local connection settings",
            "adds the saved native session token to API requests",
            "uses the saved API URL in Capacitor's localhost Android shell",
            "falls back to CapacitorHttp for native API requests when fetch fails",
        ],
        "systemAdminApi.test.ts": [
            "wraps admin user management requests",
        ],
        "userApiAccounts.test.ts": [
            "wraps user API account requests",
        ],
        "importUploads.test.ts": [
            "uploads local videos with FormData and no JSON content type",
        ],
    }

    for file_name, test_names in focused_files.items():
        focused_path = focused_dir / file_name
        assert focused_path.exists()
        focused_source = focused_path.read_text(encoding="utf-8")
        for test_name in test_names:
            assert test_name not in api_source
            assert test_name in focused_source

    assert len(api_source.splitlines()) <= 80
