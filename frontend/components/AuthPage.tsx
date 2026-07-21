"use client";

import { useEffect, useState, type MouseEvent } from "react";

import { type SystemUser } from "@/lib/api";
import LocalConnectionSettings from "@/components/LocalConnectionSettings";
import AuthCard from "@/components/auth/AuthCard";
import AuthDemoPreview from "@/components/auth/AuthDemoPreview";
import {
  getOAuthUnavailableNotice,
  supportsPublicHttpsOAuth,
  type OAuthProvider,
} from "@/components/auth/authPageLogic";
import { useAuthForm } from "@/components/auth/useAuthForm";
import { useForceDarkTheme } from "@/hooks/useTheme";

interface Props {
  onAuthSuccess: (user: SystemUser) => void;
}

export default function AuthPage({ onAuthSuccess }: Props) {
  const form = useAuthForm({ onAuthSuccess });
  const { step, email } = form;
  const [visible, setVisible] = useState(false);
  const [googleLoginSupported] = useState(() => {
    if (typeof window === "undefined") return false;
    return supportsPublicHttpsOAuth(
      window.location.protocol,
      window.location.hostname,
    );
  });
  const [oauthNotice, setOauthNotice] = useState<string | null>(null);

  useForceDarkTheme();

  useEffect(() => {
    const t = window.setTimeout(() => setVisible(true), 80);
    return () => clearTimeout(t);
  }, []);

  const isOAuthAvailable = (provider: OAuthProvider) =>
    provider === "google" && googleLoginSupported;

  const handleOAuthClick = (
    event: MouseEvent<HTMLAnchorElement>,
    provider: OAuthProvider,
  ) => {
    if (isOAuthAvailable(provider)) return;
    event.preventDefault();
    setOauthNotice(getOAuthUnavailableNotice(provider));
  };

  return (
    <div className="auth-page min-h-screen bg-[#141413] text-[#faf9f5] font-sans">
      <header
        className="auth-header fixed z-50 bg-[#141413]"
        style={{
          left: 0,
          right: 0,
          top: 0,
          height: "var(--auth-header-height)",
        }}
      >
        <div
          className="auth-header-inner h-full flex items-center"
          style={{
            margin: "0 auto",
            width: "var(--auth-container-width)",
            maxWidth: "90rem",
          }}
        >
          <div className="flex items-center gap-2.5">
            <svg
              className="auth-brand-icon w-7 h-7 text-[#d97757]"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
            >
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
            </svg>
            <span className="auth-brand-title font-[Noto_Serif_SC,Georgia,serif] text-[34px] font-semibold tracking-[-0.03em] text-[#faf9f5]">
              智库云
            </span>
          </div>
          <div className="auth-header-actions">
            <LocalConnectionSettings />
          </div>
        </div>
      </header>

      <main
        className="auth-main relative grid grid-cols-1 gap-4 xl:grid-cols-2"
        style={{
          marginLeft: "auto",
          marginRight: "auto",
          paddingTop: "var(--auth-header-height)",
          width: "var(--auth-container-width)",
          maxWidth: "90rem",
        }}
      >
        <section
          className="auth-form-section auth-form-section-lowered flex items-center justify-center py-6"
          style={{ minHeight: "calc(100svh - var(--auth-header-height))" }}
        >
          <div
            className={`auth-form-content flex flex-col items-center text-center transition-all duration-800 ease-out ${
              visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"
            }`}
            style={{ width: "min(604px, 100%)", maxWidth: "100%" }}
          >
            <h1 className="auth-title m-0 font-[Noto_Serif_SC,Songti_SC,Georgia,serif] leading-[0.98] font-medium tracking-[-0.08em] text-[#faf9f5]">
              {step === "email"
                ? "欢迎回来"
                : step === "login"
                  ? "输入密码"
                  : "创建账号"}
            </h1>
            <p className="auth-subtitle mb-0 font-[Noto_Serif_SC,Songti_SC,Georgia,serif] leading-[1.35] text-[#dedbd4]">
              {step === "email"
                ? "登录以继续你的知识探索"
                : step === "login"
                  ? email
                  : "验证邮箱并设置密码"}
            </p>

            <AuthCard
              form={form}
              oauthNotice={oauthNotice}
              isOAuthAvailable={isOAuthAvailable}
              onOAuthClick={handleOAuthClick}
            />
          </div>
          {step === "email" && (
            <p className="auth-account-hint mt-4 mb-0 text-[17px] text-[#77746e]">
              没有账号？继续后即可创建
            </p>
          )}
        </section>

        <AuthDemoPreview visible={visible} />
      </main>
    </div>
  );
}
