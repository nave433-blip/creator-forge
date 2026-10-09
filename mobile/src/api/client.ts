/**
 * Thin HTTP client for the CreatorForge FastAPI backend.
 * Every call needs the backend base URL and, if the backend was started
 * with `dashboard.api_token` set, the matching bearer token.
 */

export interface BackendSettings {
  /** e.g. "http://192.168.1.5:8765" -- no trailing slash */
  baseUrl: string;
  /** optional bearer token */
  apiToken: string;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

/* ---- API shapes (mirror forge/dashboard/app.py) ---- */

export interface CatalogItem {
  id: number;
  path: string;
  kind: string;
  mime: string;
  width: number | null;
  height: number | null;
  duration: number | null;
  tags: string[];
  notes: string;
}

export interface ChatDraft {
  id: number;
  platform: string;
  sender: string;
  incoming: string;
  reply: string;
  trigger: string;
  status: string;
}

export interface IdentityStatus {
  status: 'valid' | 'invalid' | 'missing';
  name?: string;
  signer?: string;
  date?: string;
  scope?: string;
  detail?: string;
}

export interface PostingPacket {
  dir: string;
  platform: string;
  title: string;
  scheduled_for: string;
  status: string;
  created: string;
}

/* ---- transport ---- */

function normalizeBase(url: string): string {
  return url.trim().replace(/\/+$/, '');
}

async function request<T>(
  settings: BackendSettings,
  path: string,
  init?: RequestInit,
): Promise<T> {
  if (!settings.baseUrl) {
    throw new ApiError(0, 'Backend URL is not configured. Open Setup first.');
  }
  let res: Response;
  try {
    res = await fetch(`${normalizeBase(settings.baseUrl)}${path}`, {
      ...init,
      headers: {
        'Content-Type': 'application/json',
        ...(settings.apiToken
          ? { Authorization: `Bearer ${settings.apiToken}` }
          : {}),
        ...((init && init.headers) || {}),
      },
    });
  } catch (e) {
    throw new ApiError(
      0,
      `Could not reach the backend at ${settings.baseUrl}. ` +
        `Is "forge dashboard" running and is the phone on the same network? (${String(e)})`,
    );
  }
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new ApiError(res.status, text || `HTTP ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const apiGet = <T>(
  s: BackendSettings,
  path: string,
): Promise<T> => request<T>(s, path, { method: 'GET' });

export const apiPost = <T>(
  s: BackendSettings,
  path: string,
): Promise<T> => request<T>(s, path, { method: 'POST' });

/* ---- typed endpoints ---- */

export const getCatalog = (s: BackendSettings, q?: string, kind?: string) => {
  const params = new URLSearchParams({ limit: '100' });
  if (q) params.set('q', q);
  if (kind) params.set('kind', kind);
  return apiGet<{ count: number; items: CatalogItem[] }>(
    s,
    `/catalog?${params.toString()}`,
  );
};

export const getIdentity = (s: BackendSettings) =>
  apiGet<IdentityStatus>(s, '/identity');

export const getChatQueue = (s: BackendSettings) =>
  apiGet<{ pending: ChatDraft[]; all: ChatDraft[] }>(s, '/chat/queue');

export const approveDraft = (s: BackendSettings, id: number) =>
  apiPost<{ id: number; status: string }>(s, `/chat/approve/${id}`);

export const rejectDraft = (s: BackendSettings, id: number) =>
  apiPost<{ id: number; status: string }>(s, `/chat/reject/${id}`);

export const markDraftSent = (s: BackendSettings, id: number) =>
  apiPost<{ id: number; status: string }>(s, `/chat/sent/${id}`);

export const getPayLinks = (s: BackendSettings) =>
  apiGet<{ links: Record<string, string> }>(s, '/pay/links');

export const getPackets = (s: BackendSettings) =>
  apiGet<{ packets: PostingPacket[] }>(s, '/post/packets');
