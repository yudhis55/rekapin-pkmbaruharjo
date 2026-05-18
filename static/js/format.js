"use strict";

/**
 * Format a number as IDR currency: "Rp 250.000"
 */
function formatIDR(value) {
    if (value === null || value === undefined) return "-";
    const n = typeof value === "string" ? parseFloat(value) : value;
    if (Number.isNaN(n)) return "-";
    return new Intl.NumberFormat("id-ID", {
        style: "currency",
        currency: "IDR",
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
    }).format(n);
}

/**
 * Format a YYYY-MM-DD date string to a readable Indonesian format.
 */
function formatDate(isoDate) {
    if (!isoDate) return "-";
    try {
        const d = new Date(isoDate + "T00:00:00");
        return new Intl.DateTimeFormat("id-ID", {
            day: "2-digit",
            month: "short",
            year: "numeric",
        }).format(d);
    } catch (_e) {
        return isoDate;
    }
}

/**
 * Format an ISO datetime as "X menit lalu" (relative).
 */
function formatRelative(iso) {
    if (!iso) return "-";
    const t = new Date(iso);
    const now = new Date();
    const diffSec = Math.round((now - t) / 1000);
    if (diffSec < 60) return "Baru saja";
    const diffMin = Math.round(diffSec / 60);
    if (diffMin < 60) return `${diffMin} menit lalu`;
    const diffH = Math.round(diffMin / 60);
    if (diffH < 24) return `${diffH} jam lalu`;
    const diffD = Math.round(diffH / 24);
    if (diffD < 7) return `${diffD} hari lalu`;
    return new Intl.DateTimeFormat("id-ID", {
        day: "2-digit", month: "short", year: "numeric",
    }).format(t);
}

/**
 * Escape HTML for safe insertion into innerHTML.
 */
function escapeHtml(s) {
    if (s === null || s === undefined) return "";
    return String(s)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

window.RekapFormat = { formatIDR, formatDate, formatRelative, escapeHtml };
