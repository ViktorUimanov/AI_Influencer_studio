const pageDefaults = {
  dashboard: { page: "dashboard", id: "" },
  influencers: { page: "influencers", id: "" },
  trends: { page: "trends", id: "" },
  runs: { page: "runs", id: "" },
  library: { page: "library", id: "" },
  settings: { page: "settings", id: "" },
  createInfluencer: { page: "createInfluencer", id: "" },
};

export function parseRoute(hash) {
  const clean = hash.replace(/^#\/?/, "");
  if (!clean) return pageDefaults.dashboard;
  const parts = clean.split("/").filter(Boolean);

  if (parts[0] === "influencer" && parts[1]) {
    return { page: "influencerDetail", id: decodeURIComponent(parts[1]) };
  }
  if (parts[0] === "run" && parts[1]) {
    return { page: "runDetail", id: decodeURIComponent(parts[1]) };
  }
  if (parts[0] === "create-influencer") {
    return pageDefaults.createInfluencer;
  }

  return pageDefaults[parts[0]] || pageDefaults.dashboard;
}

export function navigate(path) {
  window.location.hash = path;
}

export function resolveMediaPath(path) {
  if (!path) return "";
  if (path.startsWith("blob:") || path.startsWith("data:") || path.startsWith("http")) {
    return path;
  }
  if (import.meta.env.DEV && path.startsWith("/") && !path.startsWith("/@fs/") && !path.startsWith("/api/")) {
    return `/@fs${path}`;
  }
  if (import.meta.env.DEV && path.startsWith("../backend/data/")) {
    const filePath = path.replace("../backend/data/", "");
    return `/@fs${__BACKEND_DATA_ROOT__}/${filePath}`;
  }
  return path.replace("../", "/");
}

export function formatDateTime(value) {
  if (!value) return "Unknown";
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

export function formatShortDate(value) {
  if (!value) return "Unknown";
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
  }).format(new Date(value));
}

export function formatRelative(value) {
  if (!value) return "Unknown";
  const diffMs = new Date(value).getTime() - Date.now();
  const minutes = Math.round(diffMs / 60000);
  const rtf = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
  const units = [
    ["day", 60 * 24],
    ["hour", 60],
    ["minute", 1],
  ];
  for (const [unit, amount] of units) {
    if (Math.abs(minutes) >= amount || unit === "minute") {
      return rtf.format(Math.round(minutes / amount), unit);
    }
  }
  return "just now";
}

export function compactNumber(value) {
  return new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 }).format(value || 0);
}

export function titleCase(value) {
  return String(value || "")
    .replace(/([A-Z])/g, " $1")
    .replace(/[-_]/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

export function initials(value) {
  return String(value || "")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() || "")
    .join("");
}

export function pluralize(count, singular, plural = `${singular}s`) {
  return `${count} ${count === 1 ? singular : plural}`;
}

export function statusTone(status) {
  const value = String(status || "").toLowerCase();
  if (["running", "processing"].includes(value)) return "running";
  if (["queued", "draft"].includes(value)) return "queued";
  if (["completed", "active"].includes(value)) return "success";
  if (["failed", "error"].includes(value)) return "danger";
  return "neutral";
}

export function buildWorkspaceSummary(workspace) {
  const influencers = workspace?.influencers || [];
  const runs = workspace?.runs || [];
  const assets = workspace?.assets || [];
  return {
    influencerCount: influencers.length,
    activeRunCount: runs.filter((run) => ["Running", "Queued"].includes(run.status)).length,
    recentOutputCount: assets.filter((asset) => asset.kind === "output").length,
    failedRunCount: runs.filter((run) => run.status === "Failed").length,
  };
}

export function matchesQuery(query, values) {
  if (!query) return true;
  const term = query.trim().toLowerCase();
  return values.some((value) => String(value || "").toLowerCase().includes(term));
}

export function sortByDateDesc(items, field = "createdAt") {
  return [...items].sort((a, b) => new Date(b[field] || 0).getTime() - new Date(a[field] || 0).getTime());
}
