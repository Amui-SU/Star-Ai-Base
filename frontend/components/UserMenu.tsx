"use client";

import Image from "next/image";
import { SystemUser } from "@/lib/api";

interface Props {
  user: SystemUser;
  onLogout: () => void;
}

export default function UserMenu({ user, onLogout }: Props) {
  const initial = user.display_name?.charAt(0)?.toUpperCase() || "?";

  return (
    <div className="relative group">
      <button className="w-9 h-9 rounded-full bg-(--paper-2) text-(--ink-soft) flex items-center justify-center font-semibold text-sm border border-(--border) hover:border-(--accent) transition-all duration-200">
        {user.avatar_url ? (
          <Image
            src={user.avatar_url}
            alt={`${user.display_name} 的头像`}
            width={36}
            height={36}
            unoptimized
            className="w-full h-full rounded-full object-cover"
            referrerPolicy="no-referrer"
          />
        ) : (
          initial
        )}
      </button>

      <div className="pointer-events-none absolute top-full right-0 mt-2 w-40 rounded-2xl border border-(--border) bg-(--panel-bg) shadow-[0_14px_30px_rgba(0,0,0,0.35)] backdrop-blur-md opacity-0 translate-y-1.5 scale-[0.98] origin-top-right transition-all duration-200 group-hover:pointer-events-auto group-hover:opacity-100 group-hover:translate-y-0 group-hover:scale-100">
        <div className="px-4 pt-3.5 pb-4 text-center">
          <div className="text-[10px] tracking-[0.08em] text-(--muted) mb-1">
            当前账号
          </div>
          <div className="text-sm font-semibold truncate text-(--ink-soft)">
            {user.display_name}
          </div>
          <div className="text-[10px] text-(--muted) truncate mt-0.5">
            {user.email}
          </div>
        </div>
        <button
          onClick={onLogout}
          className="w-full px-4 py-2.5 text-xs font-medium text-(--danger) hover:bg-(--paper-2) rounded-b-2xl transition-colors flex items-center justify-center gap-2 border-t border-(--border)"
        >
          <svg
            className="w-3.5 h-3.5"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
            />
          </svg>
          退出登录
        </button>
      </div>
    </div>
  );
}
