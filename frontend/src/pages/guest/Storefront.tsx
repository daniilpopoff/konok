import { Link, useParams } from "react-router-dom";
import { api, mediaUrl } from "../../api";
import { ErrorBox, Logo, Spinner, Stars, useLoad } from "../../components/ui";
import type { PublicAccount } from "../../types";
import { money } from "../../utils";

export default function Storefront() {
  const { slug = "" } = useParams();
  const src = new URLSearchParams(window.location.search).get("src");
  const { data, error, loading } = useLoad(() => api<PublicAccount>(`/public/${slug}`, { auth: false }), [slug]);

  return (
    <>
      <header className="topbar">
        <Logo />
        {data && <span className="muted small">{data.name}</span>}
      </header>
      <main className="page stack-lg">
        {loading && <Spinner />}
        <ErrorBox error={error} />
        {data && (
          <>
            <div className="stack" style={{ gap: 6 }}>
              <h1>{data.name}</h1>
              <p className="muted">Посуточная аренда · {data.apartments.length} кв. · бронь онлайн без звонков</p>
            </div>
            {data.apartments.length === 0 && <div className="empty-state">Квартир пока нет</div>}
            <div className="grid-auto">
              {data.apartments.map((a) => (
                <Link key={a.slug} to={`/${slug}/${a.slug}${src ? `?src=${src}` : ""}`} className="apt-card">
                  <div className="cover">
                    {a.cover ? <img src={mediaUrl(a.cover)} alt={a.title} /> : <span>Фото скоро будет</span>}
                  </div>
                  <div className="stack" style={{ padding: 16, gap: 6 }}>
                    <h3>{a.title}</h3>
                    <p className="small muted">
                      {a.district || "Бишкек"}
                      {a.rating !== null && <> · <Stars value={a.rating} /> {a.rating.toFixed(1)} ({a.reviews_count})</>}
                    </p>
                    <p><b>{money(a.price_per_night)}</b> <span className="muted small">/ сутки</span></p>
                  </div>
                </Link>
              ))}
            </div>
          </>
        )}
      </main>
    </>
  );
}
