import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { api } from "../../api";
import { useAuth } from "../../auth";
import { ErrorBox, Logo, errText } from "../../components/ui";

export function Home() {
  const { user } = useAuth();
  return (
    <>
      <header className="topbar">
        <Logo />
        <div className="row">
          {user ? <Link className="btn btn-primary" to="/app">Открыть CRM</Link> : (
            <>
              <Link className="btn btn-ghost" to="/login">Войти</Link>
              <Link className="btn btn-primary" to="/register">Попробовать</Link>
            </>
          )}
        </div>
      </header>
      <main className="page stack-lg" style={{ paddingTop: 64 }}>
        <div className="stack" style={{ maxWidth: 680, gap: 16 }}>
          <h1 style={{ fontSize: 44, lineHeight: 1.1 }}>Все ваши квартиры, брони и деньги — в одной ссылке</h1>
          <p style={{ fontSize: 18 }} className="muted">
            Вставьте ссылку в объявление на Lalafo или в Instagram. Гость сам выберет даты, внесёт предоплату и загрузит чек,
            а вы подтвердите оплату в Telegram одной кнопкой.
          </p>
          <div className="row">
            <Link className="btn btn-primary" to="/register">Создать кабинет бесплатно</Link>
            <Link className="btn" to="/azamat">Посмотреть демо-витрину</Link>
          </div>
        </div>
        <div className="grid-auto">
          {[
            ["Без двойных броней", "Даты блокируются, пока гость платит. Две брони на одни даты невозможны."],
            ["Подтверждение в Telegram", "Чек приходит в бот — нажали «Подтвердить», гостю открылся адрес."],
            ["Видно, что приносит деньги", "Загрузка, выручка и прибыль по каждой квартире и по источникам."],
          ].map(([t, d]) => (
            <div key={t} className="card stack" style={{ gap: 6 }}><h3>{t}</h3><p className="muted">{d}</p></div>
          ))}
        </div>
      </main>
    </>
  );
}

export function Login() {
  const { login, user } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: "", password: "" });
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  if (user) return <Navigate to="/app" replace />;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      const r = await api<{ access_token: string }>("/auth/login", { body: form, auth: false });
      await login(r.access_token);
      navigate("/app");
    } catch (e2) {
      setErr(errText(e2));
      setBusy(false);
    }
  };

  return (
    <main className="page-narrow" style={{ paddingTop: 64 }}>
      <form className="card stack" onSubmit={submit}>
        <Logo />
        <h1>Вход</h1>
        <label className="field">Email
          <input type="email" required autoComplete="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
        </label>
        <label className="field">Пароль
          <input type="password" required autoComplete="current-password" value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })} />
        </label>
        <ErrorBox error={err} />
        <button className="btn btn-primary" disabled={busy}>{busy ? "Входим…" : "Войти"}</button>
        <p className="small muted">Нет кабинета? <Link to="/register">Зарегистрироваться</Link></p>
        <p className="small muted">Демо: azamat@konok.kg / password123</p>
      </form>
    </main>
  );
}

export function Register() {
  const { login, user } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: "", business_name: "", slug: "", email: "", password: "" });
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  if (user) return <Navigate to="/app" replace />;

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      const r = await api<{ access_token: string }>("/auth/register", { body: form, auth: false });
      await login(r.access_token);
      navigate("/app/apartments?new=1");
    } catch (e2) {
      setErr(errText(e2));
      setBusy(false);
    }
  };

  return (
    <main className="page-narrow" style={{ paddingTop: 48 }}>
      <form className="card stack" onSubmit={submit}>
        <Logo />
        <h1>Новый кабинет</h1>
        <label className="field">Ваше имя<input required value={form.name} onChange={set("name")} /></label>
        <label className="field">Название для гостей
          <input required placeholder="Квартиры Азамата" value={form.business_name} onChange={set("business_name")} />
        </label>
        <label className="field">Адрес витрины
          <input required pattern="[a-z0-9][a-z0-9\-]{1,38}[a-z0-9]" placeholder="azamat" value={form.slug}
            onChange={(e) => setForm({ ...form, slug: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "") })} />
          <span className="hint">konok.kg/{form.slug || "ваш-логин"} — латиница, цифры и дефис, 3–40 символов</span>
        </label>
        <label className="field">Email<input type="email" required autoComplete="email" value={form.email} onChange={set("email")} /></label>
        <label className="field">Пароль
          <input type="password" required minLength={8} autoComplete="new-password" value={form.password} onChange={set("password")} />
          <span className="hint">Минимум 8 символов</span>
        </label>
        <ErrorBox error={err} />
        <button className="btn btn-primary" disabled={busy}>{busy ? "Создаём…" : "Создать кабинет"}</button>
        <p className="small muted">Уже есть кабинет? <Link to="/login">Войти</Link></p>
      </form>
    </main>
  );
}
