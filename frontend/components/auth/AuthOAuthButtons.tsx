"use client";

import Image from "next/image";
import type { MouseEvent } from "react";

import { systemAuthApi } from "@/lib/api";
import type { OAuthProvider } from "@/components/auth/authPageLogic";

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

interface AuthOAuthButtonsProps {
  notice: string | null;
  isAvailable: (provider: OAuthProvider) => boolean;
  onProviderClick: (
    event: MouseEvent<HTMLAnchorElement>,
    provider: OAuthProvider,
  ) => void;
}

export default function AuthOAuthButtons({
  notice,
  isAvailable,
  onProviderClick,
}: AuthOAuthButtonsProps) {
  return (
    <>
      <div className="auth-oauth-grid">
        {oauthButtons.map((button) => {
          const available = isAvailable(button.provider);

          return (
            <a
              key={button.provider}
              href={
                available
                  ? systemAuthApi.getOAuthLoginUrl(button.provider)
                  : "#"
              }
              aria-disabled={!available}
              onClick={(event) => onProviderClick(event, button.provider)}
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
                <OAuthIcon provider={button.provider} />
              </span>
              <span>{button.label}</span>
            </a>
          );
        })}
      </div>
      {notice && (
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
          {notice}
        </div>
      )}
    </>
  );
}

function OAuthIcon({ provider }: { provider: OAuthProvider }) {
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
}
