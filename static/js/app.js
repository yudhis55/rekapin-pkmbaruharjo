"use strict";

(function () {
    const { formatIDR, formatDate, formatRelative, escapeHtml } = window.RekapFormat;

    let currentJobId = null;
    let currentEventSource = null;
    let currentDisplayTanggal = null;
    let currentDisplayCaraBayar = null;

    // ----- DOM -----
    const els = {
        form: document.getElementById("scrape-form"),
        ruang: document.getElementById("ruang"),
        btnStart: document.getElementById("btn-start"),
        btnCancel: document.getElementById("btn-cancel"),
        progressCard: document.getElementById("progress-card"),
        progressBadge: document.getElementById("progress-badge"),
        progressLabel: document.getElementById("progress-label"),
        progressCount: document.getElementById("progress-count"),
        progressBar: document.getElementById("progress-bar"),
        progressLog: document.getElementById("progress-log"),
        visitsTbody: document.getElementById("visits-tbody"),
        recapTbody: document.getElementById("recap-tbody"),
        btnExport: document.getElementById("btn-export"),
        toast: document.getElementById("toast-container"),
    };

    // ----- Toast notifications -----
    function toast(message, kind) {
        const k = kind || "info";
        const colors = {
            info: "bg-blue-600",
            success: "bg-primary-600",
            error: "bg-red-600",
            warning: "bg-amber-600",
        };
        const div = document.createElement("div");
        div.className = (colors[k] || colors.info) + " text-white px-4 py-2 rounded-lg shadow-lg text-sm";
        div.textContent = message;
        els.toast.appendChild(div);
        setTimeout(function () { div.remove(); }, 4000);
    }

    // ----- Helper for export button -----
    function updateExportButton() {
        if (!els.btnExport) return;
        // Disable if tbody has no rows OR only has a placeholder (colspan) row
        const rows = els.visitsTbody.querySelectorAll("tr");
        const hasRealData = rows.length > 0 && !els.visitsTbody.querySelector("tr td[colspan]");
        els.btnExport.disabled = !hasRealData;
    }

    // ----- Mode toggle -----
    function syncMode() {
        const mode = els.form.querySelector("input[name='mode']:checked").value;
        document.querySelector("[data-mode-single]").classList.toggle("hidden", mode !== "single");
        const rangeEl = document.querySelector("[data-mode-range]");
        rangeEl.classList.toggle("hidden", mode !== "range");
        rangeEl.classList.toggle("grid", mode === "range");
    }

    els.form.querySelectorAll("input[name='mode']").forEach(function (r) {
        r.addEventListener("change", syncMode);
    });

    // ----- Load ruang -----
    async function loadRuang() {
        try {
            const r = await fetch("/api/ruang");
            const data = await r.json();
            for (const ruang of data.ruang) {
                const opt = document.createElement("option");
                opt.value = ruang;
                opt.textContent = ruang;
                els.ruang.appendChild(opt);
            }
        } catch (e) {
            toast("Gagal memuat daftar ruang", "error");
        }
    }

    // ----- Progress UI helpers -----
    function setBadge(kind, text) {
        const map = {
            running: "badge-info",
            done: "badge-success",
            error: "badge-error",
            cancelled: "badge-warning",
            pending: "badge-neutral",
        };
        els.progressBadge.className = map[kind] || "badge-neutral";
        els.progressBadge.textContent = text;
    }

    function appendLog(message) {
        const line = document.createElement("div");
        line.textContent = "[" + new Date().toLocaleTimeString("id-ID") + "] " + message;
        els.progressLog.appendChild(line);
        els.progressLog.scrollTop = els.progressLog.scrollHeight;
    }

    function resetProgress() {
        els.progressLabel.textContent = "Mempersiapkan...";
        els.progressCount.textContent = "0 / 0";
        els.progressBar.style.width = "0%";
        els.progressLog.innerHTML = "";
    }

    function updateProgress(current, total, label) {
        if (total > 0) {
            const pct = Math.round((current / total) * 100);
            els.progressBar.style.width = pct + "%";
            els.progressCount.textContent = current + " / " + total;
        }
        if (label) els.progressLabel.textContent = label;
    }

    // ----- Form submit -----
    els.form.addEventListener("submit", async function (e) {
        e.preventDefault();
        const mode = els.form.querySelector("input[name='mode']:checked").value;
        const ruang = els.ruang.value || null;
        const body = { mode: mode, ruang: ruang };
        const cara_bayar = document.getElementById("cara_bayar").value;
        body.cara_bayar = cara_bayar;
        if (mode === "single") {
            body.tanggal_from = document.getElementById("tanggal").value;
        } else {
            body.tanggal_from = document.getElementById("tanggal-from").value;
            body.tanggal_to = document.getElementById("tanggal-to").value;
        }

        try {
            const r = await fetch("/api/scrape", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body),
            });
            if (r.status === 409) {
                toast("Ada job lain sedang berjalan. Coba lagi nanti.", "warning");
                return;
            }
            if (r.status === 422) {
                const err = await r.json();
                toast("Validasi gagal: " + (err.detail || err.error), "error");
                return;
            }
            if (!r.ok) {
                toast("Gagal memulai scraping (" + r.status + ")", "error");
                return;
            }
            const data = await r.json();
            currentJobId = data.job_id;
            startScrapeFlow(currentJobId);
        } catch (e) {
            toast("Network error: " + e.message, "error");
        }
    });

    // ----- Scrape flow -----
    function startScrapeFlow(jobId) {
        els.progressCard.classList.remove("hidden");
        resetProgress();
        setBadge("running", "Berjalan");
        els.btnStart.disabled = true;
        els.btnCancel.disabled = false;
        appendLog("Job #" + jobId + " dimulai");

        currentEventSource = new EventSource("/api/scrape/" + jobId + "/stream");

        currentEventSource.addEventListener("log", function (ev) {
            const data = JSON.parse(ev.data);
            appendLog(data.message);
        });

        currentEventSource.addEventListener("progress", function (ev) {
            const data = JSON.parse(ev.data);
            updateProgress(data.current || 0, data.total || 0, data.message);
        });

        currentEventSource.addEventListener("done", async function (ev) {
            const data = JSON.parse(ev.data);
            setBadge("done", "Selesai");
            updateProgress(1, 1, data.message);
            appendLog("Selesai: " + data.message);
            toast("Scraping selesai", "success");
            closeStream();
            await refreshVisits();
            await refreshRecaps();
        });

        currentEventSource.addEventListener("error", async function (ev) {
            try {
                const data = JSON.parse(ev.data || "{}");
                if (data.message) {
                    setBadge("error", "Error");
                    appendLog("Error: " + data.message);
                    toast("Error: " + data.message, "error");
                }
            } catch (_e) { /* connection error - ignore */ }
            closeStream();
            await refreshRecaps();
        });

        currentEventSource.addEventListener("cancelled", function (ev) {
            const data = JSON.parse(ev.data);
            setBadge("cancelled", "Dibatalkan");
            appendLog("Dibatalkan: " + data.message);
            toast("Scraping dibatalkan", "warning");
            closeStream();
        });
    }

    function closeStream() {
        if (currentEventSource) {
            currentEventSource.close();
            currentEventSource = null;
        }
        els.btnStart.disabled = false;
        els.btnCancel.disabled = true;
    }

    // ----- Cancel -----
    els.btnCancel.addEventListener("click", async function () {
        if (!currentJobId) return;
        try {
            await fetch("/api/scrape/" + currentJobId + "/cancel", { method: "POST" });
        } catch (e) {
            toast("Gagal mengirim perintah batalkan", "error");
        }
    });

    // ----- Visits table -----
    async function loadVisitsForRange(tanggal_from, tanggal_to, ruang) {
        currentDisplayTanggal = tanggal_from;
        const cara_bayar_val = document.getElementById("cara_bayar")?.value;
        currentDisplayCaraBayar = cara_bayar_val || null;
        
        const params = new URLSearchParams({ tanggal_from });
        if (tanggal_to) params.set("tanggal_to", tanggal_to);
        if (ruang) params.set("ruang", ruang);
        const cara_bayar = document.getElementById("cara_bayar")?.value;
        if (cara_bayar && cara_bayar !== "SEMUA") params.set("cara_bayar", cara_bayar);
        const r = await fetch(`/api/visits?${params}`);
        if (!r.ok) {
            toast(`Gagal memuat data kunjungan (${r.status})`, "error");
            return;
        }
        const visits = await r.json();
        renderVisits(visits);
    }

    async function refreshVisits() {
        const mode = els.form.querySelector("input[name='mode']:checked").value;
        let from, to;
        if (mode === "single") {
            from = document.getElementById("tanggal").value;
            to = from;
        } else {
            from = document.getElementById("tanggal-from").value;
            to = document.getElementById("tanggal-to").value;
        }
        const ruang = els.ruang.value || null;
        await loadVisitsForRange(from, to, ruang);
    }

    function renderVisits(visits) {
        if (!visits.length) {
            els.visitsTbody.innerHTML = `
                <tr><td colspan="8" class="text-center text-sm text-ink-400 py-12">
                    Tidak ada kunjungan untuk filter ini.
                </td></tr>`;
            updateExportButton();
            return;
        }
        const rows = visits.map((v) => {
            // Tindakan column
            let tindakanHtml = '<span class="text-ink-400 text-xs">—</span>';
            if (v.treatments && v.treatments.length > 0) {
                const items = v.treatments.map(t =>
                    `<li class="flex justify-between gap-2 text-xs py-0.5">
                        <span class="flex-1">${escapeHtml(t.nama_tindakan)}</span>
                        <span class="badge-neutral text-xs">${escapeHtml(t.kategori || 'biasa')}</span>
                        <span class="font-medium">${formatIDR(t.biaya)}</span>
                    </li>`
                ).join("");
                tindakanHtml = `
                    <details class="text-sm">
                        <summary class="cursor-pointer text-primary-600 hover:text-primary-700 text-xs font-medium">
                            ${v.treatments.length} tindakan
                        </summary>
                        <ul class="mt-1 space-y-0.5 pl-2 border-l-2 border-ink-100">
                            ${items}
                        </ul>
                    </details>`;
            } else if (v.cara_bayar === "UMUM") {
                tindakanHtml = '<span class="text-ink-400 text-xs">Tidak ada tindakan</span>';
            }

            const cbClass = v.cara_bayar === "UMUM" ? "badge-success" : "badge-info";

            return `
                <tr>
                    <td class="font-mono text-xs">${escapeHtml(v.no_rm)}</td>
                    <td>${escapeHtml(v.nama)}</td>
                    <td>${formatDate(v.tgl_lahir)}</td>
                    <td><span class="badge-neutral">${escapeHtml(v.ruang)}</span></td>
                    <td><span class="${cbClass}">${escapeHtml(v.cara_bayar || '')}</span></td>
                    <td>${formatDate(v.tanggal_kunjungan)}</td>
                    <td>${tindakanHtml}</td>
                    <td class="text-right font-medium text-xs">${formatIDR(v.total_biaya || 0)}</td>
                </tr>
            `;
        }).join("");
        els.visitsTbody.innerHTML = rows;
        updateExportButton();
    }

    // ----- Recap table -----
    async function refreshRecaps() {
        try {
            const r = await fetch("/api/recap?limit=50");
            if (!r.ok) return;
            const recaps = await r.json();
            renderRecaps(recaps);
        } catch (_e) { /* silent */ }
    }

    function renderRecaps(recaps) {
        if (!recaps.length) {
            els.recapTbody.innerHTML =
                '<tr><td colspan="5" class="text-center text-sm text-ink-400 py-12">' +
                "Belum ada riwayat." +
                "</td></tr>";
            return;
        }
        const rows = recaps.map(function (r) {
            return '<tr class="cursor-pointer" data-tanggal="' + escapeHtml(r.tanggal_kunjungan) + '">' +
                '<td class="font-medium">' + formatDate(r.tanggal_kunjungan) + "</td>" +
                '<td class="text-right font-semibold">' + formatIDR(r.total_biaya) + "</td>" +
                '<td class="text-right">' + r.total_pasien + "</td>" +
                '<td class="text-right">' + r.total_tindakan + "</td>" +
                '<td class="text-xs text-ink-600">' + formatRelative(r.last_scraped_at) + "</td>" +
                "</tr>";
        }).join("");
        els.recapTbody.innerHTML = rows;

        els.recapTbody.querySelectorAll("tr[data-tanggal]").forEach(function (tr) {
            tr.addEventListener("click", async function () {
                const tanggal = tr.dataset.tanggal;
                await loadVisitsForRange(tanggal, tanggal, null);
                document.querySelector("[data-card='visits']").scrollIntoView({ behavior: "smooth" });
            });
        });
    }

    // ----- Export Excel -----
    els.btnExport.addEventListener("click", function () {
        try {
            const tanggal = currentDisplayTanggal;
            if (!tanggal) {
                toast("Tidak ada data yang ditampilkan untuk diekspor", "warning");
                return;
            }
            const caraBayar = currentDisplayCaraBayar;
            const params = new URLSearchParams({ tanggal: tanggal });
            if (caraBayar && caraBayar !== "SEMUA") {
                params.set("cara_bayar", caraBayar);
            }
            window.location.href = "/api/export/excel?" + params.toString();
        } catch (e) {
            toast("Gagal mengekspor Excel: " + e.message, "error");
        }
    });

    // ----- Init -----
    syncMode();
    loadRuang().then(function () { refreshRecaps(); });
})();
