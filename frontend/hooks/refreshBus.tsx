"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

export type RefreshTopic =
  "knowledge-bases" | "kb-stats" | "api-accounts" | "chat-history";

type RefreshBus = {
  emit: (topic: RefreshTopic) => void;
  subscribe: (topic: RefreshTopic, listener: () => void) => () => void;
};

const RefreshBusContext = createContext<RefreshBus | null>(null);

const createRefreshBus = (): RefreshBus => {
  const listeners = new Map<RefreshTopic, Set<() => void>>();
  return {
    emit: (topic) => listeners.get(topic)?.forEach((listener) => listener()),
    subscribe: (topic, listener) => {
      const set = listeners.get(topic) ?? new Set();
      listeners.set(topic, set);
      set.add(listener);
      return () => {
        set.delete(listener);
      };
    },
  };
};

export function RefreshBusProvider({ children }: { children: ReactNode }) {
  const [bus] = useState(createRefreshBus);
  return (
    <RefreshBusContext.Provider value={bus}>
      {children}
    </RefreshBusContext.Provider>
  );
}

/** 广播"某类数据已变化"；无 Provider 时为空操作 */
export function useRefreshEmit() {
  const bus = useContext(RefreshBusContext);
  return useCallback((topic: RefreshTopic) => bus?.emit(topic), [bus]);
}

/** 订阅主题，返回递增版本号，可直接作为 useEffect 依赖触发重新拉取 */
export function useRefreshVersion(topic: RefreshTopic) {
  const bus = useContext(RefreshBusContext);
  const [version, setVersion] = useState(0);
  useEffect(() => {
    if (!bus) return;
    return bus.subscribe(topic, () => setVersion((value) => value + 1));
  }, [bus, topic]);
  return version;
}
