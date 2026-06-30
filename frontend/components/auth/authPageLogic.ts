export type AuthStep = "email" | "login" | "register";
export type OAuthProvider = "google" | "wechat" | "qq";

export const isLocalhost = (host: string) =>
  host === "localhost" || host === "127.0.0.1" || host === "[::1]";

export function getOAuthUnavailableNotice(provider: OAuthProvider) {
  if (provider === "google") {
    return "Google login requires an HTTPS public callback. Use email login in local mobile preview.";
  }
  return "WeChat and QQ login are not configured yet. Use email login for now.";
}
