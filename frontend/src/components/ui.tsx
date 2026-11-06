import { useCallback, useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import type { BookingStatus } from "../types";
import { STATUS } from "../utils";

export function LogoMark({ light = false, size = 40 }: { light?: boolean; size?: number }) {
  const c = light ? "#FFFFFF" : "#0E6B58";
  return (
    <svg width={size} height={size / 2} viewBox="0 0 120 60" aria-hidden="true">
      <circle cx="30" cy="30" r="20" fill="none" stroke={c} strokeWidth="7" />
      <path d="M16 22 Q30 30 44 22 M16 38 Q30 30 44 38 M22 14 Q30 30 22 46 M38 14 Q30 30 38 46" fill="none"
        stroke={c} strokeWidth="3.5" strokeLinecap="round" />
      <path d="M50 30 H110 M94 30 V42 M106 30 V40" fill="none" stroke={c} strokeWidth="7" strokeLinecap="round" />
      <circle cx="30" cy="30" r="5" fill="#F2A93B" />
    </svg>
  );
}

export function Logo({ light = false, to = "/" }: { light?: boolean; to?: string }) {
  return (
    <Link to={to} className="logo" aria-label="Konok — на главную">
      <LogoMark light={light} />
      konok
    </Link>
  );
}

export function StatusBadge({ status }: { status: BookingStatus }) {
  const s = STATUS[status];
  return <span className={`badge ${s.cls}`}>{s.label}</span>;
}

export function ErrorBox({ error }: { error: string | null }) {
  if (!error) return null;
  return <div className="error" role="alert">{error}</div>;
}

export function Spinner({ text = "Загружаем…" }: { text?: string }) {
  return <div className="spinner" role="status">{text}</div>;
}

export function Stars({ value }: { value: number }) {
  const full = Math.round(value);
  return <span className="stars" aria-label={`${value} из 5`}>{"★".repeat(full)}{"☆".repeat(5 - full)}</span>;
}

export function Drawer({ onClose, children, label }: { onClose: () => void; children: ReactNode; label: string }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <aside className="drawer" role="dialog" aria-modal="true" aria-label={label}>{children}</aside>
    </div>
  );
}

export function Modal({ onClose, children, label }: { onClose: () => void; children: ReactNode; label: string }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="overlay modal-overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={label}>{children}</div>
    </div>
  );
}

/** Загрузка данных: { data, error, loading, reload }. */
export function useLoad<T>(fn: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const run = useCallback(fn, deps);
  const reload = useCallback(async () => {
    setLoading(true);
    try {
      setData(await run());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setLoading(false);
    }
  }, [run]);
  useEffect(() => {
    void reload();
  }, [reload]);
  return { data, error, loading, reload, setData };
}

export function errText(e: unknown): string {
  return e instanceof Error ? e.message : "Что-то пошло не так";
}
