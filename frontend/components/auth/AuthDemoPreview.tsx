"use client";

import { useAuthDemoPreview } from "@/components/auth/useAuthDemoPreview";

interface AuthDemoPreviewProps {
  visible: boolean;
}

export default function AuthDemoPreview({ visible }: AuthDemoPreviewProps) {
  const { demoStep, demoTyped, demoAnswerTyped, demoSources } =
    useAuthDemoPreview();

  return (
    <section
      className="hidden lg:flex items-center justify-center bg-[#262624] relative overflow-hidden rounded-[42px]"
      style={{
        height: "calc(100svh - var(--auth-header-height) - 1.5rem)",
      }}
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

          <div className="mt-3 mb-1">
            <span className="text-[13px] text-[#8a8680]">
              {demoStep === "searching" && "系统正在检索你的收藏夹内容..."}
              {demoStep === "answering" && "系统正在生成结构化答案..."}
              {demoStep === "done" && "演示完成，可继续追问"}
              {(demoStep === "typing" || demoStep === "idle") && "等待输入..."}
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

          {demoStep === "done" && (
            <div className="mt-2">
              <div className="text-[13px] text-[#8a8680] mb-1">来源</div>
              <div className="flex gap-1.5 flex-wrap">
                {demoSources.map((source, index) => (
                  <span
                    key={index}
                    style={{
                      fontSize: 10,
                      color: "#8a8680",
                      whiteSpace: "nowrap",
                      padding: "2px 8px",
                      borderRadius: 999,
                      background: "rgba(0,0,0,0.06)",
                    }}
                  >
                    {source.title}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
