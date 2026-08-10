"use client";

import * as React from "react";

const STORAGE_KEY = "finmind:masked";

interface MaskContextValue {
  masked: boolean;
  toggle: () => void;
}

const MaskContext = React.createContext<MaskContextValue | null>(null);

const listeners = new Set<() => void>();

function subscribe(onStoreChange: () => void) {
  listeners.add(onStoreChange);
  return () => listeners.delete(onStoreChange);
}

function getSnapshot() {
  return window.localStorage.getItem(STORAGE_KEY) === "1";
}

function getServerSnapshot() {
  return false;
}

function setMaskedStore(next: boolean) {
  window.localStorage.setItem(STORAGE_KEY, next ? "1" : "0");
  listeners.forEach((listener) => listener());
}

/** Topbar privacy toggle — masks every currency figure as "••••••".
 * Client-only, persisted to localStorage per the Nocturne redesign spec.
 * Reads via useSyncExternalStore so the localStorage-backed value is never
 * set from inside an effect (avoids the cascading-render lint/perf issue). */
export function MaskProvider({ children }: { children: React.ReactNode }) {
  const masked = React.useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);

  const toggle = React.useCallback(() => {
    setMaskedStore(!getSnapshot());
  }, []);

  const value = React.useMemo(() => ({ masked, toggle }), [masked, toggle]);

  return <MaskContext.Provider value={value}>{children}</MaskContext.Provider>;
}

export function useMask() {
  const ctx = React.useContext(MaskContext);
  if (!ctx) throw new Error("useMask must be used within a MaskProvider");
  return ctx;
}
