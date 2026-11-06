import { useMemo, useState } from "react";
import { MONTHS, WD, addDays, nightBusy, todayISO, weekday } from "../utils";

interface Props {
  busy: { start_at: string; end_at: string }[];
  checkIn: string | null;
  checkOut: string | null;
  onChange: (checkIn: string | null, checkOut: string | null) => void;
}

function monthDays(year: number, month: number): string[] {
  const days: string[] = [];
  const first = `${year}-${String(month + 1).padStart(2, "0")}-01`;
  for (let d = first; d.slice(0, 7) === first.slice(0, 7); d = addDays(d, 1)) days.push(d);
  return days;
}

/** Выбор заезда и выезда. Занятые ночи зачёркнуты; выезд можно поставить на день, когда начинается чужая бронь. */
export function DateRangePicker({ busy, checkIn, checkOut, onChange }: Props) {
  const today = todayISO();
  const [offset, setOffset] = useState(0);
  const months = useMemo(() => {
    const [y, m] = today.split("-").map(Number);
    return [0, 1].map((i) => {
      const idx = m - 1 + offset + i;
      return { year: y + Math.floor(idx / 12), month: ((idx % 12) + 12) % 12 };
    });
  }, [today, offset]);

  const isBusy = (d: string) => nightBusy(d, busy);
  const rangeFree = (a: string, b: string) => {
    for (let d = a; d < b; d = addDays(d, 1)) if (isBusy(d)) return false;
    return true;
  };

  const pick = (d: string) => {
    if (!checkIn || checkOut) {
      if (!isBusy(d)) onChange(d, null);
      return;
    }
    if (d > checkIn && rangeFree(checkIn, d)) onChange(checkIn, d);
    else if (!isBusy(d)) onChange(d, null);
  };

  return (
    <div className="stack">
      <div className="row between">
        <button type="button" className="btn btn-sm" onClick={() => setOffset((o) => Math.max(0, o - 1))}
          disabled={offset === 0} aria-label="Предыдущий месяц">←</button>
        <span className="small muted">
          {checkIn && !checkOut ? "Теперь выберите дату выезда" : "Выберите дату заезда"}
        </span>
        <button type="button" className="btn btn-sm" onClick={() => setOffset((o) => o + 1)} aria-label="Следующий месяц">→</button>
      </div>
      <div className="cal-months">
        {months.map(({ year, month }) => {
          const days = monthDays(year, month);
          const pad = weekday(days[0]);
          return (
            <div key={`${year}-${month}`} className="stack" style={{ gap: 6 }}>
              <h3>{MONTHS[month]} {year}</h3>
              <div className="cal-grid">
                {WD.map((w) => <span key={w} className="cal-wd">{w}</span>)}
                {Array.from({ length: pad }, (_, i) => <span key={`p${i}`} className="cal-day empty" />)}
                {days.map((d) => {
                  const past = d < today;
                  const busyNight = isBusy(d);
                  const canBeCheckout = !!checkIn && !checkOut && d > checkIn && rangeFree(checkIn, d);
                  const disabled = past || (busyNight && !canBeCheckout);
                  const edge = d === checkIn || d === checkOut;
                  const inRange = !!checkIn && !!checkOut && d > checkIn && d < checkOut;
                  const cls = ["cal-day", busyNight && !edge ? "busy" : "", inRange ? "in-range" : "", edge ? "edge" : ""]
                    .filter(Boolean).join(" ");
                  return (
                    <button key={d} type="button" className={cls} disabled={disabled} onClick={() => pick(d)}
                      aria-pressed={edge} aria-label={`${Number(d.slice(8))} ${MONTHS[month]}${busyNight ? ", занято" : ""}`}>
                      {Number(d.slice(8))}
                    </button>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
      {(checkIn || checkOut) && (
        <button type="button" className="btn btn-ghost btn-sm" style={{ alignSelf: "flex-start" }}
          onClick={() => onChange(null, null)}>Сбросить даты</button>
      )}
    </div>
  );
}
