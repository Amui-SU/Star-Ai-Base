"use client";

import Image from "next/image";
import { useEffect, useState } from "react";

import { systemAuthApi, type SystemUser } from "@/lib/api";
import LocalConnectionSettings from "@/components/LocalConnectionSettings";
import AuthDemoPreview from "@/components/auth/AuthDemoPreview";
import {
  getOAuthUnavailableNotice,
  isLocalhost,
  type OAuthProvider,
} from "@/components/auth/authPageLogic";
import { useAuthForm } from "@/components/auth/useAuthForm";
import { useForceDarkTheme } from "@/hooks/useTheme";

interface Props {
  onAuthSuccess: (user: SystemUser) => void;
}

export default function AuthPage({ onAuthSuccess }: Props) {
  const {
    step,
    setStep,
    email,
    setEmail,
    password,
    setPassword,
    displayName,
    setDisplayName,
    confirmPassword,
    setConfirmPassword,
    verificationCode,
    setVerificationCode,
    sendingCode,
    codeCountdown,
    codeHint,
    error,
    setError,
    submitting,
    handleSendCode,
    handleEmailContinue,
    handleLogin,
    handleRegister,
    backToEmail,
  } = useAuthForm({ onAuthSuccess });
  const [visible, setVisible] = useState(false);
  const [googleLoginSupported] = useState(() => {
    if (typeof window === "undefined") return false;
    return isLocalhost(window.location.hostname);
  });
  const [oauthNotice, setOauthNotice] = useState<string | null>(null);

  useForceDarkTheme();

  useEffect(() => {
    const t = window.setTimeout(() => setVisible(true), 80);
    return () => clearTimeout(t);
  }, []);

  const inputStyle: React.CSSProperties = {
    width: "100%",
    height: "var(--auth-control-height)",
    borderRadius: "var(--auth-control-radius)",
    border: "1px solid #484744",
    background: "#30302e",
    color: "#f5f3ee",
    padding: "0 var(--auth-control-x)",
    fontSize: "var(--auth-control-font)",
    outline: "none",
    boxSizing: "border-box",
    transition: "all .2s",
  };
  const btnStyle: React.CSSProperties = {
    width: "100%",
    height: "var(--auth-control-height)",
    borderRadius: "var(--auth-control-radius)",
    border: 0,
    background: "#f5f3ee",
    color: "#3b3935",
    fontSize: "var(--auth-control-font)",
    fontWeight: 650,
    cursor: "pointer",
    transition: "all .2s",
  };
  const oauthButtons: { provider: OAuthProvider; label: string }[] = [
    {
      provider: "google",
      label: "Google",
    },
    {
      provider: "wechat",
      label: "WeChat",
    },
    { provider: "qq", label: "QQ" },
  ];

  const renderOAuthIcon = (provider: OAuthProvider) => {
    if (provider === "google") {
      return (
        <svg
          viewBox="0 0 24 24"
          aria-hidden="true"
          focusable="false"
          style={{ width: "100%", height: "100%", display: "block" }}
        >
          <path
            fill="#4285F4"
            d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.27-4.74 3.27-8.1Z"
          />
          <path
            fill="#34A853"
            d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84A10.99 10.99 0 0 0 12 23Z"
          />
          <path
            fill="#FBBC05"
            d="M5.84 14.09A6.6 6.6 0 0 1 5.49 12c0-.73.13-1.43.35-2.09V7.07H2.18A10.99 10.99 0 0 0 1 12c0 1.78.43 3.45 1.18 4.93l3.66-2.84Z"
          />
          <path
            fill="#EA4335"
            d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1A10.99 10.99 0 0 0 2.18 7.07l3.66 2.84C6.71 7.31 9.14 5.38 12 5.38Z"
          />
        </svg>
      );
    }

    if (provider === "wechat") {
      return (
        <svg
          viewBox="0 0 24 24"
          aria-hidden="true"
          focusable="false"
          style={{ width: "100%", height: "100%", display: "block" }}
        >
          <circle cx="12" cy="12" r="11" fill="#07C160" />
          <path
            fill="#FFFFFF"
            d="M10.2 7.2c-3.18 0-5.76 2.02-5.76 4.52 0 1.42.83 2.67 2.13 3.5l-.46 1.39 1.76-.81c.72.28 1.5.43 2.33.43h.3a4.32 4.32 0 0 1-.17-1.2c0-2.23 2.2-4.04 4.9-4.04.22 0 .44.01.65.04-.45-2.16-2.84-3.83-5.68-3.83Zm-1.94 2.35a.68.68 0 1 1 0 1.36.68.68 0 0 1 0-1.36Zm3.75 0a.68.68 0 1 1 0 1.36.68.68 0 0 1 0-1.36Z"
          />
          <path
            fill="#FFFFFF"
            d="M15.23 11.9c-2.4 0-4.35 1.48-4.35 3.31s1.95 3.31 4.35 3.31c.61 0 1.19-.1 1.72-.27l1.39.64-.35-1.09c.97-.62 1.59-1.55 1.59-2.59 0-1.83-1.95-3.31-4.35-3.31Zm-1.46 1.81a.52.52 0 1 1 0 1.04.52.52 0 0 1 0-1.04Zm2.92 0a.52.52 0 1 1 0 1.04.52.52 0 0 1 0-1.04Z"
          />
        </svg>
      );
    }

    return (
      <Image
        src="/icons/qq-app-icon.jpg"
        alt=""
        aria-hidden="true"
        width={24}
        height={24}
        style={{
          width: "100%",
          height: "100%",
          display: "block",
          borderRadius: 6,
          objectFit: "cover",
        }}
      />
    );
  };

  const isOAuthAvailable = (provider: OAuthProvider) =>
    provider === "google" && googleLoginSupported;

  const handleOAuthClick = (
    event: React.MouseEvent<HTMLAnchorElement>,
    provider: OAuthProvider,
  ) => {
    if (isOAuthAvailable(provider)) return;
    event.preventDefault();
    setOauthNotice(getOAuthUnavailableNotice(provider));
  };

  const oauthButtonStyle: React.CSSProperties = {
    width: "100%",
    minWidth: 0,
    height: "var(--auth-oauth-height)",
    borderRadius: "var(--auth-oauth-radius)",
    border: "1px solid rgba(250, 249, 245, 0.14)",
    background:
      "linear-gradient(180deg, rgba(255,255,255,0.055), rgba(255,255,255,0.025))",
    color: "#faf9f5",
    fontSize: "var(--auth-oauth-font)",
    fontWeight: 640,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: "var(--auth-oauth-icon-gap)",
    padding: "0 var(--auth-oauth-x)",
    cursor: "pointer",
    transition: "all .2s",
    textDecoration: "none",
    boxShadow: "inset 0 1px 0 rgba(255,255,255,0.04)",
  };

  return (
    <div className="auth-page min-h-screen bg-[#141413] text-[#faf9f5] font-sans">
      {/* 固定顶部 Header */}
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

      {/* 主内容区 */}
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
        {/* 左侧登录区 */}
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

            {/* 卡片 */}
            <div
              className="auth-card border border-[#333230] bg-transparent box-border text-left"
              style={{
                marginTop: "var(--auth-card-gap)",
                width: "min(620px, 100%)",
                maxWidth: "100%",
                padding: "var(--auth-card-padding)",
                borderRadius: "var(--auth-card-radius)",
              }}
            >
              {step === "email" && (
                <form onSubmit={handleEmailContinue}>
                  {error && (
                    <div className="mb-5 p-3.5 rounded-[9px] bg-[#3b1a1a] border border-[#5c2a2a] text-sm text-[#e88c8c] text-center">
                      {error}
                    </div>
                  )}
                  <div className="auth-form-inner">
                    <div className="auth-oauth-grid">
                      {oauthButtons.map((button) => {
                        const available = isOAuthAvailable(button.provider);

                        return (
                          <a
                            key={button.provider}
                            href={
                              available
                                ? systemAuthApi.getOAuthLoginUrl(
                                    button.provider,
                                  )
                                : "#"
                            }
                            aria-disabled={!available}
                            onClick={(event) =>
                              handleOAuthClick(event, button.provider)
                            }
                            style={{
                              ...oauthButtonStyle,
                              cursor: available ? "pointer" : "help",
                              opacity: available ? 1 : 0.82,
                            }}
                          >
                            <span
                              style={{
                                width: button.provider === "google" ? 20 : 22,
                                height: button.provider === "google" ? 20 : 22,
                                display: "inline-flex",
                                alignItems: "center",
                                justifyContent: "center",
                                lineHeight: 1,
                              }}
                            >
                              {renderOAuthIcon(button.provider)}
                            </span>
                            <span>{button.label}</span>
                          </a>
                        );
                      })}
                    </div>
                    {oauthNotice && (
                      <div
                        role="status"
                        style={{
                          marginTop: 10,
                          color: "#c9c1b4",
                          fontSize: 12,
                          lineHeight: 1.55,
                          textAlign: "center",
                        }}
                      >
                        {oauthNotice}
                      </div>
                    )}
                    <div
                      className="auth-separator"
                      style={{
                        margin: "var(--auth-separator-margin)",
                        display: "flex",
                        alignItems: "center",
                        gap: "var(--auth-separator-gap)",
                        color: "#c4c0b8",
                        fontSize: "var(--auth-separator-font)",
                        lineHeight: 1,
                      }}
                    >
                      <span
                        style={{
                          flex: 1,
                          height: 1,
                          background: "rgba(255,255,255,0.16)",
                        }}
                      />
                      <span>OR</span>
                      <span
                        style={{
                          flex: 1,
                          height: 1,
                          background: "rgba(255,255,255,0.16)",
                        }}
                      />
                    </div>
                    <div className="auth-primary-controls">
                      <input
                        type="email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        style={inputStyle}
                        placeholder="输入邮箱地址"
                        autoComplete="email"
                        autoFocus
                      />
                      <button
                        type="submit"
                        disabled={submitting}
                        style={{
                          ...btnStyle,
                          marginTop: "var(--auth-field-gap)",
                        }}
                      >
                        继续
                      </button>
                    </div>
                    <p
                      style={{
                        margin: "var(--auth-help-gap) auto 0",
                        color: "#a8a49c",
                        fontSize: "var(--auth-help-font)",
                        lineHeight: 1.55,
                        textAlign: "center",
                      }}
                    >
                      继续即表示你同意我们的服务条款和隐私政策
                    </p>
                  </div>
                </form>
              )}

              {step === "login" && (
                <form onSubmit={handleLogin}>
                  {error && (
                    <div className="mb-5 p-3.5 rounded-[9px] bg-[#3b1a1a] border border-[#5c2a2a] text-sm text-[#e88c8c] text-center">
                      {error}
                    </div>
                  )}
                  <div className="auth-form-inner">
                    <input
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      style={inputStyle}
                      placeholder="输入密码"
                      autoComplete="current-password"
                      autoFocus
                    />
                    <button
                      type="submit"
                      disabled={submitting}
                      style={{
                        ...btnStyle,
                        marginTop: "var(--auth-field-gap)",
                      }}
                    >
                      {submitting ? "登录中..." : "继续"}
                    </button>
                    <div className="text-center space-y-2">
                      <button
                        type="button"
                        onClick={() => {
                          setStep("register");
                          setError(null);
                          setDisplayName(email);
                        }}
                        className="text-[15px] text-[#77746e] hover:text-[#a8a49c] transition-colors"
                      >
                        没有账号？创建一个 →
                      </button>
                      <br />
                      <button
                        type="button"
                        onClick={backToEmail}
                        className="text-sm text-[#5c5a55] hover:text-[#77746e] transition-colors"
                      >
                        不是这个邮箱？返回修改
                      </button>
                    </div>
                  </div>
                </form>
              )}

              {step === "register" && (
                <form onSubmit={handleRegister}>
                  {error && (
                    <div className="mb-5 p-3.5 rounded-[9px] bg-[#3b1a1a] border border-[#5c2a2a] text-sm text-[#e88c8c] text-center">
                      {error}
                    </div>
                  )}
                  <div className="auth-form-inner">
                    <input
                      type="text"
                      value={displayName}
                      onChange={(e) => setDisplayName(e.target.value)}
                      style={inputStyle}
                      placeholder="你的邮箱"
                      autoComplete="name"
                      autoFocus
                    />
                    <div
                      className="auth-code-row"
                      style={{
                        display: "flex",
                        gap: 8,
                        marginTop: "var(--auth-field-gap)",
                      }}
                    >
                      <input
                        type="text"
                        value={verificationCode}
                        onChange={(e) => setVerificationCode(e.target.value)}
                        style={inputStyle}
                        placeholder="验证码"
                        autoComplete="one-time-code"
                        maxLength={6}
                      />
                      <button
                        type="button"
                        onClick={handleSendCode}
                        disabled={sendingCode || codeCountdown > 0}
                        style={{
                          height: "var(--auth-control-height)",
                          padding: "0 var(--auth-code-button-x)",
                          borderRadius: "var(--auth-control-radius)",
                          border: "1px solid #484744",
                          background: "transparent",
                          color: "#dedbd4",
                          fontSize: 15,
                          fontWeight: 600,
                          cursor: "pointer",
                          whiteSpace: "nowrap",
                          opacity: sendingCode || codeCountdown > 0 ? 0.4 : 1,
                          flexShrink: 0,
                        }}
                      >
                        {sendingCode
                          ? "发送中"
                          : codeCountdown > 0
                            ? `${codeCountdown}s`
                            : "获取验证码"}
                      </button>
                    </div>
                    {codeHint && (
                      <div
                        style={{
                          padding: 12,
                          borderRadius: 9,
                          background: "#1a2e2a",
                          border: "1px solid #2a4a42",
                          fontSize: 14,
                          color: "#8cc8b8",
                          wordBreak: "break-all",
                          textAlign: "center",
                          marginTop: "var(--auth-field-gap)",
                        }}
                      >
                        {codeHint}
                      </div>
                    )}
                    <input
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      style={{
                        ...inputStyle,
                        marginTop: "var(--auth-field-gap)",
                      }}
                      placeholder="设置密码"
                      autoComplete="new-password"
                    />
                    <input
                      type="password"
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      style={{
                        ...inputStyle,
                        marginTop: "var(--auth-field-gap)",
                      }}
                      placeholder="确认密码"
                      autoComplete="new-password"
                    />
                    <button
                      type="submit"
                      disabled={submitting}
                      style={{
                        ...btnStyle,
                        marginTop: "var(--auth-field-gap)",
                      }}
                    >
                      {submitting ? "创建中..." : "创建账号"}
                    </button>
                    <div className="text-center">
                      <button
                        type="button"
                        onClick={backToEmail}
                        className="text-[15px] text-[#77746e] hover:text-[#a8a49c] transition-colors"
                      >
                        ← 返回
                      </button>
                    </div>
                  </div>
                </form>
              )}
            </div>
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
