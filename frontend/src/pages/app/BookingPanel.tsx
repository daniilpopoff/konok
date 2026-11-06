import { useEffect, useState } from "react";
import { api, fetchBlobUrl } from "../../api";
import { Drawer, ErrorBox, Spinner, StatusBadge, errText } from "../../components/ui";
import type { BookingDetail } from "../../types";
import { SOURCES, STATUS, fmtDateTime, fmtDay, localDate, money } from "../../utils";

interface Props {
  bookingId: number;
  aptTitle: (id: number) => string;
  onClose: () => void;
  onChanged: () => void;
}

/** Карточка брони: всё, что менеджер делает с бронью, в одном месте. */
export default function BookingPanel({ bookingId, aptTitle, onClose, onChanged }: Props) {
  const [b, setB] = useState<BookingDetail | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [receiptUrl, setReceiptUrl] = useState<string | null>(null);
  const [mode, setMode] = useState<null | "reject" | "checkin" | "deposit" | "cancel">(null);
  const [reason, setReason] = useState("");
  const [checkin, setCheckin] = useState({ balance_paid: true, deposit_received: true });
  const [deposit, setDeposit] = useState({ action: "returned" as "returned" | "withheld", withheld_amount: "", note: "" });
  const [copied, setCopied] = useState(false);

  const load = async () => {
    try {
      const data = await api<BookingDetail>(`/bookings/${bookingId}`);
      setB(data);
      setErr(null);
      if (data.has_receipt) setReceiptUrl(await fetchBlobUrl(`/bookings/${bookingId}/receipt`).catch(() => null));
      else setReceiptUrl(null);
    } catch (e) {
      setErr(errText(e));
    }
  };

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bookingId]);

  const act = async (path: string, body?: unknown) => {
    setBusy(true);
    setErr(null);
    try {
      setB(await api<BookingDetail>(`/bookings/${bookingId}/${path}`, { method: "POST", body: body ?? {} }));
      setMode(null);
      setReason("");
      onChanged();
    } catch (e) {
      setErr(errText(e));
    } finally {
      setBusy(false);
    }
  };

  const openWhatsapp = async () => {
    try {
      const r = await api<{ url: string }>(`/bookings/${bookingId}/whatsapp`);
      window.open(r.url, "_blank", "noopener");
    } catch (e) {
      setErr(errText(e));
    }
  };

  const copyLink = async () => {
    if (!b) return;
    try {
      await navigator.clipboard.writeText(b.guest_link);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };

  return (
    <Drawer onClose={onClose} label="Карточка брони">
      <div className="row between">
        <span className="small muted">Бронь #{bookingId}</span>
        <button className="btn btn-ghost btn-sm" onClick={onClose} aria-label="Закрыть">✕</button>
      </div>
      {!b && !err && <Spinner />}
      <ErrorBox error={err} />
      {b && (
        <>
          <div className="stack" style={{ gap: 8 }}>
            <StatusBadge status={b.status} />
            <h2>{b.status === "blocked" ? `Блокировка: ${b.block_reason ?? ""}` : b.guest?.name ?? "Гость"}</h2>
            <p className="muted">{aptTitle(b.apartment_id)} · {fmtDay(localDate(b.start_at))} → {fmtDay(localDate(b.end_at))}</p>
            {b.guest?.is_blacklisted && (
              <div className="error">⚑ Гость в чёрном списке: {b.guest.blacklist_reason ?? "без причины"}</div>
            )}
          </div>

          {b.status !== "blocked" && (
            <div className="kv">
              <div><p className="k">Сумма</p><p className="v">{money(b.total_price)}</p></div>
              <div><p className="k">Предоплата</p><p className="v">{money(b.prepayment_amount)}</p></div>
              <div><p className="k">Залог</p><p className="v">{money(b.deposit_amount)}{depositNote(b)}</p></div>
              <div><p className="k">Остаток оплачен</p><p className="v">{b.balance_paid ? "Да" : "Нет"}</p></div>
              <div><p className="k">Телефон</p><p className="v">{b.guest?.phone ?? "—"}</p></div>
              <div><p className="k">Источник</p><p className="v">{SOURCES[b.source] ?? b.source}</p></div>
              <div><p className="k">Гостей</p><p className="v">{b.guests_count}</p></div>
              <div><p className="k">Создана</p><p className="v">{fmtDateTime(b.created_at)}</p></div>
            </div>
          )}

          {b.refund_due && (
            <div className={b.refunded ? "notice" : "error"}>
              {b.refunded ? "Предоплата возвращена гостю." : `Нужно вернуть предоплату ${money(b.prepayment_amount)}.`}
            </div>
          )}
          {b.reject_reason && b.status === "awaiting_payment" && <p className="small muted">Чек отклонён: {b.reject_reason}</p>}
          {b.cancel_reason && <p className="small muted">Причина отмены: {b.cancel_reason}</p>}

          {receiptUrl && (
            <a href={receiptUrl} target="_blank" rel="noreferrer">
              <img src={receiptUrl} alt="Чек гостя" className="receipt" onError={(e) => (e.currentTarget.style.display = "none")} />
              <span className="small">Открыть чек полностью</span>
            </a>
          )}

          {/* Действия по статусу */}
          <div className="stack">
            {b.status === "awaiting_confirmation" && mode === null && (
              <>
                <button className="btn btn-primary" disabled={busy} onClick={() => act("confirm")}>Подтвердить оплату</button>
                <button className="btn btn-danger" onClick={() => setMode("reject")}>Отклонить чек</button>
              </>
            )}
            {b.status === "awaiting_payment" && mode === null && (
              <button className="btn" disabled={busy} onClick={() => act("confirm")}>Подтвердить без чека (наличные, перевод)</button>
            )}
            {b.status === "confirmed" && mode === null && (
              <button className="btn btn-primary" onClick={() => setMode("checkin")}>Заселить гостя</button>
            )}
            {b.status === "checked_in" && mode === null && (
              <button className="btn btn-primary" disabled={busy} onClick={() => act("check-out")}>Гость выехал</button>
            )}
            {(b.status === "checked_in" || b.status === "checked_out") && b.deposit_status === "received" && mode === null && (
              <button className="btn" onClick={() => setMode("deposit")}>Закрыть залог</button>
            )}
            {b.status === "checked_out" && b.deposit_status !== "received" && mode === null && (
              <button className="btn btn-primary" disabled={busy} onClick={() => act("close")}>Закрыть бронь</button>
            )}
            {b.refund_due && !b.refunded && (
              <button className="btn" disabled={busy} onClick={() => act("refunded")}>Отметить: предоплата возвращена</button>
            )}

            {mode === "reject" && (
              <form className="card card-tight stack" onSubmit={(e) => { e.preventDefault(); void act("reject", { reason }); }}>
                <label className="field">Почему отклоняем? Гость увидит причину
                  <input required autoFocus value={reason} placeholder="Сумма не совпадает" onChange={(e) => setReason(e.target.value)} />
                </label>
                <div className="row">
                  <button className="btn btn-danger" disabled={busy}>Отклонить</button>
                  <button type="button" className="btn btn-ghost" onClick={() => setMode(null)}>Отмена</button>
                </div>
              </form>
            )}
            {mode === "checkin" && (
              <form className="card card-tight stack" onSubmit={(e) => { e.preventDefault(); void act("check-in", checkin); }}>
                <label className="check">
                  <input type="checkbox" checked={checkin.balance_paid} onChange={(e) => setCheckin({ ...checkin, balance_paid: e.target.checked })} />
                  Остаток {money(Number(b.total_price) - Number(b.prepayment_amount))} получен
                </label>
                {Number(b.deposit_amount) > 0 && (
                  <label className="check">
                    <input type="checkbox" checked={checkin.deposit_received} onChange={(e) => setCheckin({ ...checkin, deposit_received: e.target.checked })} />
                    Залог {money(b.deposit_amount)} получен
                  </label>
                )}
                <div className="row">
                  <button className="btn btn-primary" disabled={busy}>Заселить</button>
                  <button type="button" className="btn btn-ghost" onClick={() => setMode(null)}>Отмена</button>
                </div>
              </form>
            )}
            {mode === "deposit" && (
              <form className="card card-tight stack" onSubmit={(e) => {
                e.preventDefault();
                void act("deposit", { action: deposit.action, note: deposit.note,
                  withheld_amount: deposit.action === "withheld" ? deposit.withheld_amount || "0" : "0" });
              }}>
                <label className="check">
                  <input type="radio" name="dep" checked={deposit.action === "returned"} onChange={() => setDeposit({ ...deposit, action: "returned" })} />
                  Вернули залог полностью
                </label>
                <label className="check">
                  <input type="radio" name="dep" checked={deposit.action === "withheld"} onChange={() => setDeposit({ ...deposit, action: "withheld" })} />
                  Удержали часть
                </label>
                {deposit.action === "withheld" && (
                  <>
                    <label className="field">Сколько удержали, сом
                      <input type="number" min={1} max={Number(b.deposit_amount)} required value={deposit.withheld_amount}
                        onChange={(e) => setDeposit({ ...deposit, withheld_amount: e.target.value })} />
                    </label>
                    <label className="field">За что
                      <input required value={deposit.note} placeholder="Разбитая кружка" onChange={(e) => setDeposit({ ...deposit, note: e.target.value })} />
                    </label>
                  </>
                )}
                <div className="row">
                  <button className="btn btn-primary" disabled={busy}>Сохранить</button>
                  <button type="button" className="btn btn-ghost" onClick={() => setMode(null)}>Отмена</button>
                </div>
              </form>
            )}
            {mode === "cancel" && (
              <form className="card card-tight stack" onSubmit={(e) => { e.preventDefault(); void act("cancel", { reason }); }}>
                <label className="field">Причина отмены
                  <input autoFocus value={reason} onChange={(e) => setReason(e.target.value)} />
                </label>
                <div className="row">
                  <button className="btn btn-danger" disabled={busy}>{b.status === "blocked" ? "Снять блокировку" : "Отменить бронь"}</button>
                  <button type="button" className="btn btn-ghost" onClick={() => setMode(null)}>Назад</button>
                </div>
              </form>
            )}
          </div>

          {b.status !== "blocked" && (
            <div className="row">
              <button className="btn btn-sm" onClick={openWhatsapp}>Написать в WhatsApp</button>
              <button className="btn btn-sm" onClick={copyLink}>{copied ? "Скопировано" : "Ссылка для гостя"}</button>
            </div>
          )}
          {["awaiting_payment", "awaiting_confirmation", "confirmed", "blocked"].includes(b.status) && mode === null && (
            <button className="btn btn-ghost btn-danger btn-sm" style={{ alignSelf: "flex-start" }} onClick={() => setMode("cancel")}>
              {b.status === "blocked" ? "Снять блокировку" : "Отменить бронь"}
            </button>
          )}

          <div className="timeline">
            <h3>История</h3>
            {b.events.map((e, i) => (
              <div key={i} className="timeline-item">
                <span className="muted">{fmtDateTime(e.created_at)}</span>
                <span>
                  <b>{STATUS[e.to_status as keyof typeof STATUS]?.label ?? e.to_status}</b> · {e.actor}
                  {e.note && <span className="muted"> — {e.note}</span>}
                </span>
              </div>
            ))}
          </div>
        </>
      )}
    </Drawer>
  );
}

function depositNote(b: BookingDetail): string {
  switch (b.deposit_status) {
    case "received": return " · у вас";
    case "returned": return " · вернули";
    case "withheld": return ` · удержано ${money(b.deposit_withheld)}`;
    default: return "";
  }
}
