import { useState } from "react";
import { useOutletContext } from "react-router-dom";
import { api, fetchBlobUrl } from "../../api";
import { ErrorBox, Spinner, StatusBadge, useLoad } from "../../components/ui";
import type { Booking } from "../../types";
import { SOURCES, fmtDay, localDate, money } from "../../utils";
import type { AppCtx } from "./AppLayout";
import BookingPanel from "./BookingPanel";

const FILTERS: [string, string][] = [
  ["", "Все"],
  ["awaiting_confirmation", "Чек на проверке"],
  ["awaiting_payment", "Ждут оплаты"],
  ["confirmed", "Подтверждены"],
  ["checked_in", "Живут"],
  ["checked_out", "Выехали"],
  ["cancelled", "Отменены"],
];

export default function Bookings() {
  const { aptTitle, apartments, bumpPending, isOwner } = useOutletContext<AppCtx>();
  const [status, setStatus] = useState("");
  const [apt, setApt] = useState("");
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<number | null>(null);

  const params = new URLSearchParams();
  if (status) params.append("status", status);
  if (apt) params.set("apartment_id", apt);
  if (query) params.set("q", query);
  const { data, error, loading, reload } = useLoad(() => api<Booking[]>(`/bookings?${params}`), [status, apt, query]);

  return (
    <>
      <div className="page-head">
        <h1>Брони</h1>
        {isOwner && user_exportLink()}
      </div>
      <div className="row" style={{ marginBottom: 16 }}>
        {FILTERS.map(([v, l]) => (
          <button key={v} className={`btn btn-sm ${status === v ? "btn-primary" : ""}`} onClick={() => setStatus(v)}>{l}</button>
        ))}
      </div>
      <form className="row" style={{ marginBottom: 16 }} onSubmit={(e) => { e.preventDefault(); setQuery(q.trim()); }}>
        <input className="input" style={{ maxWidth: 280 }} placeholder="Имя или телефон гостя" value={q} onChange={(e) => setQ(e.target.value)}
          aria-label="Поиск по гостю" />
        <select className="input" style={{ maxWidth: 240 }} value={apt} onChange={(e) => setApt(e.target.value)} aria-label="Квартира">
          <option value="">Все квартиры</option>
          {apartments.map((a) => <option key={a.id} value={a.id}>{a.title}</option>)}
        </select>
        <button className="btn">Найти</button>
      </form>
      <ErrorBox error={error} />
      {loading && !data && <Spinner />}
      {data && data.length === 0 && <div className="card empty-state">Броней не найдено</div>}
      {data && data.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>Гость</th><th>Квартира</th><th>Даты</th><th>Статус</th><th>Источник</th><th className="num">Сумма</th></tr>
            </thead>
            <tbody>
              {data.filter((b) => b.status !== "blocked").map((b) => (
                <tr key={b.id} className="clickable" onClick={() => setSelected(b.id)} tabIndex={0}
                  onKeyDown={(e) => e.key === "Enter" && setSelected(b.id)}>
                  <td><b>{b.guest?.is_blacklisted ? "⚑ " : ""}{b.guest?.name ?? "—"}</b><br /><span className="small muted">{b.guest?.phone}</span></td>
                  <td>{aptTitle(b.apartment_id)}</td>
                  <td>{fmtDay(localDate(b.start_at))} → {fmtDay(localDate(b.end_at))}</td>
                  <td><StatusBadge status={b.status} /></td>
                  <td>{SOURCES[b.source] ?? b.source}</td>
                  <td className="num">{money(b.total_price)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {selected !== null && (
        <BookingPanel bookingId={selected} aptTitle={aptTitle} onClose={() => setSelected(null)}
          onChanged={() => { void reload(); bumpPending(); }} />
      )}
    </>
  );
}

function user_exportLink() {
  const download = async () => {
    let url: string;
    try {
      url = await fetchBlobUrl("/export/bookings.csv");
    } catch {
      return; // выгрузка доступна только владельцу
    }
    const a = document.createElement("a");
    a.href = url;
    a.download = "konok-bookings.csv";
    a.click();
    URL.revokeObjectURL(url);
  };
  return <button className="btn" onClick={download}>Выгрузить в Excel (CSV)</button>;
}
