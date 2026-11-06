import { useEffect, useRef, useState, type FormEvent } from "react";
import { useParams } from "react-router-dom";
import { api, mediaUrl } from "../../api";
import { ErrorBox, Logo, Spinner, StatusBadge, errText, useLoad } from "../../components/ui";
import type { GuestBooking } from "../../types";
import { fmtDateTime, localDate, fmtDay, money } from "../../utils";

function useCountdown(until: string | null): string | null {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!until) return;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [until]);
  if (!until) return null;
  const left = Math.max(0, new Date(until).getTime() - now);
  const m = Math.floor(left / 60000), s = Math.floor((left % 60000) / 1000);
  return `${m}:${String(s).padStart(2, "0")}`;
}

const STEPS = [
  { key: "created", label: "Бронь создана" },
  { key: "paid", label: "Чек загружен" },
  { key: "confirmed", label: "Владелец подтвердил" },
  { key: "stay", label: "Заселение" },
];

function stepIndex(status: string): number {
  if (status === "awaiting_payment") return 0;
  if (status === "awaiting_confirmation") return 1;
  if (status === "confirmed") return 2;
  return 3;
}

export default function BookingPage() {
  const { token = "" } = useParams();
  const { data, error, loading, reload, setData } = useLoad(() => api<GuestBooking>(`/public/b/${token}`, { auth: false }), [token]);
  const fileRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [actionErr, setActionErr] = useState<string | null>(null);
  const [cancelOpen, setCancelOpen] = useState(false);
  const [cancelReason, setCancelReason] = useState("");
  const [review, setReview] = useState({ rating: 5, text: "" });
  const [reviewSent, setReviewSent] = useState(false);
  const countdown = useCountdown(data?.status === "awaiting_payment" ? data.hold_expires_at : null);

  // Пока ждём подтверждения — тихо обновляем страницу каждые 10 секунд
  useEffect(() => {
    if (data?.status !== "awaiting_confirmation" && data?.status !== "awaiting_payment") return;
    const t = setInterval(() => void reload(), 10000);
    return () => clearInterval(t);
  }, [data?.status, reload]);

  const upload = async (file: File) => {
    setBusy(true);
    setActionErr(null);
    const form = new FormData();
    form.append("file", file);
    try {
      setData(await api<GuestBooking>(`/public/b/${token}/receipt`, { form, auth: false }));
    } catch (e) {
      setActionErr(errText(e));
      void reload();
    } finally {
      setBusy(false);
    }
  };

  const cancel = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      setData(await api<GuestBooking>(`/public/b/${token}/cancel`, { body: { reason: cancelReason }, auth: false }));
      setCancelOpen(false);
    } catch (err) {
      setActionErr(errText(err));
    } finally {
      setBusy(false);
    }
  };

  const sendReview = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api(`/public/b/${token}/review`, { body: review, auth: false });
      setReviewSent(true);
      void reload();
    } catch (err) {
      setActionErr(errText(err));
    } finally {
      setBusy(false);
    }
  };

  if (loading && !data) return <Spinner />;
  if (!data) return <main className="page-narrow"><ErrorBox error={error ?? "Бронь не найдена"} /></main>;

  const d = data;
  const ended = d.status === "cancelled" || d.status === "expired";
  const idx = stepIndex(d.status);
  const freeCancelLeft = new Date(d.free_cancel_until).getTime() > Date.now();

  return (
    <>
      <header className="topbar"><Logo /><span className="small muted">Ваша бронь</span></header>
      <main className="page-narrow stack-lg">
        <div className="stack" style={{ gap: 8 }}>
          <StatusBadge status={d.status} />
          <h1>{d.apartment_title}</h1>
          <p className="muted">
            {fmtDay(localDate(d.check_in))} → {fmtDay(localDate(d.check_out))} · {d.guests_count} гост. · {money(d.total_price)}
          </p>
          <p className="small muted">Сохраните эту страницу — это ваша бронь. Ссылка работает без регистрации.</p>
        </div>

        {!ended && (
          <ol className="card stack" style={{ margin: 0, paddingLeft: 40, gap: 8 }}>
            {STEPS.map((s, i) => (
              <li key={s.key} style={{ color: i <= idx ? "var(--night)" : "var(--ink-3)", fontWeight: i === idx ? 800 : 400 }}>
                {s.label}
              </li>
            ))}
          </ol>
        )}

        <ErrorBox error={actionErr} />

        {d.status === "awaiting_payment" && (
          <section className="card stack">
            {d.reject_reason && <div className="error">Владелец отклонил чек: {d.reject_reason}. Загрузите правильный чек.</div>}
            <div className="row between">
              <h2>Внесите предоплату</h2>
              {countdown && <span className="badge st-wait">Даты держатся {countdown}</span>}
            </div>
            <p style={{ fontSize: 32, fontWeight: 800 }}>{money(d.prepayment_amount)}</p>
            {d.payment_qr && <img src={mediaUrl(d.payment_qr)} alt="QR-код для оплаты" style={{ width: 220, borderRadius: 12 }} />}
            {d.payment_details && <p className="copy" style={{ whiteSpace: "pre-line" }}>{d.payment_details}</p>}
            <p className="small muted">
              Остаток {money(Number(d.total_price) - Number(d.prepayment_amount))}
              {Number(d.deposit_amount) > 0 && ` и залог ${money(d.deposit_amount)}`} — при передаче ключей.
            </p>
            <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/webp,application/pdf" hidden
              onChange={(e) => e.target.files?.[0] && void upload(e.target.files[0])} />
            <button className="btn btn-primary btn-block" disabled={busy} onClick={() => fileRef.current?.click()}>
              {busy ? "Загружаем…" : "Я оплатил — загрузить чек"}
            </button>
            <p className="small muted">Скриншот перевода из банка: JPG, PNG, WebP или PDF до 10 МБ.</p>
          </section>
        )}

        {d.status === "awaiting_confirmation" && (
          <section className="card stack">
            <h2>Владелец проверяет оплату</h2>
            <p>Обычно это занимает до 15 минут. Страница обновится сама.</p>
          </section>
        )}

        {d.address && (
          <section className="card stack">
            <h2>Адрес и заселение</h2>
            <p><b>{d.address}</b></p>
            {d.checkin_instructions && <p style={{ whiteSpace: "pre-line" }}>{d.checkin_instructions}</p>}
            <p className="small muted">Заезд: {fmtDateTime(d.check_in)} · выезд: {fmtDateTime(d.check_out)}</p>
          </section>
        )}

        {d.status === "expired" && (
          <div className="error">Время на оплату вышло, и даты освободились. Забронируйте заново, если они ещё свободны.</div>
        )}
        {d.status === "cancelled" && <div className="notice">Бронь отменена.</div>}

        {d.can_review && !reviewSent && (
          <form className="card stack" onSubmit={sendReview}>
            <h2>Как вам квартира?</h2>
            <div className="row" role="radiogroup" aria-label="Оценка">
              {[1, 2, 3, 4, 5].map((n) => (
                <button key={n} type="button" role="radio" aria-checked={review.rating === n} aria-label={`${n} из 5`}
                  className={`btn btn-sm ${review.rating >= n ? "btn-primary" : ""}`} onClick={() => setReview({ ...review, rating: n })}>
                  ★
                </button>
              ))}
            </div>
            <label className="field">Пара слов для других гостей
              <textarea value={review.text} onChange={(e) => setReview({ ...review, text: e.target.value })} />
            </label>
            <button className="btn btn-primary" disabled={busy}>Оставить отзыв</button>
          </form>
        )}
        {reviewSent && <div className="notice">Спасибо за отзыв!</div>}

        {d.can_cancel && (
          <section className="stack">
            {!cancelOpen ? (
              <button className="btn btn-danger" onClick={() => setCancelOpen(true)}>Отменить бронь</button>
            ) : (
              <form className="card stack" onSubmit={cancel}>
                <h3>Отменить бронь?</h3>
                <p className="small">
                  {d.status === "awaiting_payment"
                    ? "Вы ещё не платили — просто освободим даты."
                    : freeCancelLeft
                      ? `Бесплатная отмена до ${fmtDateTime(d.free_cancel_until)} — предоплату вернут.`
                      : "Срок бесплатной отмены прошёл — предоплата не возвращается."}
                </p>
                <label className="field">Причина (необязательно)
                  <input value={cancelReason} onChange={(e) => setCancelReason(e.target.value)} />
                </label>
                <div className="row">
                  <button className="btn btn-danger" disabled={busy}>Да, отменить</button>
                  <button type="button" className="btn btn-ghost" onClick={() => setCancelOpen(false)}>Не отменять</button>
                </div>
              </form>
            )}
          </section>
        )}
      </main>
    </>
  );
}
