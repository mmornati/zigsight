/**
 * Validation of manually entered Wi-Fi scan data for the channel
 * recommendation (mirrors the server side schema in api.py).
 */

export const WIFI_CHANNELS = Array.from({ length: 14 }, (_, index) => index + 1);
export const MAX_ACCESS_POINTS = 500;

function toNumber(value) {
  if (typeof value === "number") return value;
  if (typeof value === "string" && value.trim() !== "") return Number(value);
  return Number.NaN;
}

/**
 * Validate access points `{channel, rssi, ssid?}`.
 * Returns `{accessPoints, errors}`; `errors` is a list of messages.
 */
export function validateAccessPoints(items) {
  const errors = [];
  const accessPoints = [];
  if (!Array.isArray(items)) {
    return { accessPoints, errors: ["Expected a list of access points"] };
  }
  if (items.length > MAX_ACCESS_POINTS) {
    errors.push(`At most ${MAX_ACCESS_POINTS} access points are supported`);
  }
  items.forEach((item, index) => {
    const row = index + 1;
    if (!item || typeof item !== "object") {
      errors.push(`Entry ${row}: expected an object with channel and rssi`);
      return;
    }
    const channel = toNumber(item.channel);
    const rssi = toNumber(item.rssi);
    if (!Number.isInteger(channel) || channel < 1 || channel > 14) {
      errors.push(`Entry ${row}: Wi-Fi channel must be a whole number from 1 to 14`);
      return;
    }
    if (!Number.isFinite(rssi) || rssi < -120 || rssi > 0) {
      errors.push(`Entry ${row}: RSSI must be between -120 and 0 dBm`);
      return;
    }
    const accessPoint = { channel, rssi };
    const ssid = typeof item.ssid === "string" ? item.ssid.trim() : "";
    if (ssid) accessPoint.ssid = ssid.slice(0, 64);
    accessPoints.push(accessPoint);
  });
  if (!items.length) errors.push("Add at least one access point");
  return { accessPoints, errors };
}

/**
 * Parse pasted JSON: a list of access points or `{"access_points": [...]}`.
 */
export function parseWifiJson(text) {
  let data;
  try {
    data = JSON.parse(text);
  } catch (error) {
    return { accessPoints: [], errors: [`Invalid JSON: ${error.message}`] };
  }
  if (data && !Array.isArray(data) && Array.isArray(data.access_points)) {
    data = data.access_points;
  }
  return validateAccessPoints(data);
}
