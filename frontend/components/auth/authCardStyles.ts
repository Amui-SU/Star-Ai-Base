import type { CSSProperties } from "react";

export const inputStyle: CSSProperties = {
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

export const buttonStyle: CSSProperties = {
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

export const fieldButtonStyle: CSSProperties = {
  ...buttonStyle,
  marginTop: "var(--auth-field-gap)",
};

export const codeButtonStyle: CSSProperties = {
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

export const authCardStyle: CSSProperties = {
  marginTop: "var(--auth-card-gap)",
  width: "min(620px, 100%)",
  maxWidth: "100%",
  padding: "var(--auth-card-padding)",
  borderRadius: "var(--auth-card-radius)",
};

export const authHelpTextStyle: CSSProperties = {
  margin: "var(--auth-help-gap) auto 0",
  color: "#a8a49c",
  fontSize: "var(--auth-help-font)",
  lineHeight: 1.55,
  textAlign: "center",
};

export const authCodeRowStyle: CSSProperties = {
  display: "flex",
  gap: 8,
  marginTop: "var(--auth-field-gap)",
};

export const authCodeHintStyle: CSSProperties = {
  padding: 12,
  borderRadius: 9,
  background: "#1a2e2a",
  border: "1px solid #2a4a42",
  fontSize: 14,
  color: "#8cc8b8",
  wordBreak: "break-all",
  textAlign: "center",
  marginTop: "var(--auth-field-gap)",
};

export const passwordInputStyle: CSSProperties = {
  ...inputStyle,
  marginTop: "var(--auth-field-gap)",
};

export const authSeparatorStyle: CSSProperties = {
  margin: "var(--auth-separator-margin)",
  display: "flex",
  alignItems: "center",
  gap: "var(--auth-separator-gap)",
  color: "#c4c0b8",
  fontSize: "var(--auth-separator-font)",
  lineHeight: 1,
};

export const authSeparatorLineStyle: CSSProperties = {
  flex: 1,
  height: 1,
  background: "rgba(255,255,255,0.16)",
};

export function getCodeButtonStateStyle(disabled: boolean): CSSProperties {
  return {
    ...codeButtonStyle,
    opacity: disabled ? 0.4 : 1,
  };
}
