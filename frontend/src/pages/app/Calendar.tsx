import { useState, type CSSProperties, type FormEvent } from "react";
import { Link, useOutletContext } from "react-router-dom";
import { api } from "../../api";
import { ErrorBox, Modal, Spinner, errText, useLoad } from "../../components/ui";
import type { CalendarData } from "../../types";
import { STATUS, WD, addDays, fmtDay, localDate, todayISO, weekday } from "../../utils";
import type { AppCtx } from "./AppLayout";
import BookingPanel from "./BookingPanel";

const DAYS = 14;

const BAR_STYLE: Record<string, CSSProperties> = {
  awaiting_payment: { background: "var(--sun-soft)", color: "var(--sun-ink)", boxShadow: "inset 0 0 0 1px #c98a1e" },
  awaiting_confirmation: { background: "var(--sun)", color: "var(--night)" },
  confirmed: { background: "var(--teal)", color: "#fff" },
  checked_in: { background: "var(--teal-deep)", color: "#fff" },
  checked_out: { background: "var(--ink-3)", color: "#fff" },
  closed: { background: "#e9e6df", color: "var(--ink-2)" },
  blocked: { background: "#d9d5cc", color: "var(--ink-2)" },
};

export default function Calendar() {
  const { aptTitle, apartments, bumpPending } = useOutletContext<AppCtx>();
  const [start, setStart] = useState(addDays(todayISO(), -1));
  const end = addDays(start, DAYS - 1);
  const { data, error, loading, reload } = useLoad(
    () => api<CalendarData>(`/bookings/calendar?date_from=${start}&date_to=${end}`), [start, end]);
  const [selected, setSelected] = useState<number | null>(null);
  const [create, setCreate] = useState<null | { apartment_id: number; day: string; kind: "booking" | "block" }>(null);

  const days = Array.from({ length: DAYS }, (_, i) => addDays(start, i));
  const today = todayISO();

  const stats = (() => {
    if (!data) return null;
    let busy = 0, pending = 0, arrivals = 0, departures = 0;
    const seen = new Set<number>();
    for (const a of data.apartments) for (const b of a.bookings) {
      if (b.status === "blocked") continue;
      const s = localDate(b.start_at), e = localDate(b.end_at);
      for (const d of days) if (s <= d && d < e) busy++;
      if (!seen.has(b.id) && b.status === "awaiting_confirmation") pending++;
      if (s === today) arrivals++;
      if (e === today) departures++;
      seen.add(b.id);
    }
    const total = days.length * data.apartments.length;
    return { occupancy: total ? Math.round((100 * busy) / total) : 0, pending, arrivals, departures };
  })();

  const changed = () => { void reload(); bumpPending(); };

  return (
    <>
      <div className="page-head">
        <h1>Шахматка</h1>
        <div className="row">
          <button className="btn btn-sm" onClick={() => setStart(addDays(start, -7))} aria-label="Неделя назад">←</button>
          <button className="btn btn-sm" onClick={() => setStart(addDays(todayISO(), -1))}>Сегодня</button>
          <button className="btn btn-sm" onClick={() => setStart(addDays(start, 7))} aria-label="Неделя вперёд">→</button>
          <span className="small muted">{fmtDay(start)} — {fmtDay(end)}</span>
        </div>
        <div className="row">
          <button className="btn" disabled={!apartments.length}
            onClick={() => setCreate({ apartment_id: apartments[0].id, day: today, kind: "block" })}>Заблокировать даты</button>
          <button className="btn btn-primary" disabled={!apartments.length}
            onClick={() => setCreate({ apartment_id: apartments[0].id, day: today, kind: "booking" })}>+ Бронь из WhatsApp</button>
        </div>
      </div>

      {stats && (
        <div className="kpis">
          <div className="kpi"><p className="small muted">Ждут подтверждения</p><p className="v" style={{ color: "var(--sun-ink)" }}>{stats.pending}</p></div>
          <div className="kpi"><p className="small muted">Загрузка за 14 дней</p><p className="v">{stats.occupancy}%</p></div>
          <div className="kpi"><p className="small muted">Заезды сегодня</p><p className="v">{stats.arrivals}</p></div>
          <div className="kpi"><p className="small muted">Выезды сегодня</p><p className="v">{stats.departures}</p></div>
        </div>
      )}

      <ErrorBox error={error} />
      {loading && !data && <Spinner />}
      {data && data.apartments.length === 0 && (
        <div className="card empty-state stack">
          <p>Пока нет ни одной квартиры.</p>
          <Link to="/app/apartments?new=1" className="btn btn-primary" style={{ alignSelf: "center" }}>Добавить квартиру</Link>
        </div>
      )}
      {data && data.apartments.length > 0 && (
        <div className="board-wrap">
          <div className="board" style={{ "--days": DAYS } as CSSProperties}>
            <div className="board-row">
              <span />
              {days.map((d) => {
                const wd = weekday(d);
                return (
                  <span key={d} className={`board-head${d === today ? " today" : ""}${wd >= 5 ? " weekend" : ""}`}>
                    {WD[wd]}<b>{Number(d.slice(8))}</b>
                  </span>
                );
              })}
            </div>
            {data.apartments.map((apt) => {
              // ячейки: свободные дни и полосы броней (colspan через grid-column span)
              const cells: JSX.Element[] = [];
              let i = 0;
              while (i < days.length) {
                const d = days[i];
                const b = apt.bookings.find((x) => localDate(x.start_at) <= d && d < localDate(x.end_at));
                if (!b) {
                  cells.push(
                    <button key={d} className="cell" aria-label={`Свободно, ${fmtDay(d)}, ${apt.title}. Создать бронь`}
                      onClick={() => setCreate({ apartment_id: apt.id, day: d, kind: "booking" })} />,
                  );
                  i++;
                  continue;
                }
                const bEnd = localDate(b.end_at);
                let span = 0;
                while (i + span < days.length && days[i + span] < bEnd) span++;
                const first = localDate(b.start_at) >= start && localDate(b.start_at) === d;
                const last = bEnd <= addDays(end, 1);
                const label = b.status === "blocked" ? b.block_reason ?? "Блок" : b.guest ?? "Гость";
                cells.push(
                  <button key={d} className={`bar${first ? " first" : ""}${last ? " last" : ""}${selected === b.id ? " selected" : ""}${b.warning ? " warn" : ""}`}
                    style={{ ...BAR_STYLE[b.status], gridColumn: `span ${span}` }}
                    title={`${label} · ${STATUS[b.status].label}`}
                    aria-label={`${label}, ${STATUS[b.status].label}, ${fmtDay(localDate(b.start_at))} – ${fmtDay(bEnd)}`}
                    onClick={() => setSelected(b.id)}>
                    {label}
                  </button>,
                );
                i += span;
              }
              return (
                <div key={apt.id} className="board-row">
                  <div className="board-apt"><b>{apt.title}</b></div>
                  {cells}
                </div>
              );
            })}
          </div>
          <div className="legend">
            {["awaiting_payment", "awaiting_confirmation", "confirmed", "checked_in", "checked_out", "blocked"].map((s) => (
              <span key={s} className="row small" style={{ gap: 6 }}>
                <span style={{ width: 14, height: 14, borderRadius: 4, ...BAR_STYLE[s] }} />
                {STATUS[s as keyof typeof STATUS].label}
              </span>
            ))}
          </div>
        </div>
      )}

      {selected !== null && (
        <BookingPanel bookingId={selected} aptTitle={aptTitle} onClose={() => setSelected(null)} onChanged={changed} />
      )}
      {create && (
        <CreateModal init={create} onClose={() => setCreate(null)} onCreated={(id) => { setCreate(null); changed(); if (id) setSelected(id); }} />
      )}
    </>
  );
}

function CreateModal({ init, onClose, onCreated }: {
  init: { apartment_id: number; day: string; kind: "booking" | "block" };
  onClose: () => void;
  onCreated: (id: number | null) => void;
}) {
  const { apartments } = useOutletContext<AppCtx>();
  const [kind, setKind] = useState(init.kind);
  const [f, setF] = useState({
    apartment_id: init.apartment_id, check_in: init.day, check_out: addDays(init.day, 1), name: "", phone: "",
    guests_count: 1, status: "confirmed", total_price: "", reason: "",
  });
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      if (kind === "block") {
        await api("/bookings/blocks", { body: { apartment_id: f.apartment_id, check_in: f.check_in, check_out: f.check_out, reason: f.reason } });
        onCreated(null);
      } else {
        const b = await api<{ id: number }>("/bookings", {
          body: { apartment_id: f.apartment_id, check_in: f.check_in, check_out: f.check_out, name: f.name, phone: f.phone,
            guests_count: f.guests_count, status: f.status, total_price: f.total_price === "" ? null : f.total_price },
        });
        onCreated(b.id);
      }
    } catch (e2) {
      setErr(errText(e2));
      setBusy(false);
    }
  };

  return (
    <Modal onClose={onClose} label={kind === "block" ? "Блокировка дат" : "Новая бронь"}>
      <div className="row between">
        <div className="row">
          <button type="button" className={`btn btn-sm ${kind === "booking" ? "btn-primary" : ""}`} onClick={() => setKind("booking")}>Бронь</button>
          <button type="button" className={`btn btn-sm ${kind === "block" ? "btn-primary" : ""}`} onClick={() => setKind("block")}>Блокировка</button>
        </div>
        <button className="btn btn-ghost btn-sm" onClick={onClose} aria-label="Закрыть">✕</button>
      </div>
      <form className="stack" onSubmit={submit}>
        <label className="field">Квартира
          <select value={f.apartment_id} onChange={(e) => setF({ ...f, apartment_id: Number(e.target.value) })}>
            {apartments.map((a) => <option key={a.id} value={a.id}>{a.title}</option>)}
          </select>
        </label>
        <div className="grid-2">
          <label className="field">{kind === "block" ? "С" : "Заезд"}
            <input type="date" required value={f.check_in} onChange={(e) => setF({ ...f, check_in: e.target.value })} />
          </label>
          <label className="field">{kind === "block" ? "По (не включая)" : "Выезд"}
            <input type="date" required min={addDays(f.check_in, 1)} value={f.check_out} onChange={(e) => setF({ ...f, check_out: e.target.value })} />
          </label>
        </div>
        {kind === "block" ? (
          <label className="field">Причина
            <input required placeholder="Ремонт, живу сам, родственники" value={f.reason} onChange={(e) => setF({ ...f, reason: e.target.value })} />
          </label>
        ) : (
          <>
            <div className="grid-2">
              <label className="field">Имя гостя<input required value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></label>
              <label className="field">Телефон<input required type="tel" placeholder="+996…" value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} /></label>
            </div>
            <div className="grid-2">
              <label className="field">Гостей<input type="number" min={1} value={f.guests_count} onChange={(e) => setF({ ...f, guests_count: Number(e.target.value) })} /></label>
              <label className="field">Сумма, сом
                <input type="number" min={0} placeholder="по прайсу" value={f.total_price} onChange={(e) => setF({ ...f, total_price: e.target.value })} />
              </label>
            </div>
            <label className="field">Предоплата
              <select value={f.status} onChange={(e) => setF({ ...f, status: e.target.value })}>
                <option value="confirmed">Уже получена — сразу подтвердить</option>
                <option value="awaiting_payment">Ещё нет — отправлю гостю ссылку на оплату</option>
              </select>
            </label>
          </>
        )}
        <ErrorBox error={err} />
        <button className="btn btn-primary" disabled={busy}>{kind === "block" ? "Заблокировать" : "Создать бронь"}</button>
      </form>
    </Modal>
  );
}
