import { useEffect, useState } from "react";
import { NavLink, Navigate, Outlet, useNavigate } from "react-router-dom";
import { api } from "../../api";
import { useAuth } from "../../auth";
import { Logo, Spinner } from "../../components/ui";
import type { Apartment, Booking } from "../../types";

export interface AppCtx {
  apartments: Apartment[];
  reloadApartments: () => Promise<void>;
  aptTitle: (id: number) => string;
  isOwner: boolean;
  bumpPending: () => void;
}

export default function AppLayout() {
  const { user, loading, logout } = useAuth();
  const navigate = useNavigate();
  const [apartments, setApartments] = useState<Apartment[]>([]);
  const [pending, setPending] = useState(0);
  const [tick, setTick] = useState(0);

  const reloadApartments = async () => {
    setApartments(await api<Apartment[]>("/apartments"));
  };

  useEffect(() => {
    if (user) void reloadApartments();
  }, [user]);

  useEffect(() => {
    if (!user) return;
    const load = () => api<Booking[]>("/bookings?status=awaiting_confirmation&limit=100")
      .then((b) => setPending(b.length)).catch(() => undefined);
    void load();
    const t = setInterval(load, 20000);
    return () => clearInterval(t);
  }, [user, tick]);

  if (loading) return <Spinner />;
  if (!user) return <Navigate to="/login" replace />;
  const isOwner = user.role === "owner";

  const links: [string, string, boolean][] = [
    ["/app", "Шахматка", true],
    ["/app/bookings", "Брони", true],
    ["/app/guests", "Гости", true],
    ["/app/reviews", "Отзывы", true],
    ["/app/apartments", "Квартиры", true],
    ["/app/analytics", "Аналитика", isOwner],
    ["/app/expenses", "Расходы", isOwner],
    ["/app/settings", "Настройки", isOwner],
  ];

  const ctx: AppCtx = {
    apartments,
    reloadApartments,
    aptTitle: (id) => apartments.find((a) => a.id === id)?.title ?? `Квартира #${id}`,
    isOwner,
    bumpPending: () => setTick((t) => t + 1),
  };

  return (
    <div className="app">
      <nav className="sidebar" aria-label="Разделы CRM">
        <Logo light to="/app" />
        {links.filter(([, , show]) => show).map(([to, label]) => (
          <NavLink key={to} to={to} end={to === "/app"} className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}>
            {label}
            {to === "/app/bookings" && pending > 0 && <span className="nav-count" aria-label={`${pending} ждут проверки`}>{pending}</span>}
          </NavLink>
        ))}
        <div className="sidebar-foot">
          <span>{user.name} · {isOwner ? "владелец" : "менеджер"}</span>
          {user.account_slug && <a href={`/${user.account_slug}`} target="_blank" rel="noreferrer" style={{ color: "#c9d3cf" }}>Моя витрина ↗</a>}
          <button onClick={() => { logout(); navigate("/login"); }}>Выйти</button>
        </div>
      </nav>
      <main className="main">
        <Outlet context={ctx} />
      </main>
    </div>
  );
}
