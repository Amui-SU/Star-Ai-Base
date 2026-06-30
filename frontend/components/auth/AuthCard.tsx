"use client";

import type { CSSProperties, MouseEvent } from "react";

import type { OAuthProvider } from "@/components/auth/authPageLogic";
import AuthOAuthButtons from "@/components/auth/AuthOAuthButtons";
import type { UseAuthFormResult } from "@/components/auth/useAuthForm";

const inputStyle: CSSProperties = {
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

const buttonStyle: CSSProperties = {
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

const fieldButtonStyle: CSSProperties = {
  ...buttonStyle,
  marginTop: "var(--auth-field-gap)",
};

const codeButtonStyle: CSSProperties = {
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
  flexShrink: 0,
};

const authCardStyle: CSSProperties = {
  marginTop: "var(--auth-card-gap)",
  width: "min(620px, 100%)",
  maxWidth: "100%",
  padding: "var(--auth-card-padding)",
  borderRadius: "var(--auth-card-radius)",
};

interface AuthCardProps {
  form: UseAuthFormResult;
  oauthNotice: string | null;
  isOAuthAvailable: (provider: OAuthProvider) => boolean;
  onOAuthClick: (
    event: MouseEvent<HTMLAnchorElement>,
    provider: OAuthProvider,
  ) => void;
}

export default function AuthCard({
  form,
  oauthNotice,
  isOAuthAvailable,
  onOAuthClick,
}: AuthCardProps) {
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
  } = form;

  return (
    <div
      className="auth-card border border-[#333230] bg-transparent box-border text-left"
      style={authCardStyle}
    >
      {step === "email" && (
        <form onSubmit={handleEmailContinue}>
          <AuthError error={error} />
          <div className="auth-form-inner">
            <AuthOAuthButtons
              notice={oauthNotice}
              isAvailable={isOAuthAvailable}
              onProviderClick={onOAuthClick}
            />
            <AuthSeparator />
            <div className="auth-primary-controls">
              <input
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                style={inputStyle}
                placeholder="输入邮箱地址"
                autoComplete="email"
                autoFocus
              />
              <button
                type="submit"
                disabled={submitting}
                style={fieldButtonStyle}
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
          <AuthError error={error} />
          <div className="auth-form-inner">
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              style={inputStyle}
              placeholder="输入密码"
              autoComplete="current-password"
              autoFocus
            />
            <button
              type="submit"
              disabled={submitting}
              style={fieldButtonStyle}
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
          <AuthError error={error} />
          <div className="auth-form-inner">
            <input
              type="text"
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
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
                onChange={(event) => setVerificationCode(event.target.value)}
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
                  ...codeButtonStyle,
                  opacity: sendingCode || codeCountdown > 0 ? 0.4 : 1,
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
              onChange={(event) => setPassword(event.target.value)}
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
              onChange={(event) => setConfirmPassword(event.target.value)}
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
              style={fieldButtonStyle}
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
  );
}

function AuthError({ error }: { error: string | null }) {
  if (!error) return null;

  return (
    <div className="mb-5 p-3.5 rounded-[9px] bg-[#3b1a1a] border border-[#5c2a2a] text-sm text-[#e88c8c] text-center">
      {error}
    </div>
  );
}

function AuthSeparator() {
  return (
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
  );
}
