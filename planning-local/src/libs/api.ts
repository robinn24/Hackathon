export const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

/**
 * Appelle l'API :
 * - si tu as mis un proxy /api → serveur (next.config.js), passe juste des paths style "/api/…"
 * - sinon, mets NEXT_PUBLIC_API_BASE_URL dans .env.local (ex: http://192.168.1.50:5000)
 */
export async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API}${path}`; // si API="", alors path doit déjà commencer par /api/…
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

