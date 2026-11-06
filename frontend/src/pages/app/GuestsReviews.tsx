import { useState, type FormEvent } from "react";
import { useOutletContext } from "react-router-dom";
import { api } from "../../api";
import { ErrorBox, Modal, Spinner, Stars, StatusBadge, errText, useLoad } from "../../components/ui";
import type { BookingStatus, Guest, GuestRow, Review } from "../../types";
import { fmtDateTime, fmtDay, localDate, money } from "../../utils";
import type { AppCtx } from "./AppLayout";

export function Guests() {
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const [onlyBlack, setOnlyBlack] = useState(false);
  const [open, setOpen] = useState<number | null>(null);
  const qs = new URLSearchParams();
  if (query) qs.set("q", query);
  if (onlyBlack) qs.set("blacklisted", "true");
  const { data, error, loading, reload } = useLoad(() => api<GuestRow[]>(`/guests?${qs}`), [query, onlyBlack]);

  return (
    <>
      <div className="page-head"><h1>Гости</h1></div>
      <form className="row" style={{ marginBottom: 16 }} onSubmit={(e) => { e.preventDefault(); setQuery(q.trim()); }}>
        <input className="input" style={{ maxWidth: 280 }} placeholder="Имя или телефон" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Поиск гостя" />
        <button className="btn">Найти</button>
        <label className="check"><input type="checkbox" checked={onlyBlack} onChange={(e) => setOnlyBlack(e.target.checked)} />Только чёрный список</label>
      </form>
      <ErrorBox error={error} />
      {loading && !data && <Spinner />}
      {data && data.length === 0 && <div className="card empty-state">Гостей пока нет — они появятся с первой бронью</div>}
      {data && data.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead><tr><th>Гость</th><th>Телефон</th><th className="num">Броней</th><th className="num">Принёс</th><th>Заметки</th></tr></thead>
            <tbody>
              {data.map((g) => (
                <tr key={g.id} className="clickable" tabIndex={0} onClick={() => setOpen(g.id)} onKeyDown={(e) => e.key === "Enter" && setOpen(g.id)}>
                  <td><b>{g.is_blacklisted ? "⚑ " : ""}{g.name}</b></td>
                  <td>{g.phone}</td>
                  <td className="num">{g.bookings}</td>
                  <td className="num">{money(g.total_spent)}</td>
                  <td className="small muted">{g.is_blacklisted ? `Чёрный список: ${g.blacklist_reason ?? ""}` : g.notes}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {open !== null && <GuestCard id={open} onClose={() => setOpen(null)} onSaved={() => void reload()} />}
    </>
  );
}

interface GuestDetail extends Guest {
  bookings: { id: number; apartment_id: number; start_at: string; end_at: string; status: BookingStatus; total_price: string }[];
  reviews: { rating: number; text: string }[];
}

function GuestCard({ id, onClose, onSaved }: { id: number; onClose: () => void; onSaved: () => void }) {
  const { aptTitle } = useOutletContext<AppCtx>();
  const { data, error } = useLoad(() => api<GuestDetail>(`/guests/${id}`), [id]);
  const [form, setForm] = useState<{ notes: string; is_blacklisted: boolean; blacklist_reason: string } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const f = form ?? (data ? { notes: data.notes, is_blacklisted: data.is_blacklisted, blacklist_reason: data.blacklist_reason ?? "" } : null);

  const save = async (e: FormEvent) => {
    e.preventDefault();
    if (!f) return;
    try {
      await api(`/guests/${id}`, { method: "PATCH", body: { ...f, blacklist_reason: f.blacklist_reason || null } });
      onSaved();
      onClose();
    } catch (e2) {
      setErr(errText(e2));
    }
  };

  return (
    <Modal onClose={onClose} label="Карточка гостя">
      <ErrorBox error={error ?? err} />
      {!data || !f ? <Spinner /> : (
        <>
          <div className="row between">
            <div><h2>{data.name}</h2><p className="muted">{data.phone}</p></div>
            <button className="btn btn-ghost btn-sm" onClick={onClose} aria-label="Закрыть">✕</button>
          </div>
          <div className="stack" style={{ gap: 8 }}>
            <h3>Брони</h3>
            {data.bookings.map((b) => (
              <div key={b.id} className="row between small">
                <span>{aptTitle(b.apartment_id)} · {fmtDay(localDate(b.start_at))} → {fmtDay(localDate(b.end_at))}</span>
                <span className="row" style={{ gap: 8 }}><StatusBadge status={b.status} />{money(b.total_price)}</span>
              </div>
            ))}
            {data.reviews.map((r, i) => <p key={i} className="small"><Stars value={r.rating} /> {r.text}</p>)}
          </div>
          <form className="stack" onSubmit={save}>
            <label className="field">Заметки<textarea value={f.notes} placeholder="Постоянный, просит ранний заезд…" onChange={(e) => setForm({ ...f, notes: e.target.value })} /></label>
            <label className="check">
              <input type="checkbox" checked={f.is_blacklisted} onChange={(e) => setForm({ ...f, is_blacklisted: e.target.checked })} />
              В чёрный список — при новой брони менеджер увидит предупреждение
            </label>
            {f.is_blacklisted && (
              <label className="field">Причина<input required value={f.blacklist_reason} onChange={(e) => setForm({ ...f, blacklist_reason: e.target.value })} /></label>
            )}
            <button className="btn btn-primary">Сохранить</button>
          </form>
        </>
      )}
    </Modal>
  );
}

export function Reviews() {
  const { isOwner } = useOutletContext<AppCtx>();
  const { data, error, loading, reload } = useLoad(() => api<Review[]>("/reviews"), []);
  const [replying, setReplying] = useState<number | null>(null);
  const [text, setText] = useState("");
  const [err, setErr] = useState<string | null>(null);

  const send = async (e: FormEvent) => {
    e.preventDefault();
    try {
      await api(`/reviews/${replying}/reply`, { body: { reply: text } });
      setReplying(null);
      setText("");
      void reload();
    } catch (e2) {
      setErr(errText(e2));
    }
  };

  const avg = data && data.length ? data.reduce((s, r) => s + r.rating, 0) / data.length : null;

  return (
    <>
      <div className="page-head">
        <h1>Отзывы</h1>
        {avg !== null && <span><Stars value={avg} /> <b>{avg.toFixed(1)}</b> <span className="muted">из {data!.length}</span></span>}
      </div>
      <p className="muted small" style={{ marginBottom: 16 }}>Отзывы оставляют только гости после выезда. Изменить или удалить их нельзя — можно ответить публично.</p>
      <ErrorBox error={error ?? err} />
      {loading && !data && <Spinner />}
      {data && data.length === 0 && <div className="card empty-state">Отзывов пока нет</div>}
      <div className="stack">
        {data?.map((r) => (
          <div key={r.id} className="card stack" style={{ gap: 8 }}>
            <div className="row between">
              <b>{r.guest_name} · {r.apartment_title}</b>
              <span className="row" style={{ gap: 8 }}><Stars value={r.rating} /><span className="small muted">{fmtDateTime(r.created_at)}</span></span>
            </div>
            {r.text && <p>{r.text}</p>}
            {r.owner_reply && <p className="small notice">Ваш ответ: {r.owner_reply}</p>}
            {isOwner && replying !== r.id && (
              <button className="btn btn-sm" style={{ alignSelf: "flex-start" }} onClick={() => { setReplying(r.id); setText(r.owner_reply ?? ""); }}>
                {r.owner_reply ? "Изменить ответ" : "Ответить"}
              </button>
            )}
            {replying === r.id && (
              <form className="stack" onSubmit={send}>
                <textarea className="input" required value={text} onChange={(e) => setText(e.target.value)} aria-label="Ответ на отзыв" />
                <div className="row"><button className="btn btn-primary btn-sm">Опубликовать</button>
                  <button type="button" className="btn btn-ghost btn-sm" onClick={() => setReplying(null)}>Отмена</button></div>
              </form>
            )}
          </div>
        ))}
      </div>
    </>
  );
}
