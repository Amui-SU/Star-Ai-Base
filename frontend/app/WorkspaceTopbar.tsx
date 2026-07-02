import UserMenu from "@/components/UserMenu";
import LocalConnectionSettings from "@/components/LocalConnectionSettings";
import type { SystemUser } from "@/lib/api";

interface WorkspaceTopbarProps {
  isDarkMode: boolean;
  themeReady: boolean;
  user: SystemUser;
  onLogout: () => void;
  onOpenAdmin: () => void;
  onOpenApiAccounts: () => void;
  onThemeToggle: () => void;
  onUserChange: (user: SystemUser) => void;
}

export default function WorkspaceTopbar({
  isDarkMode,
  themeReady,
  user,
  onLogout,
  onOpenAdmin,
  onOpenApiAccounts,
  onThemeToggle,
  onUserChange,
}: WorkspaceTopbarProps) {
  return (
    <header className="workspace-topbar">
      <div className="workspace-brand">
        <span className="workspace-brand-mark">◇</span>
        <span>智库云</span>
      </div>
      <div className="workspace-top-actions">
        <LocalConnectionSettings />
        {themeReady && (
          <button
            onClick={onThemeToggle}
            className="workspace-icon-btn"
            title={isDarkMode ? "切换到白天模式" : "切换到夜间模式"}
          >
            {isDarkMode ? <SunIcon /> : <MoonIcon />}
          </button>
        )}
        <UserMenu
          user={user}
          onUserChange={onUserChange}
          onLogout={onLogout}
          onOpenApiAccounts={onOpenApiAccounts}
          onOpenAdmin={onOpenAdmin}
        />
      </div>
    </header>
  );
}

function SunIcon() {
  return (
    <svg
      className="w-4 h-4"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"
      />
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg
      className="w-4 h-4"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"
      />
    </svg>
  );
}
