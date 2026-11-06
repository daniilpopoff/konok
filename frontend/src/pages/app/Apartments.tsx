import { useRef, useState, type FormEvent } from "react";
import { useOutletContext, useSearchParams } from "react-router-dom";
import { api, mediaUrl } from "../../api";
import { useAuth } from "../../auth";
import { ErrorBox, Modal, errText } from "../../components/ui";
import type { Apartment } from "../../types";
import { money } from "../../utils";
import type { AppCtx } from "./AppLayout";

const EMPTY = {
  slug: "", title: "", district: "", address: "", description: "", amenities: "", rules: "", checkin_instructions: "",
  price_per_night: "", weekend_price: "", min_nights: 1, max_guests: 2, check_in_time: "14:00", check_out_time: "12:00",
  prepayment: "1000", deposit: "0", free_cancel_days: 3, is_active: true,
};
type FormState = typeof EMPTY;

function toForm(a: Apartment): FormState {
  return {
    slug: a.slug, title: a.title, district: a.district, address: a.address, description: a.description,
    amenities: a.amenities.join(", "), rules: a.rules, checkin_instructions: a.checkin_instructions,
    price_per_night: String(Number(a.price_per_night)), weekend_price: a.weekend_price ? String(Number(a.weekend_price)) : "",
    min_nights: a.min_nights, max_guests: a.max_guests, check_in_time: a.check_in_time.slice(0, 5),
    check_out_time: a.check_out_time.slice(0, 5), prepayment: String(Number(a.prepayment)), deposit: String(Number(a.deposit)),
    free_cancel_days: a.free_cancel_days, is_active: a.is_active,
  };
}

export default function Apartments() {
  const { apartments, reloadApartments, isOwner } = useOutletContext<AppCtx>();
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();
  const [editing, setEditing] = useState<Apartment | "new" | null>(params.get("new") ? "new" : null);
  const [copied, setCopied] = useState<string | null>(null);
  const base = `${window.location.origin}/${user?.account_slug ?? ""}`;

  const copy = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(text);
      setTimeout(() => setCopied(null), 1500);
    } catch { /* без доступа к буферу просто показываем ссылку */ }
  };

  const close = () => {
    setEditing(null);
    if (params.get("new")) setParams({});
  };

  return (
    <>
      <div className="page-head">
        <h1>Квартиры</h1>
        {isOwner && <button className="btn btn-primary" onClick={() => setEditing("new")}>+ Добавить квартиру</button>}
      </div>
      {apartments.length === 0 && <div className="card empty-state">Добавьте первую квартиру — и получите ссылку для объявления.</div>}
      <div className="stack">
        {apartments.map((a) => (
          <div key={a.id} className="card stack">
            <div className="row between">
              <div className="row">
                <div className="cover" style={{ width: 96, height: 72, borderRadius: 12, aspectRatio: "auto" }}>
                  {a.photos[0] ? <img src={mediaUrl(a.photos[0].path)} alt="" /> : <span className="small">нет фото</span>}
                </div>
                <div className="stack" style={{ gap: 2 }}>
                  <h3>{a.title} {!a.is_active && <span className="badge st-closed">скрыта</span>}</h3>
                  <p className="small muted">{a.district} · {money(a.price_per_night)}/сутки · до {a.max_guests} гостей · {a.photos.length} фото</p>
                </div>
              </div>
              {isOwner && <button className="btn btn-sm" onClick={() => setEditing(a)}>Редактировать</button>}
            </div>
            <div className="stack" style={{ gap: 6 }}>
              <p className="small muted">Ссылки для объявлений — по ним видно, откуда пришла бронь:</p>
              {[["Lalafo", "lalafo"], ["Instagram", "instagram"]].map(([label, src]) => {
                const link = `${base}/${a.slug}?src=${src}`;
                return (
                  <div key={src} className="row" style={{ gap: 8 }}>
                    <span className="small" style={{ width: 80 }}>{label}</span>
                    <span className="copy" style={{ flex: 1 }}>{link}</span>
                    <button className="btn btn-sm" onClick={() => copy(link)}>{copied === link ? "Скопировано" : "Копировать"}</button>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
      {editing && (
        <ApartmentForm apartment={editing === "new" ? null : editing} onClose={close}
          onSaved={async () => { await reloadApartments(); }} />
      )}
    </>
  );
}

function ApartmentForm({ apartment, onClose, onSaved }: { apartment: Apartment | null; onClose: () => void; onSaved: () => Promise<void> }) {
  const [f, setF] = useState<FormState>(apartment ? toForm(apartment) : EMPTY);
  const [current, setCurrent] = useState<Apartment | null>(apartment);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const set = <K extends keyof FormState>(k: K, v: FormState[K]) => setF({ ...f, [k]: v });

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    const body = {
      ...f,
      amenities: f.amenities.split(",").map((s) => s.trim()).filter(Boolean),
      weekend_price: f.weekend_price === "" ? null : f.weekend_price,
      check_in_time: `${f.check_in_time}:00`, check_out_time: `${f.check_out_time}:00`,
    };
    try {
      if (current) {
        const { slug: _slug, check_in_time: _a, check_out_time: _b, ...patch } = body;
        void _slug; void _a; void _b;
        setCurrent(await api<Apartment>(`/apartments/${current.id}`, { method: "PATCH", body: patch }));
      } else {
        setCurrent(await api<Apartment>("/apartments", { body }));
      }
      await onSaved();
      if (current) onClose();
    } catch (e2) {
      setErr(errText(e2));
    } finally {
      setBusy(false);
    }
  };

  const upload = async (files: FileList) => {
    if (!current) return;
    setBusy(true);
    setErr(null);
    try {
      let apt = current;
      for (const file of Array.from(files)) {
        const form = new FormData();
        form.append("file", file);
        apt = await api<Apartment>(`/apartments/${current.id}/photos`, { form });
      }
      setCurrent(apt);
      await onSaved();
    } catch (e) {
      setErr(errText(e));
    } finally {
      setBusy(false);
    }
  };

  const removePhoto = async (photoId: number) => {
    if (!current) return;
    await api(`/apartments/${current.id}/photos/${photoId}`, { method: "DELETE" });
    setCurrent(await api<Apartment>(`/apartments/${current.id}`));
    await onSaved();
  };

  return (
    <Modal onClose={onClose} label={apartment ? "Редактирование квартиры" : "Новая квартира"}>
      <div className="row between">
        <h2>{apartment ? apartment.title : current ? "Квартира создана — добавьте фото" : "Новая квартира"}</h2>
        <button className="btn btn-ghost btn-sm" onClick={onClose} aria-label="Закрыть">✕</button>
      </div>
      {current && (
        <section className="stack">
          <div className="row">
            {current.photos.map((p) => (
              <div key={p.id} className="stack" style={{ gap: 4 }}>
                <img src={mediaUrl(p.path)} alt="" style={{ width: 96, height: 72, objectFit: "cover", borderRadius: 10 }} />
                <button className="btn btn-ghost btn-sm btn-danger" onClick={() => removePhoto(p.id)}>Удалить</button>
              </div>
            ))}
          </div>
          <input ref={fileRef} type="file" multiple accept="image/png,image/jpeg,image/webp" hidden
            onChange={(e) => e.target.files && void upload(e.target.files)} />
          <button className="btn" disabled={busy} onClick={() => fileRef.current?.click()}>
            {busy ? "Загружаем…" : "Загрузить фото (до 20, по 10 МБ)"}
          </button>
        </section>
      )}
      <form className="stack" onSubmit={submit}>
        <label className="field">Название<input required value={f.title} placeholder="2-комнатная у ЦУМа" onChange={(e) => set("title", e.target.value)} /></label>
        {!apartment && (
          <label className="field">Адрес ссылки
            <input required pattern="[a-z0-9][a-z0-9\-]{1,38}[a-z0-9]" placeholder="tsum-2k" value={f.slug}
              onChange={(e) => set("slug", e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ""))} />
            <span className="hint">латиница, цифры и дефис — будет в ссылке для объявления</span>
          </label>
        )}
        <div className="grid-2">
          <label className="field">Район<input value={f.district} placeholder="Центр" onChange={(e) => set("district", e.target.value)} /></label>
          <label className="field">Точный адрес<input value={f.address} onChange={(e) => set("address", e.target.value)} />
            <span className="hint">гость увидит после подтверждения</span></label>
        </div>
        <div className="grid-2">
          <label className="field">Цена за сутки, сом<input required type="number" min={1} value={f.price_per_night} onChange={(e) => set("price_per_night", e.target.value)} /></label>
          <label className="field">Цена в пт и сб, сом<input type="number" min={1} placeholder="как в будни" value={f.weekend_price} onChange={(e) => set("weekend_price", e.target.value)} /></label>
          <label className="field">Предоплата, сом<input required type="number" min={0} value={f.prepayment} onChange={(e) => set("prepayment", e.target.value)} /></label>
          <label className="field">Залог, сом<input required type="number" min={0} value={f.deposit} onChange={(e) => set("deposit", e.target.value)} /></label>
          <label className="field">Гостей максимум<input type="number" min={1} value={f.max_guests} onChange={(e) => set("max_guests", Number(e.target.value))} /></label>
          <label className="field">Минимум ночей<input type="number" min={1} value={f.min_nights} onChange={(e) => set("min_nights", Number(e.target.value))} /></label>
          {!apartment && <>
            <label className="field">Заезд с<input type="time" value={f.check_in_time} onChange={(e) => set("check_in_time", e.target.value)} /></label>
            <label className="field">Выезд до<input type="time" value={f.check_out_time} onChange={(e) => set("check_out_time", e.target.value)} /></label>
          </>}
          <label className="field">Бесплатная отмена, за сколько суток<input type="number" min={0} value={f.free_cancel_days} onChange={(e) => set("free_cancel_days", Number(e.target.value))} /></label>
        </div>
        <label className="field">Удобства<input value={f.amenities} placeholder="Wi-Fi, Стиральная машина, Парковка" onChange={(e) => set("amenities", e.target.value)} />
          <span className="hint">через запятую</span></label>
        <label className="field">Описание<textarea value={f.description} onChange={(e) => set("description", e.target.value)} /></label>
        <label className="field">Правила<textarea value={f.rules} placeholder="Не курить, без вечеринок" onChange={(e) => set("rules", e.target.value)} /></label>
        <label className="field">Как заселиться<textarea value={f.checkin_instructions} placeholder="Ключ у консьержа, код домофона…" onChange={(e) => set("checkin_instructions", e.target.value)} />
          <span className="hint">гость увидит после подтверждения</span></label>
        <label className="check"><input type="checkbox" checked={f.is_active} onChange={(e) => set("is_active", e.target.checked)} />Показывать на витрине</label>
        <ErrorBox error={err} />
        <button className="btn btn-primary" disabled={busy}>{current ? "Сохранить" : "Создать квартиру"}</button>
      </form>
    </Modal>
  );
}
