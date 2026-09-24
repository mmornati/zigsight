/**
 * Small, DOM free helpers shared by the ZigSight panel and cards.
 *
 * Rendering note: every device controlled string (friendly name, IEEE,
 * model, vendor, explanation, ...) is rendered through Lit templates, which
 * escape text. Never build HTML strings from API data.
 */

export const TYPE_LABELS = {
  coordinator: "Coordinator",
  router: "Router",
  end_device: "End device",
  unknown: "Unknown type",
};

export const TYPE_COLORS = {
  coordinator: "#1e88e5",
  router: "#43a047",
  end_device: "#fb8c00",
  unknown: "#8d8d8d",
};

export const ISSUE_COLOR = "#e53935";

export function typeLabel(type) {
  return TYPE_LABELS[type] || TYPE_LABELS.unknown;
}

export function typeColor(type) {
  return TYPE_COLORS[type] || TYPE_COLORS.unknown;
}

/** Link quality bucket: excellent / good / fair / poor / unknown. */
export function lqiLevel(lqi) {
  if (typeof lqi !== "number" || Number.isNaN(lqi)) return "unknown";
  if (lqi >= 200) return "excellent";
  if (lqi >= 150) return "good";
  if (lqi >= 100) return "fair";
  return "poor";
}

export const LQI_COLORS = {
  excellent: "#43a047",
  good: "#7cb342",
  fair: "#fb8c00",
  poor: "#e53935",
  unknown: "#9e9e9e",
};

export function lqiColor(lqi) {
  return LQI_COLORS[lqiLevel(lqi)];
}

export function healthStatus(score) {
  if (typeof score !== "number" || Number.isNaN(score)) return "Unknown";
  if (score >= 80) return "Healthy";
  if (score >= 50) return "Warning";
  return "Critical";
}

/** True if a device/node has a warning or a poor health score. */
export function hasIssues(item) {
  const analytics = item.analytics || item.analytics_metrics || {};
  return Boolean(
    analytics.connectivity_warning ||
      analytics.battery_drain_warning ||
      item.available === false ||
      (typeof item.health_score === "number" && item.health_score < 50) ||
      (typeof analytics.health_score === "number" && analytics.health_score < 50),
  );
}

export function formatNumber(value, digits = 0, suffix = "") {
  if (typeof value !== "number" || Number.isNaN(value)) return "—";
  return `${value.toFixed(digits)}${suffix}`;
}

export function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleString();
}

/** Human readable message of a failed `hass.callApi` call. */
export function apiErrorMessage(error) {
  if (!error) return "Unknown error";
  if (typeof error === "string") return error;
  return (
    error.body?.error ||
    error.body?.message ||
    error.error ||
    error.message ||
    (error.status_code ? `Request failed (${error.status_code})` : "Unknown error")
  );
}
