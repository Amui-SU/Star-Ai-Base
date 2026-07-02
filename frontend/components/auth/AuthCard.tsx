"use client";

import type { MouseEvent } from "react";

import type { OAuthProvider } from "@/components/auth/authPageLogic";
import { authCardStyle } from "@/components/auth/authCardStyles";
import {
  AuthEmailStep,
  AuthLoginStep,
  AuthRegisterStep,
} from "@/components/auth/AuthCardSteps";
import type { UseAuthFormResult } from "@/components/auth/useAuthForm";

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
  return (
    <div
      className="auth-card border border-[#333230] bg-transparent box-border text-left"
      style={authCardStyle}
    >
      {form.step === "email" && (
        <AuthEmailStep
          form={form}
          oauthNotice={oauthNotice}
          isOAuthAvailable={isOAuthAvailable}
          onOAuthClick={onOAuthClick}
        />
      )}
      {form.step === "login" && <AuthLoginStep form={form} />}
      {form.step === "register" && <AuthRegisterStep form={form} />}
    </div>
  );
}
