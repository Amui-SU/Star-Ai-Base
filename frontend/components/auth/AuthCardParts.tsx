import {
  authCodeHintStyle,
  authSeparatorLineStyle,
  authSeparatorStyle,
} from "@/components/auth/authCardStyles";

export function AuthError({ error }: { error: string | null }) {
  if (!error) return null;

  return (
    <div className="mb-5 p-3.5 rounded-[9px] bg-[#3b1a1a] border border-[#5c2a2a] text-sm text-[#e88c8c] text-center">
      {error}
    </div>
  );
}

export function AuthSeparator() {
  return (
    <div className="auth-separator" style={authSeparatorStyle}>
      <span style={authSeparatorLineStyle} />
      <span>OR</span>
      <span style={authSeparatorLineStyle} />
    </div>
  );
}

export function AuthCodeHint({ hint }: { hint: string | null }) {
  if (!hint) return null;

  return <div style={authCodeHintStyle}>{hint}</div>;
}
