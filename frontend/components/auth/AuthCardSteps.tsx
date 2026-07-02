import type { MouseEvent } from "react";

import type { OAuthProvider } from "@/components/auth/authPageLogic";
import {
  AuthCodeHint,
  AuthError,
  AuthSeparator,
} from "@/components/auth/AuthCardParts";
import {
  authCodeRowStyle,
  authHelpTextStyle,
  fieldButtonStyle,
  getCodeButtonStateStyle,
  inputStyle,
  passwordInputStyle,
} from "@/components/auth/authCardStyles";
import AuthOAuthButtons from "@/components/auth/AuthOAuthButtons";
import type { UseAuthFormResult } from "@/components/auth/useAuthForm";

interface AuthStepProps {
  form: UseAuthFormResult;
}

interface AuthEmailStepProps extends AuthStepProps {
  oauthNotice: string | null;
  isOAuthAvailable: (provider: OAuthProvider) => boolean;
  onOAuthClick: (
    event: MouseEvent<HTMLAnchorElement>,
    provider: OAuthProvider,
  ) => void;
}

export function AuthEmailStep({
  form,
  oauthNotice,
  isOAuthAvailable,
  onOAuthClick,
}: AuthEmailStepProps) {
  const { email, error, handleEmailContinue, setEmail, submitting } = form;

  return (
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
          <button type="submit" disabled={submitting} style={fieldButtonStyle}>
            继续
          </button>
        </div>
        <p style={authHelpTextStyle}>
          继续即表示你同意我们的服务条款和隐私政策
        </p>
      </div>
    </form>
  );
}

export function AuthLoginStep({ form }: AuthStepProps) {
  const {
    backToEmail,
    email,
    error,
    handleLogin,
    password,
    setDisplayName,
    setError,
    setPassword,
    setStep,
    submitting,
  } = form;

  return (
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
        <button type="submit" disabled={submitting} style={fieldButtonStyle}>
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
  );
}

export function AuthRegisterStep({ form }: AuthStepProps) {
  const {
    backToEmail,
    codeCountdown,
    codeHint,
    confirmPassword,
    displayName,
    error,
    handleRegister,
    handleSendCode,
    password,
    sendingCode,
    setConfirmPassword,
    setDisplayName,
    setPassword,
    setVerificationCode,
    submitting,
    verificationCode,
  } = form;
  const isCodeButtonDisabled = sendingCode || codeCountdown > 0;

  return (
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
        <div className="auth-code-row" style={authCodeRowStyle}>
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
            disabled={isCodeButtonDisabled}
            style={getCodeButtonStateStyle(isCodeButtonDisabled)}
          >
            {sendingCode
              ? "发送中"
              : codeCountdown > 0
                ? `${codeCountdown}s`
                : "获取验证码"}
          </button>
        </div>
        <AuthCodeHint hint={codeHint} />
        <input
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          style={passwordInputStyle}
          placeholder="设置密码"
          autoComplete="new-password"
        />
        <input
          type="password"
          value={confirmPassword}
          onChange={(event) => setConfirmPassword(event.target.value)}
          style={passwordInputStyle}
          placeholder="确认密码"
          autoComplete="new-password"
        />
        <button type="submit" disabled={submitting} style={fieldButtonStyle}>
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
  );
}
