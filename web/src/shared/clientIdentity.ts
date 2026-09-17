const STORAGE_KEY = "personal-agent-workspace-id";
const configuredDefault = import.meta.env.VITE_CLIENT_ID?.trim().toLowerCase() || "local-demo";

export function getClientId() {
  return window.localStorage.getItem(STORAGE_KEY) || configuredDefault;
}

export function saveClientId(value: string) {
  const normalized = value.trim().toLowerCase();
  window.localStorage.setItem(STORAGE_KEY, normalized);
  return normalized;
}
