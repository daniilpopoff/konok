import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, mediaUrl } from "../../api";
import { DateRangePicker } from "../../components/DateRangePicker";
import { ErrorBox, Logo, Spinner, Stars, errText, useLoad } from "../../components/ui";
import type { GuestBooking, PublicApartment, Quote } from "../../types";
import { fmtDay, fmtTime, money, nightsWord, sourceFromUrl } from "../../utils";

export default function ApartmentPage() {
  const { slug = "", apt = "" } = useParams();
  const navigate = useNavigate();
  const { data, error, loading } = useLoad(() => api<PublicApartment>(`/public/${slug}/${apt}`, { auth: false }), [slug, apt]);
  const [checkIn, setCheckIn] = useState<string | null>(null);
  const [checkOut, setCheckOut] = useState<string | null>(null);
  const [quote, setQuote] = useState<Quote | null>(null);
  const [quoteErr, setQuoteErr] = useState<string | null>(null);
  const [step, setStep] = useState<"dates" | "form">("dates");
  const [form, setForm] = useState({ name: "", phone: "", guests: 1, consent: false });
  const [submitErr, setSubmitErr] = useState<string | null>(null);
  const [sending, setSending] = useState(false);

  useEffect(() => {
    setQuote(null);
    setQuoteErr(null);
    if (!checkIn || !checkOut) return;
    api<Quote>(`/public/${slug}/${apt}/quote`, { body: { check_in: checkIn, check_out: checkOut }, auth: false })
      .then(setQuote)
      .catch((e) => setQuoteErr(errText(e)));
  }, [checkIn, checkOut, slug, apt]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!checkIn || !checkOut) return;
    setSending(true);
    setSubmitErr(null);
    try {
      const b = await api<GuestBooking>(`/public/${slug}/${apt}/bookings`, {
        auth: false,
        body: { check_in: checkIn, check_out: checkOut, guests_count: form.guests, name: form.name, phone: form.phone,
          consent: form.consent, source: sourceFromUrl() },
      });
      navigate(`/b/${b.token}`);
    } catch (err) {
      setSubmitErr(errText(err));
      setSending(false);
    }
  };

  if (loading) return <Spinner />;
  if (error || !data) return <main className="page"><ErrorBox error={error ?? "Квартира не найдена"} /></main>;

  const photos = data.photos;
  const ready = !!quote && !quoteErr;

  const bookingBox = (
    <div className="card stack">
      <div className="row between">
        <p><b style={{ fontSize: 22 }}>{money(data.price_per_night)}</b> <span className="muted">/ сутки</span></p>
        {data.rating !== null && <span className="small"><Stars value={data.rating} /> {data.rating.toFixed(1)}</span>}
      </div>
      {step === "dates" ? (
        <>
          <p className="small muted">
            {checkIn ? `${fmtDay(checkIn)} → ${checkOut ? fmtDay(checkOut) : "…"}` : "Выберите даты в календаре"}
          </p>
          <ErrorBox error={quoteErr} />
          {quote && (
            <div className="stack" style={{ gap: 6 }}>
              {summarize(quote).map((l) => (
                <div key={l.label} className="row between small"><span>{l.label}</span><span>{money(l.sum)}</span></div>
              ))}
              <div className="row between"><b>Итого за {quote.nights} {nightsWord(quote.nights)}</b><b>{money(quote.total)}</b></div>
              <p className="small muted">
                Сейчас — предоплата {money(quote.prepayment)}. Остаток{Number(quote.deposit) > 0 ? ` и залог ${money(quote.deposit)}` : ""} —
                при передаче ключей.
              </p>
            </div>
          )}
          <button className="btn btn-primary btn-block" disabled={!ready} onClick={() => setStep("form")}>Забронировать</button>
        </>
      ) : (
        <form className="stack" onSubmit={submit}>
          <button type="button" className="btn btn-ghost btn-sm" style={{ alignSelf: "flex-start" }}
            onClick={() => setStep("dates")}>← Изменить даты</button>
          <p className="small"><b>{fmtDay(checkIn!)} → {fmtDay(checkOut!)}</b> · {money(quote!.total)}</p>
          <label className="field">Ваше имя
            <input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} autoComplete="name" />
          </label>
          <label className="field">Телефон или WhatsApp
            <input required type="tel" placeholder="+996 555 123 456" value={form.phone} autoComplete="tel"
              onChange={(e) => setForm({ ...form, phone: e.target.value })} />
          </label>
          <label className="field">Сколько гостей
            <input type="number" min={1} max={data.max_guests} value={form.guests}
              onChange={(e) => setForm({ ...form, guests: Number(e.target.value) })} />
            <span className="hint">Максимум {data.max_guests}</span>
          </label>
          <label className="check">
            <input type="checkbox" checked={form.consent} onChange={(e) => setForm({ ...form, consent: e.target.checked })} />
            Согласен на обработку персональных данных
          </label>
          <ErrorBox error={submitErr} />
          <button className="btn btn-primary btn-block" disabled={!form.consent || sending}>
            {sending ? "Бронируем…" : `Перейти к оплате ${money(quote!.prepayment)}`}
          </button>
          <p className="small muted">Даты держатся за вами 30 минут, пока вы оплачиваете и загружаете чек.</p>
        </form>
      )}
    </div>
  );

  return (
    <>
      <header className="topbar">
        <Logo />
        <Link to={`/${slug}`} className="small">Все квартиры владельца</Link>
      </header>
      <main className="page stack-lg">
        <div className="gallery">
          <div className="cover">{photos[0] ? <img src={mediaUrl(photos[0])} alt={data.title} /> : <span>Фото скоро будет</span>}</div>
          <div className="gallery-side">
            {[1, 2].map((i) => (
              <div key={i} className="cover">{photos[i] ? <img src={mediaUrl(photos[i])} alt="" /> : null}</div>
            ))}
          </div>
        </div>
        <div className="apt-layout">
          <div className="stack-lg">
            <div className="stack" style={{ gap: 6 }}>
              <h1>{data.title}</h1>
              <p className="muted">
                {data.district || "Бишкек"} · до {data.max_guests} гостей · заезд с {fmtTime(data.check_in_time)}, выезд до {fmtTime(data.check_out_time)}
                {data.min_nights > 1 && ` · от ${data.min_nights} ${nightsWord(data.min_nights)}`}
              </p>
            </div>
            {data.amenities.length > 0 && (
              <div className="chips">{data.amenities.map((a) => <span key={a} className="chip">{a}</span>)}</div>
            )}
            {data.description && <p style={{ whiteSpace: "pre-line" }}>{data.description}</p>}
            <section className="card stack">
              <h2>Свободные даты</h2>
              <DateRangePicker busy={data.busy} checkIn={checkIn} checkOut={checkOut}
                onChange={(a, b) => { setCheckIn(a); setCheckOut(b); setStep("dates"); }} />
              {data.weekend_price && (
                <p className="small muted">Ночи с пятницы и субботы — {money(data.weekend_price)}</p>
              )}
            </section>
            {data.rules && (
              <section className="stack"><h2>Правила</h2><p style={{ whiteSpace: "pre-line" }}>{data.rules}</p></section>
            )}
            <section className="stack">
              <h2>Условия отмены</h2>
              <p>Бесплатно — не позднее чем за {data.free_cancel_days} сут. до заезда: предоплата возвращается. Позже предоплата не возвращается.</p>
            </section>
            <section className="stack">
              <h2>Отзывы{data.reviews.length ? ` · ${data.reviews.length}` : ""}</h2>
              <p className="small muted">Отзыв может оставить только гость, который реально жил здесь.</p>
              {data.reviews.length === 0 && <p className="muted">Отзывов пока нет</p>}
              {data.reviews.map((r, i) => (
                <div key={i} className="card card-tight stack" style={{ gap: 6 }}>
                  <div className="row between"><b>{r.guest_name}</b><Stars value={r.rating} /></div>
                  {r.text && <p>{r.text}</p>}
                  {r.owner_reply && <p className="small muted">Ответ владельца: {r.owner_reply}</p>}
                </div>
              ))}
            </section>
          </div>
          <div className="sticky" id="book">{bookingBox}</div>
        </div>
      </main>
      <div className="mobile-bar">
        <div>
          <b>{quote ? money(quote.total) : `от ${money(data.price_per_night)}`}</b>
          <p className="small muted">{quote ? `${quote.nights} ${nightsWord(quote.nights)}` : "за сутки"}</p>
        </div>
        <a href="#book" className="btn btn-primary">{ready ? "Забронировать" : "Выбрать даты"}</a>
      </div>
    </>
  );
}

function summarize(q: Quote) {
  const groups: Record<string, { label: string; sum: number }> = {};
  const names = { regular: "Будни", weekend: "Выходные", special: "Особые даты" } as const;
  for (const n of q.breakdown) {
    const key = `${n.kind}-${n.price}`;
    groups[key] ??= { label: "", sum: 0 };
    groups[key].sum += Number(n.price);
  }
  return Object.entries(groups).map(([key, g]) => {
    const [kind, price] = key.split("-") as [keyof typeof names, string];
    const count = Math.round(g.sum / Number(price));
    return { label: `${names[kind]}: ${count} × ${money(price)}`, sum: g.sum };
  });
}
