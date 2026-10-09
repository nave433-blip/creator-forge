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
  escalated: boolean;
  escalation_categories: string[];
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

export interface ScheduledPost {
  id: number;
  platform: string;
  packet_dir: string;
  title: string;
  scheduled_for: string;
  status: string;
  notes: string;
  is_due: boolean;
}

export interface AnalyticsTotals {
  total_earnings: number;
  posts_tracked: number;
  total_views: number;
  total_likes: number;
  total_comments: number;
  post_earnings: number;
}

export interface PlatformMonth {
  platform: string;
  month: string;
  currency: string;
  total: number;
  entries: number;
}

export interface ChatTemplate {
  name: string;
  category: string;
  text: string;
}

export interface SkillInfo {
  name: string;
  version: string;
  description: string;
  usage: string;
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
  init?: RequestInit,
): Promise<T> => request<T>(s, path, { method: 'POST', ...(init || {}) });

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

export const getSchedule = (s: BackendSettings) =>
  apiGet<{ scheduled: ScheduledPost[]; due_count: number; note: string }>(
    s,
    '/schedule',
  );

export const markScheduled = (s: BackendSettings, id: number, status = 'done') =>
  apiPost<{ id: number; status: string }>(
    s,
    `/schedule/mark/${id}?status=${encodeURIComponent(status)}`,
  );

export const getAnalytics = (s: BackendSettings) =>
  apiGet<{
    totals: AnalyticsTotals;
    by_platform_month: PlatformMonth[];
    recent_posts: unknown[];
  }>(s, '/analytics');

export const getSkills = (s: BackendSettings) =>
  apiGet<{ skills: SkillInfo[] }>(s, '/skills');

export const getTemplates = (s: BackendSettings) =>
  apiGet<{ templates: ChatTemplate[] }>(s, '/templates');

export const useTemplate = (
  s: BackendSettings,
  name: string,
  platform: string,
  sender: string,
) =>
  apiPost<{ draft_id: number; reply: string }>(
    s,
    `/templates/use/${encodeURIComponent(name)}`,
    { method: 'POST', body: JSON.stringify({ platform, sender }) },
  );

/* ---- spicy chat (consent-gated) + triage ---- */

export interface SpicyTier {
  tier: string;
  templates: { name: string; text: string }[];
}

export interface TriageItem {
  id: number;
  platform: string;
  sender: string;
  thumb: string;
  nsfw_label: string;
  nsfw_score: number;
  note: string;
  created: string;
}

export const getSpicyTemplates = (s: BackendSettings) =>
  apiGet<{ tiers: SpicyTier[] }>(s, '/chat/spicy/templates');

export const spicyDraft = (
  s: BackendSettings,
  platform: string,
  sender: string,
  text: string,
) =>
  apiPost<{ draft_id: number; reply: string; trigger: string; tier: string }>(
    s,
    '/chat/spicy/draft',
    { method: 'POST', body: JSON.stringify({ platform, sender, text }) },
  );

export const setSpicyTier = (
  s: BackendSettings,
  platform: string,
  sender: string,
  tier: string,
) =>
  apiPost<{ ok: boolean }>(s, '/chat/spicy/tier', {
    method: 'POST',
    body: JSON.stringify({ platform, sender, tier }),
  });

export const getTriage = (s: BackendSettings) =>
  apiGet<{ pending: TriageItem[] }>(s, '/chat/triage');

export const triageDecide = (
  s: BackendSettings,
  action: 'approve' | 'skip',
  id: number,
) => apiPost<{ id: number; status: string }>(s, `/chat/triage/${action}/${id}`);

/* ---- custom video orders ---- */

export interface VideoOrder {
  id: number;
  fan_handle: string;
  platform: string;
  scene_name: string;
  scene_path: string;
  price_label: string;
  price: string;
  status: string;
  video_job_id: number | null;
  output_path: string;
  delivery_note: string;
  created: string;
  updated: string;
}

export interface OrderableScene {
  name: string;
  path: string;
  mode: string;
  reason: string;
  orderable: boolean;
}

export const getOrders = (s: BackendSettings, status?: string) => {
  const q = status ? `?status=${encodeURIComponent(status)}` : '';
  return apiGet<{ orders: VideoOrder[] }>(s, `/orders${q}`);
};

export const orderAction = (
  s: BackendSettings,
  id: number,
  action: 'pay' | 'render' | 'review' | 'approve' | 'deliver' | 'cancel' | 'refund',
  extra?: Record<string, string>,
) =>
  apiPost<{ order: VideoOrder }>(s, `/orders/${id}/${action}`, {
    method: 'POST',
    body: JSON.stringify(extra || {}),
  });

export const getOrderableScenes = (s: BackendSettings) =>
  apiGet<{ scenes: OrderableScene[] }>(s, '/orders/scenes');

/* ---- live avatar ---- */

export interface LiveStatus {
  active: boolean;
  provider?: string;
  started_at?: string;
  info?: Record<string, unknown>;
}

export const getLiveStatus = (s: BackendSettings) =>
  apiGet<LiveStatus>(s, '/live');

export const liveStart = (
  s: BackendSettings,
  provider: string,
  extra?: Record<string, string>,
) =>
  apiPost<{ session?: unknown; provider?: string; guide?: string }>(
    s,
    '/live/start',
    { method: 'POST', body: JSON.stringify({ provider, ...(extra || {}) }) },
  );

export const liveStop = (s: BackendSettings) =>
  apiPost<{ stopped?: boolean; note?: string }>(s, '/live/stop');

/* ---- fan CRM ---- */

export interface Fan {
  platform: string;
  handle: string;
  tags: string[];
  notes: string;
  total_spend: number;
  purchase_count: number;
  message_count: number;
  status: string;
  first_seen: string;
  last_seen: string;
  last_purchase_at: string | null;
}

export interface BuyerIntent {
  score: number;
  reasons: string[];
  method: string;
}

export const getFans = (s: BackendSettings, platform?: string) =>
  apiGet<{ fans: Fan[] }>(
    s,
    '/crm' + (platform ? `?platform=${encodeURIComponent(platform)}` : ''),
  );

export const getFan = (s: BackendSettings, platform: string, handle: string) =>
  apiGet<Fan & { buyer_intent: BuyerIntent }>(
    s,
    `/crm/fan?platform=${encodeURIComponent(platform)}&handle=${encodeURIComponent(handle)}`,
  );

export const crmFanAction = (
  s: BackendSettings,
  body: Record<string, string | number>,
) => apiPost<{ fan: Fan }>(s, '/crm/fan', { method: 'POST', body: JSON.stringify(body) });

export const getSmartList = (s: BackendSettings, kind: string, platform?: string) =>
  apiGet<{ kind: string; fans: Fan[] }>(
    s,
    `/crm/smart/${encodeURIComponent(kind)}` +
      (platform ? `?platform=${encodeURIComponent(platform)}` : ''),
  );

export const getCrmStats = (s: BackendSettings) =>
  apiGet<{ stats: unknown[] }>(s, '/crm/stats');

/* ---- spicy livestream ---- */

export interface StreamPlatform {
  key: string;
  label: string;
  rtmp_ingest: boolean;
  rtmp_notes: string;
  chat_api: string;
  chat_notes: string;
  verification: string;
  tos_risk: string;
  payout_notes: string;
}

export interface StreamStatus {
  active: boolean;
  platform?: string;
  platform_label?: string;
  started_at?: string;
  avatar?: Record<string, unknown>;
  chat_mode?: string;
  checklist?: string[];
}

export const getStreamPlatforms = (s: BackendSettings) =>
  apiGet<{ platforms: StreamPlatform[] }>(s, '/stream/platforms');

export const getStreamStatus = (s: BackendSettings) =>
  apiGet<StreamStatus>(s, '/stream/status');

export const streamGoLive = (
  s: BackendSettings,
  body: { platform: string; avatar: string; avatar_source?: string; i_understand_the_risk: boolean },
) => apiPost<{ session: unknown }>(s, '/stream/go-live', { method: 'POST', body: JSON.stringify(body) });

export const streamStop = (s: BackendSettings) =>
  apiPost<{ stopped?: boolean; note?: string }>(s, '/stream/stop');

/* ---- chat flows / ppv / humanizer / compliance ---- */

export interface FlowRun {
  id: number;
  flow: string;
  platform: string;
  handle: string;
  step_idx: number;
  enrolled_at: string;
  due_at: string;
  status: string;
}

export const getFlowPending = (s: BackendSettings) =>
  apiGet<{ pending: FlowRun[] }>(s, '/chat/flows/pending');

export const enrollFlow = (s: BackendSettings, flow: string, platform: string, handle: string) =>
  apiPost<unknown>(s, '/chat/flows/enroll', {
    method: 'POST',
    body: JSON.stringify({ flow, platform, handle }),
  });

export const runFlows = (s: BackendSettings) =>
  apiPost<{ drafted: number; draft_ids: number[] }>(s, '/chat/flows/run');

export const draftPpv = (s: BackendSettings, platform: string, sender: string, text: string) =>
  apiPost<{ drafted: boolean; draft_id?: number; reply?: string; note?: string }>(
    s,
    '/chat/ppv',
    { method: 'POST', body: JSON.stringify({ platform, sender, text }) },
  );

export const previewHumanize = (s: BackendSettings, text: string) =>
  apiPost<{ original: string; humanized: string }>(
    s,
    '/chat/humanize',
    { method: 'POST', body: JSON.stringify({ text }) },
  );

export interface ComplianceFinding {
  category: string;
  match: string;
  detail: string;
}

export const checkCompliance = (s: BackendSettings, text: string) =>
  apiPost<{ clean: boolean; findings: ComplianceFinding[] }>(
    s,
    '/chat/check',
    { method: 'POST', body: JSON.stringify({ text }) },
  );

/* ---- content ideas / analytics additions ---- */

export interface ContentIdea {
  caption: string;
  hashtags: string;
  angle: string;
  tag: string;
  method: string;
}

export const getIdeas = (s: BackendSettings, count = 10) =>
  apiGet<{ ideas: ContentIdea[] }>(s, `/content/ideas?count=${count}`);

export interface LtvReport {
  total_earnings: number;
  fan_count: number;
  arpu: number;
  avg_ltv: number;
  median_fan_spend?: number;
  top_10pct_share?: number;
  method: string;
}

export const getLtv = (s: BackendSettings) =>
  apiGet<{ ltv: LtvReport; summary: string }>(s, '/analytics/ltv');

export interface PeakSlot {
  weekday: string;
  hour: number;
  posts: number;
  avg_engagement: number;
  note?: string;
}

export const getPeakTimes = (s: BackendSettings) =>
  apiGet<{ peak_times: PeakSlot[] }>(s, '/analytics/peak-times');

/* ---- tube sites (manual-assist) + word bank ---- */

export interface TubeSiteInfo {
  site: string;
  key: string;
  upload: string;
  verification: string;
  monetization: string;
}

export interface TubeMetadata {
  site: string;
  title: string;
  description: string;
  tags: string[];
  tags_truncated: boolean;
  notes: string[];
}

export const getTubeSites = (s: BackendSettings) =>
  apiGet<{ sites: TubeSiteInfo[] }>(s, '/tube/sites');

export const previewTubeMetadata = (
  s: BackendSettings,
  site: string,
  opts: { name?: string; tags?: string[] } = {},
) =>
  apiPost<TubeMetadata>(s, '/tube/metadata', {
    body: JSON.stringify({ site, name: opts.name || '', tags: opts.tags || [] }),
  });

export const buildTubePacket = (
  s: BackendSettings,
  video: string,
  site: string,
  opts: { name?: string; tags?: string[] } = {},
) =>
  apiPost<{ packet: string }>(s, '/tube/packet', {
    body: JSON.stringify({
      video,
      site,
      name: opts.name || '',
      tags: opts.tags || [],
    }),
  });

export interface LexiconEntry {
  term: string;
  note: string;
  added: number;
}

export const getLexicon = (s: BackendSettings) =>
  apiGet<{ categories: Record<string, LexiconEntry[]> }>(s, '/chat/lexicon');

export const addLexiconTerm = (
  s: BackendSettings,
  category: string,
  term: string,
  note = '',
) =>
  apiPost<{ added: boolean; category: string; term: string }>(
    s,
    '/chat/lexicon/add',
    { body: JSON.stringify({ category, term, note }) },
  );

export const removeLexiconTerm = (
  s: BackendSettings,
  category: string,
  term: string,
) =>
  apiPost<{ removed: boolean }>(s, '/chat/lexicon/remove', {
    body: JSON.stringify({ category, term }),
  });

export interface AIProviderStatus {
  provider: string;
  model: string;
  configured: boolean;
  docs: string;
}

export interface AIAnswer {
  provider: string;
  model: string;
  text: string;
  draft: boolean;
}

export const getAIProviders = (s: BackendSettings) =>
  apiGet<{ providers: AIProviderStatus[] }>(s, '/ai/providers');

export const aiAsk = (s: BackendSettings, body: Record<string, unknown>) =>
  apiPost<AIAnswer>(s, '/ai/ask', { body: JSON.stringify(body) });
