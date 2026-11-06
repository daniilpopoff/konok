// Тонкий клиент к FastAPI. Токен владельца/менеджера лежит в localStorage.

const TOKEN_KEY = "konok_token";

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* приватный режим браузера — просто не запоминаем */
  }
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function messageFrom(body: unknown, status: number): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail.length) {
      // ошибки валидации pydantic
      return detail
        .map((d) => (typeof d === "object" && d && "msg" in d ? String((d as { msg: unknown }).msg) : String(d)))
        .join("; ")
        .replace(/^Value error, /, "");
    }
  }
  if (status === 0) return "Нет связи с сервером";
  return `Ошибка сервера (${status})`;
}

type Options = { method?: string; body?: unknown; form?: FormData; auth?: boolean };

export async function api<T>(path: string, opts: Options = {}): Promise<T> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token && opts.auth !== false) headers.Authorization = `Bearer ${token}`;
  let body: BodyInit | undefined;
  if (opts.form) body = opts.form;
  else if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.body);
  }
  let res: Response;
  try {
    res = await fetch(`/api${path}`, { method: opts.method ?? (body ? "POST" : "GET"), headers, body });
  } catch {
    throw new ApiError(0, "Нет связи с сервером");
  }
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  let data: unknown = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }
  if (!res.ok) {
    if (res.status === 401 && token && opts.auth !== false) setToken(null);
    throw new ApiError(res.status, messageFrom(data, res.status));
  }
  return data as T;
}

/** Файл, доступный только по токену (чек), → временная ссылка для <img>/<a>. */
export async function fetchBlobUrl(path: string): Promise<string> {
  const res = await fetch(`/api${path}`, { headers: { Authorization: `Bearer ${getToken() ?? ""}` } });
  if (!res.ok) throw new ApiError(res.status, "Не удалось загрузить файл");
  return URL.createObjectURL(await res.blob());
}

export const mediaUrl = (path: string) => `/media/${path}`;
