const ALLOWED_NEXT_PATHS = new Set([
  "/quota-building",
  "/quota-building-pg",
  "/quota-a111",
  "/platform-account",
  "/platform-admin/users",
]);

export function safeNext(raw, fallback = "/quota-building") {
  if (!raw || !raw.startsWith("/") || raw.startsWith("//") || raw.includes("\\")) return fallback;
  let parsed;
  try {
    parsed = new URL(raw, location.origin);
  } catch {
    return fallback;
  }
  if (parsed.origin !== location.origin || !ALLOWED_NEXT_PATHS.has(parsed.pathname)) return fallback;
  return `${parsed.pathname}${parsed.search}${parsed.hash}`;
}

export function requestedNext(fallback = "/quota-building") {
  return safeNext(new URLSearchParams(location.search).get("next"), fallback);
}

export function withNext(path, next) {
  return `${path}?next=${encodeURIComponent(safeNext(next))}`;
}
