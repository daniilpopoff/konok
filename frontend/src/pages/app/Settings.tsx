import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, mediaUrl } from "../../api";
import { useAuth } from "../../auth";
import { ErrorBox, Spinner, errText, useLoad } from "../../components/ui";
import type { AccountSettings, User } from "../../types";

export default function Settings() {
  const { user, refresh } = useAuth();
  const { data, error, setData } = useLoad(() => api<AccountSettings>("/settings"), []);
  const team = useLoad(() => api<User[]>("/team"), []);
  const [form, setForm] = useState({ name: "", payment_details: "" });
  const [saved, setSaved] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [code, setCode] = useState<string | null>(null);
  const [mgr, setMgr] = useState({ name: "", email: "", password: "" });
  const [mgrErr, setMgrErr] = useState<string | null>(null);
  const qrRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (data) setForm({ name: data.name, payment_details: data.payment_details });
  }, [data]);

  const save = async (e: FormEvent) => {
    e.preventDefault();
    setErr(null);
    try {
      setData(await api<AccountSettings>("/settings", { method: "PATCH", body: form }));
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
      void refresh();
    } catch (e2) {
      setErr(errText(e2));
    }
  };

  const uploadQr = async (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    try {
      const r = await api<{ payment_qr: string }>("/settings/payment-qr", { form: fd });
      if (data) setData({ ...data, payment_qr: r.payment_qr });
    } catch (e) {
      setErr(errText(e));
    }
  };

  const linkTelegram = async () => {
    const r = await api<{ code: string }>("/telegram/link-code", { method: "POST" });
    setCode(r.code);
  };

  const addManager = async (e: FormEvent) => {
    e.preventDefault();
    setMgrErr(null);
    try {
      await api("/team/managers", { body: mgr });
      setMgr({ name: "", email: "", password: "" });
      void team.reload();
    } catch (e2) {
      setMgrErr(errText(e2));
    }
  };

  if (!data) return error ? <ErrorBox error={error} /> : <Spinner />;

  return (
    <>
      <div className="page-head"><h1>Настройки</h1></div>
      <div className="stack-lg" style={{ maxWidth: 720 }}>
        <form className="card stack" onSubmit={save}>
          <h2>Бизнес и оплата</h2>
          <label className="field">Название для гостей<input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
          <p className="small muted">Витрина: <a href={`/${data.slug}`} target="_blank" rel="noreferrer">{window.location.origin}/{data.slug}</a></p>
          <label className="field">Реквизиты для предоплаты
            <textarea value={form.payment_details} placeholder={"MBank: +996 555 000 000 (Азамат Т.)\nOptima: 4169 …"}
              onChange={(e) => setForm({ ...form, payment_details: e.target.value })} />
            <span className="hint">Гость видит их на странице брони, пока не оплатил</span>
          </label>
          <div className="row">
            {data.payment_qr && <img src={mediaUrl(data.payment_qr)} alt="QR для оплаты" style={{ width: 120, borderRadius: 10 }} />}
            <input ref={qrRef} type="file" accept="image/png,image/jpeg,image/webp" hidden onChange={(e) => e.target.files?.[0] && void uploadQr(e.target.files[0])} />
            <button type="button" className="btn" onClick={() => qrRef.current?.click()}>{data.payment_qr ? "Заменить QR" : "Загрузить QR для оплаты"}</button>
          </div>
          <ErrorBox error={err} />
          <div className="row"><button className="btn btn-primary">Сохранить</button>{saved && <span className="notice">Сохранено</span>}</div>
        </form>

        <section className="card stack">
          <h2>Telegram</h2>
          <p className="muted">Сюда приходят новые брони и чеки с кнопками «Подтвердить / Отклонить».</p>
          {user?.telegram_linked ? <p className="notice">Telegram подключён</p> : (
            <>
              <button className="btn" style={{ alignSelf: "flex-start" }} onClick={linkTelegram}>Получить код привязки</button>
              {code && <p>Откройте бота Konok в Telegram и отправьте: <span className="copy">/start {code}</span></p>}
            </>
          )}
        </section>

        <section className="card stack">
          <h2>Команда</h2>
          <p className="muted small">Менеджер ведёт брони, шахматку и гостей, но не видит аналитику, расходы и настройки.</p>
          {team.data?.map((u) => (
            <div key={u.id} className="row between small"><span><b>{u.name}</b> · {u.email}</span><span className="muted">{u.role === "owner" ? "владелец" : "менеджер"}</span></div>
          ))}
          <form className="stack" onSubmit={addManager}>
            <div className="grid-2">
              <label className="field">Имя<input required value={mgr.name} onChange={(e) => setMgr({ ...mgr, name: e.target.value })} /></label>
              <label className="field">Email<input required type="email" value={mgr.email} onChange={(e) => setMgr({ ...mgr, email: e.target.value })} /></label>
            </div>
            <label className="field">Пароль для входа<input required minLength={8} type="text" value={mgr.password} onChange={(e) => setMgr({ ...mgr, password: e.target.value })} />
              <span className="hint">Передайте менеджеру email и пароль</span></label>
            <ErrorBox error={mgrErr} />
            <button className="btn" style={{ alignSelf: "flex-start" }}>Добавить менеджера</button>
          </form>
        </section>
      </div>
    </>
  );
}
