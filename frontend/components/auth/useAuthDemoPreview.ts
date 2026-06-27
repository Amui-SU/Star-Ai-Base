"use client";

import { useEffect, useState } from "react";

export type AuthDemoStep =
  | "idle"
  | "typing"
  | "searching"
  | "answering"
  | "done";

const DEMO_QUESTION = "这个收藏夹里有哪些适合快速入门的 AI 视频？";
const DEMO_ANSWER =
  "我从你的收藏夹中找到了 3 个非常适合入门的内容：\n\n" +
  "1) 《AI 入门路线 30 分钟速览》— 覆盖机器学习、深度学习、NLP 三大方向，每节 10 分钟，适合碎片时间学习。\n\n" +
  "2) 《从零理解大模型》— 从 Transformer 架构讲起，深入浅出地解释 GPT 系列模型的原理，不需要数学基础。\n\n" +
  "3) 《提示词工程的 10 个关键技巧》— 实战导向，含大量可复用的 Prompt 模板，学完即可在日常工作中提效。\n\n" +
  "建议你从第 1 个视频开始，搭建整体框架，再按兴趣深入后两个。三个视频总时长约 90 分钟，一个周末就能完成入门。";

const DEMO_SOURCES = [
  { title: "AI 入门路线 30 分钟速览" },
  { title: "从零理解大模型" },
  { title: "提示词工程的 10 个关键技巧" },
];

export function useAuthDemoPreview() {
  const [demoStep, setDemoStep] = useState<AuthDemoStep>("idle");
  const [demoTyped, setDemoTyped] = useState("");
  const [demoAnswerTyped, setDemoAnswerTyped] = useState("");
  const [demoRunId, setDemoRunId] = useState(0);

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
      setDemoTyped(DEMO_QUESTION.slice(0, i));
      if (i >= DEMO_QUESTION.length) {
        if (typingTimer) window.clearInterval(typingTimer);
        setDemoStep("searching");
        searchTimer = window.setTimeout(() => {
          setDemoStep("answering");
          let j = 0;
          answerTimer = window.setInterval(() => {
            j += 2;
            setDemoAnswerTyped(DEMO_ANSWER.slice(0, j));
            if (j >= DEMO_ANSWER.length) {
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
  }, [demoRunId]);

  useEffect(() => {
    if (demoStep !== "done") return;
    const timer = window.setTimeout(
      () => setDemoRunId((value) => value + 1),
      3000,
    );
    return () => clearTimeout(timer);
  }, [demoStep]);

  return {
    demoStep,
    demoTyped,
    demoAnswerTyped,
    demoSources: DEMO_SOURCES,
  };
}
