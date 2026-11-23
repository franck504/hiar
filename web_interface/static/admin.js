(() => {
  "use strict";

  let timer = null;
  const $ = (id) => document.getElementById(id);

  function say(id, message) {
    const el = $(id);
    if (!el) return;
    el.textContent = message || "";
    el.classList.toggle("error", Boolean(message));
  }

  const DIAG_LABELS = {
    ok: "Opérationnel",
    warn: "Avertissement",
    error: "Erreur",
    offline: "Hors ligne",
  };

  function normalizeStatus(st) {
    const s = String(st || "").toLowerCase();
    if (s === "ok" || s === "running" || s === "connected" || s === "true") return "ok";
    if (s === "warn" || s === "warning" || s === "degraded") return "warn";
    if (s === "error" || s === "failed" || s === "disconnected") return "error";
    return "offline";
  }

  function makeDiagCard(icon, title, status, detail, meta) {
    const norm = normalizeStatus(status);
    const card = document.createElement("div");
    card.className = "diag-card diag-card-" + norm;

    const head = document.createElement("div");
    head.className = "diag-card-head";

    const titleWrap = document.createElement("span");
    titleWrap.className = "diag-card-title";
    titleWrap.textContent = icon + " " + title;

    const badge = document.createElement("span");
    badge.className = "diag-pill diag-" + norm;
    badge.textContent = DIAG_LABELS[norm] || norm;

    head.append(titleWrap, badge);

    const detailEl = document.createElement("p");
    detailEl.className = "diag-card-detail";
    detailEl.textContent = detail || "-";

    card.append(head, detailEl);

    if (meta) {
      const metaEl = document.createElement("p");
      metaEl.className = "diag-card-meta";
      metaEl.textContent = meta;
      card.append(metaEl);
    }
    return card;
  }

  function renderDiagnostics(data) {
    const grid = $("diag-grid");
    const pill = $("diag-bridge-pill");
    const subtitle = $("diag-subtitle");
    if (!grid || !pill || !subtitle) return;

    const online = Boolean(data && data.bridge_online);
    pill.className = "diag-pill " + (online ? "diag-ok" : "diag-offline");
    pill.textContent = online ? "Temps réel actif" : "Pont hors ligne";

    const net = (data && data.network) || {};
    const timeStr = new Date().toLocaleTimeString("fr-FR");
    subtitle.textContent = online
      ? "IP Robot : " + (net.ip || "-") + " · Firmware : " + (data.firmware_diagnostics || "-") + " · Mis à jour à " + timeStr
      : "En attente du pont ROS 2 (hmi_websocket_bridge) · Vérifié à " + timeStr;

    const esp32 = (data && data.esp32) || {};
    const sensors = (data && data.sensors) || {};
    const rosNodes = (data && data.ros_nodes) || {};
    const llm = (data && data.llm) || {};

    const cards = [
      makeDiagCard("🩺", "MAX30102 (Pouls / SpO2)", sensors.max30102?.status, sensors.max30102?.detail || "En attente de mesure", sensors.max30102?.meta),
      makeDiagCard("🌡️", "DS18B20 (Température)", sensors.ds18b20?.status, sensors.ds18b20?.detail || "En attente de mesure", sensors.ds18b20?.meta),
      makeDiagCard("📡", "HC-SR04 Centre (Obstacles)", sensors.ultrasonic?.status, sensors.ultrasonic?.detail || "Capteur frontal", sensors.ultrasonic?.meta),
      makeDiagCard("⬅️", "HC-SR04 Gauche (Obstacles)", sensors.ultrasonic_left?.status, sensors.ultrasonic_left?.detail || "Capteur latéral gauche", sensors.ultrasonic_left?.meta),
      makeDiagCard("➡️", "HC-SR04 Droite (Obstacles)", sensors.ultrasonic_right?.status, sensors.ultrasonic_right?.detail || "Capteur latéral droit", sensors.ultrasonic_right?.meta),
      makeDiagCard("⚡", "ESP32 Châssis & Moteurs", esp32.status, esp32.detail || "Liaison série USB", esp32.port ? "Port : " + esp32.port : null),
      makeDiagCard("🧠", "IA Hybride (Gemini + Qwen)", llm.status, llm.detail || "Gemini Cloud + Fallback Edge Qwen 2.5", llm.meta),
      makeDiagCard("🤖", "Nœuds ROS 2 du Robot", rosNodes.status, rosNodes.detail || "Superviseur & Navigation", rosNodes.meta),
      makeDiagCard("🌐", "Pont WebSocket & Réseau", online ? "ok" : "offline", online ? "ws://" + (net.ip || "127.0.0.1") + ":" + (net.ws_port || 5000) + "/ws" : "Déconnecté", "Port Web : " + (net.web_port || 5001)),
    ];

    grid.replaceChildren(...cards);
  }

  async function refreshDiagnostics() {
    try {
      const pin = localStorage.getItem("hiar_web_pin") || "";
      const response = await fetch("/api/system/diagnostics", {
        headers: { "X-Web-PIN": pin },
      });
      if (!response.ok) return;
      const data = await response.json();
      renderDiagnostics(data);
    } catch (_) {
      renderDiagnostics({ bridge_online: false });
    }
  }

  let activeTab = "hardware";
  let cachedAppointments = [];

  function switchTab(tab) {
    activeTab = tab;
    const isHard = tab === "hardware";
    const tabHard = $("tab-btn-hardware");
    const tabDash = $("tab-btn-dashboard");
    const panelHard = $("diagnostics-panel");
    const panelDash = $("dashboard-panel");

    if (tabHard) {
      tabHard.classList.toggle("active", isHard);
      tabHard.setAttribute("aria-selected", isHard ? "true" : "false");
    }
    if (tabDash) {
      tabDash.classList.toggle("active", !isHard);
      tabDash.setAttribute("aria-selected", !isHard ? "true" : "false");
    }
    if (panelHard) panelHard.hidden = !isHard;
    if (panelDash) panelDash.hidden = isHard;

    if (isHard) {
      refreshDiagnostics();
    } else {
      loadDashboardData();
    }
  }

  function unlockAdmin() {
    $("login-panel").hidden = true;
    $("admin-topbar-actions").hidden = false;
    if ($("admin-tab-nav")) $("admin-tab-nav").hidden = false;
    switchTab(activeTab);
    if (!timer) timer = setInterval(() => {
      if (activeTab === "hardware") refreshDiagnostics();
      else loadDashboardData();
    }, 4000);
  }

  function lockAdmin(message) {
    clearInterval(timer);
    timer = null;
    localStorage.removeItem("hiar_web_pin");
    if ($("admin-tab-nav")) $("admin-tab-nav").hidden = true;
    $("diagnostics-panel").hidden = true;
    if ($("dashboard-panel")) $("dashboard-panel").hidden = true;
    $("admin-topbar-actions").hidden = true;
    $("login-panel").hidden = false;
    const digits = [ $("pin-1"), $("pin-2"), $("pin-3"), $("pin-4"), $("pin-5"), $("pin-6") ];
    digits.forEach(d => { if (d) d.value = ""; });
    if (digits[0]) digits[0].focus();
    if (message) say("login-feedback", message);
  }

  async function loadDashboardData() {
    try {
      const pin = localStorage.getItem("hiar_web_pin") || "";
      const res = await fetch("/api/admin/dashboard", {
        headers: { "X-Web-PIN": pin },
      });
      if (!res.ok) return;
      const data = await res.json();
      if (!data.ok) return;

      const stats = data.stats || {};
      if ($("kpi-total")) $("kpi-total").textContent = stats.total || 0;
      if ($("kpi-confirmed")) $("kpi-confirmed").textContent = stats.confirmed || 0;
      if ($("kpi-consulting")) $("kpi-consulting").textContent = stats.in_consultation || 0;
      if ($("kpi-done")) $("kpi-done").textContent = stats.done || 0;
      if ($("kpi-alerts")) $("kpi-alerts").textContent = stats.alerts || 0;

      cachedAppointments = data.appointments || [];
      renderDashboardTable();
    } catch (err) {
      console.error("Erreur dashboard:", err);
    }
  }

  function escapeHtml(str) {
    return String(str || "").replace(/[&<>"']/g, (m) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    }[m]));
  }

  function renderDashboardTable() {
    const tbody = $("dashboard-history-body");
    if (!tbody) return;

    const docFilter = $("filter-doctor")?.value || "";
    const stFilter = $("filter-status")?.value || "";
    const searchFilter = ($("filter-search")?.value || "").toLowerCase().trim();

    const STATUS_GROUP_MAP = {
      CONFIRMED: ["CONFIRMED", "WAITING", "en attente"],
      IN_CONSULTATION: ["IN_CONSULTATION", "appelé"],
      DONE: ["DONE", "COMPLETED", "terminé"],
      CANCELLED: ["CANCELLED", "annulé", "non reçu"],
    };

    const filtered = cachedAppointments.filter((a) => {
      if (docFilter && (a.doctor || "") !== docFilter) return false;
      if (stFilter) {
        const allowed = STATUS_GROUP_MAP[stFilter] || [stFilter];
        if (!allowed.includes(a.status)) return false;
      }
      if (searchFilter) {
        const haystack = `${a.patient_name || ""} ${a.contact || ""} ${a.ticket_label || ""} ${a.reason_code || ""}`.toLowerCase();
        if (!haystack.includes(searchFilter)) return false;
      }
      return true;
    });

    if (filtered.length === 0) {
      tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; color:#64748b; padding:24px;">Aucun rendez-vous trouvé.</td></tr>';
      return;
    }

    const STATUS_LABELS = {
      CONFIRMED: "En attente",
      WAITING: "En attente",
      "en attente": "En attente",
      IN_CONSULTATION: "En consultation",
      "appelé": "En consultation",
      DONE: "Terminé",
      COMPLETED: "Terminé",
      "terminé": "Terminé",
      CANCELLED: "Annulé",
      "annulé": "Annulé",
      "non reçu": "Non reçu",
    };

    const ST_CLASS_MAP = {
      CONFIRMED: "status-waiting",
      WAITING: "status-waiting",
      "en attente": "status-waiting",
      IN_CONSULTATION: "status-in_consultation",
      "appelé": "status-in_consultation",
      DONE: "status-done",
      COMPLETED: "status-done",
      "terminé": "status-done",
      CANCELLED: "status-cancelled",
      "annulé": "status-cancelled",
      "non reçu": "status-cancelled",
    };

    const rows = filtered.map((a) => {
      const tr = document.createElement("tr");

      let vitalsHtml = "-";
      const parts = [];
      let hasAlert = false;
      if (a.temperature_c != null) {
        const isHot = a.temperature_c >= 38.0 || a.temperature_c <= 35.0;
        if (isHot) hasAlert = true;
        parts.push(`<span class="${isHot ? 'vitals-alert' : ''}">${a.temperature_c}°C</span>`);
      }
      if (a.heart_rate_bpm != null) {
        const isAbnormalHr = a.heart_rate_bpm > 100 || a.heart_rate_bpm < 50;
        if (isAbnormalHr) hasAlert = true;
        parts.push(`<span class="${isAbnormalHr ? 'vitals-alert' : ''}">${a.heart_rate_bpm} bpm</span>`);
      }
      if (a.spo2_percent != null) {
        const isHypoxia = a.spo2_percent < 95;
        if (isHypoxia) hasAlert = true;
        parts.push(`<span class="${isHypoxia ? 'vitals-alert' : ''}">${a.spo2_percent}%</span>`);
      }
      if (parts.length > 0) {
        vitalsHtml = parts.join(" · ");
        if (hasAlert) {
          vitalsHtml += ' <span class="badge-alert-pill">Alerte</span>';
        }
      }

      const st = a.status || "en attente";
      const stLabel = STATUS_LABELS[st] || st;
      const stClass = ST_CLASS_MAP[st] || ("status-" + String(st).toLowerCase().replace(/\s+/g, "_"));

      const dateStr = a.requested_date ? (a.requested_time ? `${a.requested_date} ${a.requested_time}` : a.requested_date) : "-";
      const doctorStr = a.doctor ? `Dr. ${a.doctor} (${a.period || 'MAT'})` : "-";

      tr.innerHTML = `
        <td><strong>${escapeHtml(dateStr)}</strong></td>
        <td><span class="ticket-badge">${escapeHtml(a.ticket_label || "-")}</span></td>
        <td>${escapeHtml(a.patient_name || "-")}</td>
        <td>${escapeHtml(a.contact || "-")}</td>
        <td>${escapeHtml(a.reason_code || "-")}</td>
        <td>${escapeHtml(doctorStr)}</td>
        <td>${vitalsHtml}</td>
        <td><span class="status-pill ${stClass}">${escapeHtml(stLabel)}</span></td>
      `;
      return tr;
    });

    tbody.replaceChildren(...rows);
  }

  function initPinAuth() {
    const form = $("login-form");
    const digits = [ $("pin-1"), $("pin-2"), $("pin-3"), $("pin-4"), $("pin-5"), $("pin-6") ];
    if (!form || !digits[0]) return;

    function getEnteredPin() {
      return digits.map(d => d ? d.value : "").join("");
    }

    function clearDigits() {
      digits.forEach(d => { if (d) d.value = ""; });
      if (digits[0]) digits[0].focus();
    }

    digits.forEach((d, i) => {
      d.addEventListener("input", () => {
        if (d.value.length >= 1) {
          d.value = d.value.slice(-1);
          if (i < 5 && digits[i + 1]) digits[i + 1].focus();
          else if (getEnteredPin().length === 6) form.requestSubmit();
        }
      });
      d.addEventListener("keydown", (e) => {
        if (e.key === "Backspace" && !d.value && i > 0 && digits[i - 1]) {
          digits[i - 1].focus();
        }
      });
    });

    document.querySelectorAll(".pin-key").forEach(btn => {
      btn.addEventListener("click", () => {
        const val = btn.dataset.val;
        if (val === "C") {
          clearDigits();
          say("login-feedback", "");
          return;
        }
        if (val !== undefined && val !== "") {
          for (let i = 0; i < 6; i++) {
            if (digits[i] && !digits[i].value) {
              digits[i].value = val;
              if (i < 5 && digits[i + 1]) digits[i + 1].focus();
              else if (getEnteredPin().length === 6) form.requestSubmit();
              break;
            }
          }
        }
      });
    });

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const enteredPin = getEnteredPin();
      if (enteredPin.length !== 6) {
        say("login-feedback", "Veuillez saisir les 6 chiffres du code PIN.");
        return;
      }
      say("login-feedback", "");
      try {
        const res = await fetch("/api/auth/pin", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ pin: enteredPin }),
        });
        const data = await res.json();
        if (res.ok && data.ok) {
          unlockAdmin();
        } else {
          say("login-feedback", data.error || "Code PIN incorrect.");
          clearDigits();
        }
      } catch (_) {
        say("login-feedback", "Erreur réseau. Veuillez réessayer.");
      }
    });
        say("login-feedback", "Erreur réseau. Veuillez réessayer.");
      }
    });

    const logoutBtn = $("admin-logout-btn");
    if (logoutBtn) {
      logoutBtn.addEventListener("click", () => {
        fetch("/api/auth/logout", { method: "POST" }).finally(() => {
          lockAdmin();
        });
      });
    }

    const stopBtn = $("admin-emergency-stop-btn");
    if (stopBtn) {
      stopBtn.addEventListener("click", async () => {
        if (!confirm("Voulez-vous vraiment ARRÊTER D'URGENCE le robot ?")) return;
        try {
          const res = await fetch("/api/navigation/cancel", { method: "POST" });
          const data = await res.json();
          if (data.ok) {
            alert("ARRÊT D'URGENCE EXÉCUTÉ ! Ordre STOP transmis sur /navigation/command, /robot/command et /robot/motor_command.");
          } else {
            alert("Échec de l'arrêt d'urgence : " + (data.error || "inconnu"));
          }
        } catch (err) {
          alert("Erreur réseau : " + err.message);
        }
      });
    }

    const tabHardBtn = $("tab-btn-hardware");
    if (tabHardBtn) tabHardBtn.addEventListener("click", () => switchTab("hardware"));

    const tabDashBtn = $("tab-btn-dashboard");
    if (tabDashBtn) tabDashBtn.addEventListener("click", () => switchTab("dashboard"));

    const refreshBtn = $("diag-refresh-btn");
    if (refreshBtn) refreshBtn.addEventListener("click", refreshDiagnostics);

    const refreshTopBtn = $("diag-refresh-top-btn");
    if (refreshTopBtn) refreshTopBtn.addEventListener("click", refreshDiagnostics);

    const dashRefreshBtn = $("dashboard-refresh-btn");
    if (dashRefreshBtn) dashRefreshBtn.addEventListener("click", loadDashboardData);

    const filterDoctor = $("filter-doctor");
    if (filterDoctor) filterDoctor.addEventListener("change", renderDashboardTable);

    const filterStatus = $("filter-status");
    if (filterStatus) filterStatus.addEventListener("change", renderDashboardTable);

    const filterSearch = $("filter-search");
    if (filterSearch) filterSearch.addEventListener("input", renderDashboardTable);
  }

  document.addEventListener("DOMContentLoaded", initPinAuth);
})();
