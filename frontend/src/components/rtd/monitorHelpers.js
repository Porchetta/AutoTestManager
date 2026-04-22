export function displayTargetLineName(targetLine) {
  return String(targetLine || "").replace(/_TARGET\b/gi, "");
}

export function monitorStatusChip(item) {
  const ownerMatch = String(item.status_text || "").match(/\(([^)]+)\)\s*$/);
  const owner = ownerMatch?.[1] || "";

  if (item.compile?.status === "RUNNING") {
    return owner ? `Compiling [${owner}]` : "Compiling";
  }
  if (item.test?.status === "RUNNING") {
    return owner ? `Testing [${owner}]` : "Testing";
  }
  if (item.copy?.status === "RUNNING") {
    return owner ? `Copying [${owner}]` : "Copying";
  }
  if (
    item.compile?.status === "PENDING" ||
    item.test?.status === "PENDING" ||
    item.copy?.status === "PENDING"
  ) {
    return owner ? `대기 [${owner}]` : "대기";
  }
  return "대기";
}

export function monitorActionDisplay(status) {
  const normalized = String(status || "").toUpperCase();
  if (normalized === "DONE") return "✓";
  if (normalized === "FAIL") return "✕";
  return "";
}

export function monitorActionIconClass(status) {
  const normalized = String(status || "").toUpperCase();
  if (normalized === "DONE") return "is-success";
  if (normalized === "FAIL") return "is-fail";
  return "";
}

export function monitorDownloadDisplay(enabled) {
  return enabled ? "⬇" : "—";
}

export function monitorActionDetail(action) {
  if (!action || !action.message || action.message === "-") return "";
  if (action.status === "FAIL" || action.status === "DONE") return action.message;
  return "";
}

export function monitorActionClass(status) {
  if (status === "DONE") return "is-success";
  if (status === "FAIL") return "is-fail";
  if (status === "PENDING") return "is-pending";
  if (status === "RUNNING") return "is-running";
  return "is-idle";
}

export function showMonitorSpinner(status) {
  return status === "PENDING" || status === "RUNNING";
}
