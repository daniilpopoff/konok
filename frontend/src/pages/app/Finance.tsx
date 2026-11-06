import { useState, type FormEvent } from "react";
import { useOutletContext } from "react-router-dom";
import { api } from "../../api";
import { ErrorBox, Spinner, errText, useLoad } from "../../components/ui";
import type { Analytics as AnalyticsData, Expense } from "../../types";
import { EXPENSE_CATEGORIES, SOURCES, addDays, fmtDay, money, todayISO } from "../../utils";
import type { AppCtx } from "./AppLayout";

function monthStart(day: string) {
  return `${day.slice(0, 7)}-01`;
}
function monthEnd(day: string) {
  const [y, m] = day.split("-").map(Number);
  return addDays(`${m === 12 ? y + 1 : y}-${String(m === 12 ? 1 : m + 1).padStart(2, "0")}-01`, -1);
}

function PeriodPicker({ from, to, onChange }: { from: string; to: string; onChange: (f: string, t: string) => void }) {
  const today = todayISO();
  const presets: [string, string, string][] = [
    ["Этот месяц", monthStart(today), monthEnd(today)],
    ["Прошлый месяц", monthStart(addDays(monthStart(today), -1)), addDays(monthStart(today), -1)],
    ["30 дней", addDays(today, -29), today],
    ["След. 30 дней", today, addDays(today, 29)],
  ];
  return (
    <div className="row">
      {presets.map(([l, f, t]) => (
        <button key={l} className={`btn btn-sm ${from === f && to === t ? "btn-primary" : ""}`} onClick={() => onChange(f, t)}>{l}</button>
      ))}
      <input type="date" className="input" style={{ width: 160 }} value={from} onChange={(e) => onChange(e.target.value, to)} aria-label="С" />
      <input type="date" className="input" style={{ width: 160 }} value={to} onChange={(e) => onChange(from, e.target.value)} aria-label="По" />
    </div>
  );
}

export function Analytics() {
  const today = todayISO();
  const [from, setFrom] = useState(monthStart(today));
  const [to, setTo] = useState(monthEnd(today));
  const { data, error, loading } = useLoad(() => api<AnalyticsData>(`/analytics?date_from=${from}&date_to=${to}`), [from, to]);
  const maxRev = data ? Math.max(1, ...data.apartments.map((a) => Number(a.revenue))) : 1;
  const maxSrc = data ? Math.max(1, ...data.sources.map((s) => Number(s.revenue))) : 1;

  return (
    <>
      <div className="page-head">
        <h1>Аналитика</h1>
        <PeriodPicker from={from} to={to} onChange={(f, t) => { setFrom(f); setTo(t); }} />
      </div>
      <ErrorBox error={error} />
      {loading && !data && <Spinner />}
      {data && (
        <div className="stack-lg">
          <p className="muted small">{fmtDay(data.from)} — {fmtDay(data.to)} · {data.days} дн. Выручка учитывается по ночам, попавшим в период.</p>
          <div className="kpis">
            <div className="kpi"><p className="small muted">Загрузка</p><p className="v">{data.totals.occupancy_pct}%</p></div>
            <div className="kpi"><p className="small muted">Выручка</p><p className="v">{money(data.totals.revenue)}</p></div>
            <div className="kpi"><p className="small muted">Расходы</p><p className="v">{money(data.totals.expenses)}</p></div>
            <div className="kpi"><p className="small muted">Прибыль</p><p className="v" style={{ color: "var(--teal)" }}>{money(data.totals.profit)}</p></div>
            <div className="kpi"><p className="small muted">Средняя цена ночи</p><p className="v">{money(data.totals.avg_night_price)}</p></div>
            <div className="kpi"><p className="small muted">Отмены / неоплаты</p><p className="v">{data.totals.cancelled_pct}% / {data.totals.expired_pct}%</p></div>
          </div>
          <section className="stack">
            <h2>По квартирам</h2>
            <div className="table-wrap">
              <table>
                <thead><tr><th>Квартира</th><th className="num">Загрузка</th><th className="num">Ночей</th><th>Выручка</th>
                  <th className="num">Расходы</th><th className="num">Прибыль</th><th className="num">Ср. цена</th></tr></thead>
                <tbody>
                  {data.apartments.map((a) => (
                    <tr key={a.apartment_id}>
                      <td><b>{a.title}</b></td>
                      <td className="num">{a.occupancy_pct}%</td>
                      <td className="num">{a.nights}</td>
                      <td style={{ minWidth: 200 }}>
                        <div className="row" style={{ gap: 8, flexWrap: "nowrap" }}>
                          <div className="bar-track" style={{ flex: 1 }}><div className="bar-h" style={{ width: `${(100 * Number(a.revenue)) / maxRev}%` }} /></div>
                          <span className="small" style={{ whiteSpace: "nowrap" }}>{money(a.revenue)}</span>
                        </div>
                      </td>
                      <td className="num">{money(a.expenses)}</td>
                      <td className="num"><b>{money(a.profit)}</b></td>
                      <td className="num">{money(a.avg_night_price)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
          <section className="stack">
            <h2>Откуда приходят брони</h2>
            {data.sources.length === 0 && <p className="muted">За период подтверждённых броней нет</p>}
            <div className="card stack">
              {data.sources.map((s) => (
                <div key={s.source} className="stack" style={{ gap: 4 }}>
                  <div className="row between small"><b>{SOURCES[s.source] ?? s.source}</b><span>{s.bookings} бр. · {money(s.revenue)}</span></div>
                  <div className="bar-track"><div className="bar-h" style={{ width: `${(100 * Number(s.revenue)) / maxSrc}%`, background: "var(--sun)" }} /></div>
                </div>
              ))}
            </div>
          </section>
        </div>
      )}
    </>
  );
}

export function Expenses() {
  const { apartments, aptTitle } = useOutletContext<AppCtx>();
  const today = todayISO();
  const [from, setFrom] = useState(monthStart(today));
  const [to, setTo] = useState(monthEnd(today));
  const { data, error, loading, reload } = useLoad(() => api<Expense[]>(`/expenses?date_from=${from}&date_to=${to}`), [from, to]);
  const [f, setF] = useState({ apartment_id: 0, category: "cleaning", amount: "", spent_on: today, note: "" });
  const [err, setErr] = useState<string | null>(null);

  const add = async (e: FormEvent) => {
    e.preventDefault();
    setErr(null);
    try {
      await api("/expenses", { body: { ...f, apartment_id: f.apartment_id || apartments[0]?.id } });
      setF({ ...f, amount: "", note: "" });
      void reload();
    } catch (e2) {
      setErr(errText(e2));
    }
  };

  const remove = async (id: number) => {
    await api(`/expenses/${id}`, { method: "DELETE" });
    void reload();
  };

  const total = data?.reduce((s, x) => s + Number(x.amount), 0) ?? 0;

  return (
    <>
      <div className="page-head">
        <h1>Расходы</h1>
        <PeriodPicker from={from} to={to} onChange={(a, b) => { setFrom(a); setTo(b); }} />
      </div>
      <form className="card stack" style={{ marginBottom: 20 }} onSubmit={add}>
        <h3>Добавить расход</h3>
        <div className="row" style={{ alignItems: "flex-end" }}>
          <label className="field" style={{ minWidth: 200 }}>Квартира
            <select value={f.apartment_id || apartments[0]?.id || 0} onChange={(e) => setF({ ...f, apartment_id: Number(e.target.value) })}>
              {apartments.map((a) => <option key={a.id} value={a.id}>{a.title}</option>)}
            </select>
          </label>
          <label className="field">Категория
            <select value={f.category} onChange={(e) => setF({ ...f, category: e.target.value })}>
              {Object.entries(EXPENSE_CATEGORIES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </label>
          <label className="field" style={{ width: 140 }}>Сумма, сом<input required type="number" min={1} value={f.amount} onChange={(e) => setF({ ...f, amount: e.target.value })} /></label>
          <label className="field">Дата<input required type="date" value={f.spent_on} onChange={(e) => setF({ ...f, spent_on: e.target.value })} /></label>
          <label className="field" style={{ flex: 1, minWidth: 180 }}>Комментарий<input value={f.note} onChange={(e) => setF({ ...f, note: e.target.value })} /></label>
          <button className="btn btn-primary" disabled={!apartments.length}>Добавить</button>
        </div>
        <ErrorBox error={err} />
      </form>
      <ErrorBox error={error} />
      {loading && !data && <Spinner />}
      {data && data.length === 0 && <div className="card empty-state">За период расходов нет</div>}
      {data && data.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead><tr><th>Дата</th><th>Квартира</th><th>Категория</th><th>Комментарий</th><th className="num">Сумма</th><th /></tr></thead>
            <tbody>
              {data.map((x) => (
                <tr key={x.id}>
                  <td>{fmtDay(x.spent_on)}</td><td>{aptTitle(x.apartment_id)}</td><td>{EXPENSE_CATEGORIES[x.category]}</td>
                  <td className="muted">{x.note}</td><td className="num">{money(x.amount)}</td>
                  <td className="num"><button className="btn btn-ghost btn-sm btn-danger" onClick={() => remove(x.id)}>Удалить</button></td>
                </tr>
              ))}
              <tr><td colSpan={4}><b>Итого</b></td><td className="num"><b>{money(total)}</b></td><td /></tr>
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
