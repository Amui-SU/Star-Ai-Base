"use client";

import { useState, useEffect, useRef, useMemo } from "react";
import { systemAuthApi, SystemUser } from "@/lib/api";

interface Props {
  onAuthSuccess: (user: SystemUser) => void;
}

type Step = "email" | "login" | "register";
const CODE_COUNTDOWN = 60;

export default function AuthPage({ onAuthSuccess }: Props) {
  const [step, setStep] = useState<Step>("email");
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
  const [visible, setVisible] = useState(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ─── 演示流程状态 ───
  type DemoStep = "idle" | "typing" | "searching" | "answering" | "done";
  const [demoStep, setDemoStep] = useState<DemoStep>("idle");
  const [demoTyped, setDemoTyped] = useState("");
  const [demoAnswerTyped, setDemoAnswerTyped] = useState("");
  const [demoRunId, setDemoRunId] = useState(0);
  const demoQuestion = "这个收藏夹里有哪些适合快速入门的 AI 视频？";
  const demoAnswer =
    "我从你的收藏夹中找到了 3 个非常适合入门的内容：\n\n" +
    "1) 《AI 入门路线 30 分钟速览》— 覆盖机器学习、深度学习、NLP 三大方向，每节 10 分钟，适合碎片时间学习。\n\n" +
    "2) 《从零理解大模型》— 从 Transformer 架构讲起，深入浅出地解释 GPT 系列模型的原理，不需要数学基础。\n\n" +
    "3) 《提示词工程的 10 个关键技巧》— 实战导向，含大量可复用的 Prompt 模板，学完即可在日常工作中提效。\n\n" +
    "建议你从第 1 个视频开始，搭建整体框架，再按兴趣深入后两个。三个视频总时长约 90 分钟，一个周末就能完成入门。";
  const demoSources = useMemo(
    () => [
      { title: "AI 入门路线 30 分钟速览" },
      { title: "从零理解大模型" },
      { title: "提示词工程的 10 个关键技巧" },
    ],
    [],
  );

  useEffect(() => {
    const t = window.setTimeout(() => setVisible(true), 80);
    return () => clearTimeout(t);
  }, []);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  // ─── 演示动画编排 ───
  useEffect(() => {
    let initTimer: number | null = null;
    let typingTimer: number | null = null;
    let searchTimer: number | null = null;
    let answerTimer: number | null = null;

    initTimer = window.setTimeout(() => {
      setDemoStep("typing");
      setDemoTyped("");
      setDemoAnswerTyped("");
    }, 600);

    let i = 0;
    typingTimer = window.setInterval(() => {
      i += 1;
      setDemoTyped(demoQuestion.slice(0, i));
      if (i >= demoQuestion.length) {
        if (typingTimer) window.clearInterval(typingTimer);
        setDemoStep("searching");
        searchTimer = window.setTimeout(() => {
          setDemoStep("answering");
          let j = 0;
          answerTimer = window.setInterval(() => {
            j += 2;
            setDemoAnswerTyped(demoAnswer.slice(0, j));
            if (j >= demoAnswer.length) {
              if (answerTimer) window.clearInterval(answerTimer);
              setDemoStep("done");
            }
          }, 18);
        }, 1400);
      }
    }, 60);

    return () => {
      if (initTimer) window.clearTimeout(initTimer);
      if (typingTimer) window.clearInterval(typingTimer);
      if (searchTimer) window.clearTimeout(searchTimer);
      if (answerTimer) window.clearInterval(answerTimer);
    };
  }, [demoRunId, demoQuestion, demoAnswer]);

  // ─── 演示完成 3 秒后自动重播 ───
  useEffect(() => {
    if (demoStep !== "done") return;
    const t = window.setTimeout(() => setDemoRunId((v) => v + 1), 3000);
    return () => clearTimeout(t);
  }, [demoStep]);

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

  // 第一步：输入邮箱 → 进入登录步骤
  const handleEmailContinue = (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) return setError("请输入邮箱地址");
    setError(null);
    setStep("login");
  };

  // 第二步：登录
  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
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

  // 第二步：注册
  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
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

  const inputStyle: React.CSSProperties = {
    width: "100%",
    height: 66,
    borderRadius: 10,
    border: "1px solid #484744",
    background: "#30302e",
    color: "#f5f3ee",
    padding: "0 20px",
    fontSize: 22,
    outline: "none",
    boxSizing: "border-box",
    transition: "all .2s",
  };
  const btnStyle: React.CSSProperties = {
    width: "100%",
    height: 66,
    borderRadius: 10,
    border: 0,
    background: "#f5f3ee",
    color: "#3b3935",
    fontSize: 22,
    fontWeight: 650,
    cursor: "pointer",
    transition: "all .2s",
  };
  const googleBtnStyle: React.CSSProperties = {
    width: "100%",
    height: 64,
    borderRadius: 10,
    border: "1px solid #484744",
    background: "transparent",
    color: "#faf9f5",
    fontSize: 22,
    fontWeight: 650,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: 13,
    cursor: "pointer",
    transition: "all .2s",
    textDecoration: "none",
  };

  return (
    <div className="min-h-screen bg-[#141413] text-[#faf9f5] font-sans">
      {/* 固定顶部 Header */}
      <header
        className="fixed z-50 bg-[#141413]"
        style={{ left: 0, right: 0, top: 0, height: "5.25rem" }}
      >
        <div
          className="h-full flex items-center"
          style={{
            margin: "0 auto",
            width: "calc(100% - 2 * clamp(2rem, 1.43rem + 2.86vw, 4rem))",
            maxWidth: "90rem",
          }}
        >
          <div className="flex items-center gap-2.5">
            <svg
              className="w-7 h-7 text-[#d97757]"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
            >
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
            </svg>
            <span className="font-[Noto_Serif_SC,Georgia,serif] text-[34px] font-semibold tracking-[-0.03em] text-[#faf9f5]">
              智库云
            </span>
          </div>
        </div>
      </header>

      {/* 主内容区 */}
      <main
        className="relative grid grid-cols-1 gap-4 xl:grid-cols-2"
        style={{
          marginLeft: "auto",
          marginRight: "auto",
          paddingTop: "5.25rem",
          width: "calc(100% - 2 * clamp(2rem, 1.43rem + 2.86vw, 4rem))",
          maxWidth: "90rem",
        }}
      >
        {/* 左侧登录区 */}
        <section
          className="flex items-center justify-center py-6"
          style={{ minHeight: "calc(100vh - 5.25rem)" }}
        >
          <div
            className={`flex flex-col items-center text-center transition-all duration-800 ease-out ${
              visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"
            }`}
            style={{ width: 654, maxWidth: "100%" }}
          >
            <h1
              className="m-0 font-[Noto_Serif_SC,Songti_SC,Georgia,serif] leading-[0.98] font-medium tracking-[-0.08em] text-[#faf9f5]"
              style={{ fontSize: 68 }}
            >
              {step === "email"
                ? "欢迎回来"
                : step === "login"
                  ? "输入密码"
                  : "创建账号"}
            </h1>
            <p
              className="mb-0 font-[Noto_Serif_SC,Songti_SC,Georgia,serif] leading-[1.35] text-[#dedbd4]"
              style={{ marginTop: 10, fontSize: 24 }}
            >
              {step === "email"
                ? "登录以继续你的知识探索"
                : step === "login"
                  ? email
                  : "验证邮箱并设置密码"}
            </p>

            {/* 卡片 */}
            <div
              className="border border-[#333230] bg-transparent box-border text-left"
              style={{
                marginTop: 44,
                width: 672,
                maxWidth: "100%",
                padding: "42px 43px 40px",
                borderRadius: 42,
              }}
            >
              {step === "email" && (
                <form onSubmit={handleEmailContinue}>
                  {error && (
                    <div className="mb-5 p-3.5 rounded-[9px] bg-[#3b1a1a] border border-[#5c2a2a] text-sm text-[#e88c8c] text-center">
                      {error}
                    </div>
                  )}
                  <div
                    style={{ width: 586, maxWidth: "100%", margin: "0 auto" }}
                  >
                    <a
                      href={systemAuthApi.googleLoginUrl}
                      style={googleBtnStyle}
                    >
                      <svg className="w-5 h-5" viewBox="0 0 24 24">
                        <path
                          fill="#4285F4"
                          d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"
                        />
                        <path
                          fill="#34A853"
                          d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                        />
                        <path
                          fill="#FBBC05"
                          d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                        />
                        <path
                          fill="#EA4335"
                          d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                        />
                      </svg>
                      <span>使用 Google 继续</span>
                    </a>

                    <div
                      style={{
                        margin: "23px 0",
                        display: "flex",
                        alignItems: "center",
                        gap: 22,
                        color: "#c4c0b8",
                        fontSize: 20,
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
                      style={{ ...btnStyle, marginTop: 24 }}
                    >
                      继续
                    </button>
                    <p
                      style={{
                        margin: "18px auto 0",
                        color: "#a8a49c",
                        fontSize: 18,
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
                  <div
                    style={{ width: 586, maxWidth: "100%", margin: "0 auto" }}
                  >
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
                      style={{ ...btnStyle, marginTop: 24 }}
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
                  <div
                    style={{ width: 586, maxWidth: "100%", margin: "0 auto" }}
                  >
                    <input
                      type="text"
                      value={displayName}
                      onChange={(e) => setDisplayName(e.target.value)}
                      style={inputStyle}
                      placeholder="你的邮箱"
                      autoComplete="name"
                      autoFocus
                    />
                    <div style={{ display: "flex", gap: 8, marginTop: 20 }}>
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
                          height: 66,
                          padding: "0 20px",
                          borderRadius: 10,
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
                          marginTop: 20,
                        }}
                      >
                        {codeHint}
                      </div>
                    )}
                    <input
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      style={{ ...inputStyle, marginTop: 20 }}
                      placeholder="设置密码"
                      autoComplete="new-password"
                    />
                    <input
                      type="password"
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      style={{ ...inputStyle, marginTop: 20 }}
                      placeholder="确认密码"
                      autoComplete="new-password"
                    />
                    <button
                      type="submit"
                      disabled={submitting}
                      style={{ ...btnStyle, marginTop: 24 }}
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

            {step === "email" && (
              <p className="mt-4 mb-0 text-[17px] text-[#77746e]">
                没有账号？继续后即可创建
              </p>
            )}
          </div>
        </section>

        {/* 右侧视觉面板 */}
        <section
          className="hidden lg:flex items-center justify-center bg-[#262624] relative overflow-hidden rounded-[42px]"
          style={{ height: "calc(100vh - 5.25rem - 1.5rem)" }}
        >
          <div
            className="rounded-[34px] bg-[#f5f3ee] text-[#222220] box-border transition-all duration-1000 ease-out"
            style={{
              position: "absolute",
              left: 56,
              right: 56,
              top: 80,
              opacity: visible ? 1 : 0,
              transform: visible ? "translateY(0)" : "translateY(24px)",
              transitionDelay: "200ms",
            }}
          >
            <div style={{ padding: "38px 44px" }}>
              <h3 className="m-0 mb-1 text-[26px] font-bold leading-none tracking-tight">
                检索流程演示
              </h3>
              <p className="m-0 mb-5 text-[15px] text-[#8a8680]">
                慢速演示：理解&quot;提问 → 检索 → 回答&quot;
              </p>

              {/* 提问输入框 */}
              <div
                style={{
                  width: "100%",
                  padding: "12px 14px",
                  borderRadius: 12,
                  border: "1px solid #d5d1c9",
                  background: "#fff",
                  fontSize: 14,
                  color: demoStep === "idle" ? "#a8a49c" : "#222220",
                  minHeight: 40,
                  boxSizing: "border-box",
                }}
              >
                {demoTyped || (demoStep === "idle" ? "等待开始..." : "...")}
              </div>

              {/* 状态指示 */}
              <div className="mt-3 mb-1">
                <span className="text-[13px] text-[#8a8680]">
                  {demoStep === "searching" && "系统正在检索你的收藏夹内容..."}
                  {demoStep === "answering" && "系统正在生成结构化答案..."}
                  {demoStep === "done" && "演示完成，可继续追问"}
                  {(demoStep === "typing" || demoStep === "idle") &&
                    "等待输入..."}
                </span>
                <div className="mt-2 flex justify-end">
                  <span
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 6,
                      padding: "4px 10px",
                      borderRadius: 999,
                      background:
                        demoStep === "done"
                          ? "rgba(47,124,120,0.2)"
                          : "rgba(217,139,43,0.16)",
                      color: demoStep === "done" ? "#1f7a75" : "#9a6b2e",
                      fontSize: 12,
                      fontWeight: 600,
                    }}
                  >
                    {demoStep === "done" ? "完成" : "处理中"}
                  </span>
                </div>
              </div>

              {/* 回答 */}
              <div className="mt-3">
                <div className="text-[13px] text-[#8a8680] mb-1">回答</div>
                <div
                  style={{
                    padding: "12px 14px",
                    borderRadius: 18,
                    background: "#fff",
                    border: "1px solid #e8e4dc",
                    fontSize: 13,
                    lineHeight: 1.62,
                    color: "#222220",
                    minHeight: 120,
                    whiteSpace: "pre-line",
                  }}
                >
                  {demoAnswerTyped || " "}
                </div>
              </div>

              {/* 来源（完成时显示） */}
              {demoStep === "done" && (
                <div className="mt-2">
                  <div className="text-[13px] text-[#8a8680] mb-1">来源</div>
                  <div className="flex gap-1.5 flex-wrap">
                    {demoSources.map((s, i) => (
                      <span
                        key={i}
                        style={{
                          fontSize: 10,
                          color: "#8a8680",
                          whiteSpace: "nowrap",
                          padding: "2px 8px",
                          borderRadius: 999,
                          background: "rgba(0,0,0,0.06)",
                        }}
                      >
                        {s.title}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
