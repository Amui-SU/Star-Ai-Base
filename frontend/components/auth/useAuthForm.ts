import {
  useEffect,
  useRef,
  useState,
  type Dispatch,
  type FormEvent,
  type SetStateAction,
} from "react";

import { systemAuthApi, type SystemUser } from "@/lib/api";
import type { AuthStep } from "@/components/auth/authPageLogic";

const CODE_COUNTDOWN = 60;

interface UseAuthFormOptions {
  onAuthSuccess: (user: SystemUser) => void;
}

interface UseAuthFormResult {
  step: AuthStep;
  setStep: Dispatch<SetStateAction<AuthStep>>;
  email: string;
  setEmail: Dispatch<SetStateAction<string>>;
  password: string;
  setPassword: Dispatch<SetStateAction<string>>;
  displayName: string;
  setDisplayName: Dispatch<SetStateAction<string>>;
  confirmPassword: string;
  setConfirmPassword: Dispatch<SetStateAction<string>>;
  verificationCode: string;
  setVerificationCode: Dispatch<SetStateAction<string>>;
  sendingCode: boolean;
  codeCountdown: number;
  codeHint: string | null;
  error: string | null;
  setError: Dispatch<SetStateAction<string | null>>;
  submitting: boolean;
  handleSendCode: () => Promise<void>;
  handleEmailContinue: (event: FormEvent) => void;
  handleLogin: (event: FormEvent) => Promise<void>;
  handleRegister: (event: FormEvent) => Promise<void>;
  backToEmail: () => void;
}

export function useAuthForm({
  onAuthSuccess,
}: UseAuthFormOptions): UseAuthFormResult {
  const [step, setStep] = useState<AuthStep>("email");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [verificationCode, setVerificationCode] = useState("");
  const [sendingCode, setSendingCode] = useState(false);
  const [codeCountdown, setCodeCountdown] = useState(0);
  const [codeHint, setCodeHint] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  const startCountdown = () => {
    setCodeCountdown(CODE_COUNTDOWN);
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = setInterval(() => {
      setCodeCountdown((prev) => {
        if (prev <= 1) {
          clearInterval(timerRef.current!);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
  };

  const handleSendCode = async () => {
    if (!email.trim()) return setError("请输入邮箱地址");
    setError(null);
    setSendingCode(true);
    try {
      const resp = await systemAuthApi.sendCode(email.trim());
      startCountdown();
      if (resp.code) setCodeHint(`验证码: ${resp.code}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "发送失败");
    } finally {
      setSendingCode(false);
    }
  };

  const handleEmailContinue = (event: FormEvent) => {
    event.preventDefault();
    if (!email.trim()) return setError("请输入邮箱地址");
    setError(null);
    setStep("login");
  };

  const handleLogin = async (event: FormEvent) => {
    event.preventDefault();
    if (!password.trim()) return setError("请输入密码");
    setError(null);
    setSubmitting(true);
    try {
      const resp = await systemAuthApi.login({ email: email.trim(), password });
      onAuthSuccess(resp.user);
    } catch (err) {
      setError(err instanceof Error ? err.message : "登录失败");
    } finally {
      setSubmitting(false);
    }
  };

  const handleRegister = async (event: FormEvent) => {
    event.preventDefault();
    if (!displayName.trim()) return setError("请填写显示名称");
    if (!verificationCode.trim()) return setError("请输入验证码");
    if (!password.trim()) return setError("请输入密码");
    if (password !== confirmPassword) return setError("两次输入的密码不一致");
    setError(null);
    setSubmitting(true);
    try {
      const resp = await systemAuthApi.register({
        email: email.trim(),
        password,
        display_name: displayName.trim(),
        code: verificationCode.trim(),
      });
      onAuthSuccess(resp.user);
    } catch (err) {
      setError(err instanceof Error ? err.message : "注册失败");
    } finally {
      setSubmitting(false);
    }
  };

  const backToEmail = () => {
    setStep("email");
    setPassword("");
    setDisplayName("");
    setConfirmPassword("");
    setVerificationCode("");
    setCodeHint(null);
    setError(null);
    setCodeCountdown(0);
  };

  return {
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
  };
}
