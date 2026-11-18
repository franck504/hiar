(() => {
  "use strict";

  let token = "";
  let timer = null;

  const DOCTOR_TOKENS = {
    A: "wOBSF8JfiwWVfcDaeSYyxHU7Z530o2BwXlfF6tWZBss",
    B: "7iG_xhLoTcOfbppd6LTxwtuTwQjwE_eKtHKYbE69GKA",
    C: "JqtfOWu0M1Blu7aYeKx-sVQx8huEte41n734tLroaps",
    D: "owykW-nd1meLRSMowaKT999c00c7zsZkhexmnFIs_dI",
  };

  const PERIODS = { MAT: "Matin", AM: "Après-midi" };
  const ACTIONS = {
    "en attente": [["appelé", "Appeler"], ["non reçu", "Non reçu"], ["annulé", "Annuler"]],
    "appelé": [["terminé", "Terminé"], ["non reçu", "Non reçu"], ["annulé", "Annuler"]],
  };

  const $ = (id) => document.getElementById(id);

  function today() {
    return new Date().toLocaleDateString("sv-SE", { timeZone: "Indian/Antananarivo" });
  }

  function say(id, message) {
    const el = $(id);
    el.textContent = message || "";
    el.classList.toggle("error", Boolean(message));
  }

  async function api(url, options = {}) {
    const response = await fetch(url, {
      ...options,
      headers: {
        "X-Doctor-Token": token,
        "Content-Type": "application/json",
        ...(options.headers || {}),
      },
    });
    let body = {};
    try { body = await response.json(); } catch (_) { /* corps vide */ }
    if (response.status === 401) {
      logout("Jeton invalide ou expiré.");
      throw new Error("auth");
    }
    if (!response.ok) {
      throw new Error(body.error || "Erreur " + response.status);
    }
    return body;
  }

  function logout(message) {
    token = "";
    localStorage.removeItem("hiar_doctor_token");
    clearInterval(timer);
    $("queue-panel").hidden = true;
    $("doctor-topbar-actions").hidden = true;
    $("login-panel").hidden = false;
    $("token").value = "";
    say("login-feedback", message || "");
  }

  async function setSession(period, isOpen) {
    try {
      await api("/api/doctor/sessions", {
        method: "POST",
        body: JSON.stringify({ requested_date: today(), period, is_open: isOpen }),
      });
      say("queue-feedback", "");
      await refresh();
    } catch (err) {
      if (err.message !== "auth") say("queue-feedback", err.message);
    }
  }

  function renderSessions(sessions) {
    const box = $("sessions");
    box.replaceChildren();
    Object.keys(PERIODS).forEach((period) => {
      const found = sessions.find((s) => s.period === period);
      const open = Boolean(found && found.is_open);
      const button = document.createElement("button");
      button.type = "button";
      button.className = "btn btn-outline";
      button.textContent = PERIODS[period] + " : " + (open ? "ouvert (fermer)" : "fermé (ouvrir)");
      button.addEventListener("click", () => setSession(period, !open));
      box.append(button);
    });
  }

  async function changeStatus(id, status) {
    try {
      await api("/api/doctor/appointments/" + id, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
      say("queue-feedback", "");
      await refresh();
    } catch (err) {
      if (err.message !== "auth") say("queue-feedback", err.message);
    }
  }

  function cell(row, text) {
    const td = document.createElement("td");
    td.textContent = text == null ? "" : String(text);
    row.append(td);
    return td;
  }

  function renderQueue(items) {
    const body = $("queue-body");
    body.replaceChildren();
    if (!items.length) {
      const tr = document.createElement("tr");
      const td = cell(tr, "Aucun patient inscrit aujourd'hui.");
      td.colSpan = 8;
      td.className = "empty";
      body.append(tr);
      return;
    }
    items.forEach((item) => {
      const tr = document.createElement("tr");
      cell(tr, item.doctor + "-" + item.period + "-" + item.ticket_number);
      cell(tr, PERIODS[item.period] || item.period);
      cell(tr, item.patient_name);
      cell(tr, item.contact || "—");
      cell(tr, item.reason);

      // Signes vitaux mesurés par HIAR
      const vitals = [];
      if (item.temperature_c != null) vitals.push("🌡️ " + item.temperature_c + " °C");
      if (item.heart_rate_bpm != null) vitals.push("❤️ " + item.heart_rate_bpm + " bpm");
      if (item.spo2_percent != null) vitals.push("🫁 " + item.spo2_percent + " %");
      const vitalsCell = cell(tr, vitals.length ? vitals.join("  |  ") : "Non mesurées");
      vitalsCell.className = "vitals-cell";

      const statusCell = cell(tr, item.status);
      statusCell.className = "status";
      statusCell.dataset.status = item.status;
      const actions = document.createElement("td");
      actions.className = "actions-cell";
      (ACTIONS[item.status] || []).forEach(([status, label]) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = (status === "appelé" || status === "terminé")
          ? "btn btn-small"
          : "btn btn-small btn-outline";
        button.textContent = label;
        button.addEventListener("click", () =>
          changeStatus(item.id ?? item.appointment_id, status));
        actions.append(button);
      });
      tr.append(actions);
      body.append(tr);
    });
  }

  async function refresh() {
    const day = today();
    try {
      const [sessions, queue] = await Promise.all([
        api("/api/doctor/sessions?date=" + day),
        api("/api/doctor/appointments?date=" + day),
      ]);
      $("queue-title").textContent = "Ma file — médecin " + queue.doctor;
      $("queue-date").textContent = "Date : " + day;
      renderSessions(sessions.sessions || []);
      renderQueue(queue.appointments || []);
    } catch (err) {
      if (err.message !== "auth") say("queue-feedback", err.message);
    }
  }

  async function performLogin(candidateToken) {
    token = candidateToken.trim();
    say("login-feedback", "");
    try {
      await api("/api/doctor/sessions?date=" + today());
    } catch (err) {
      if (err.message !== "auth") say("login-feedback", err.message);
      return false;
    }
    localStorage.setItem("hiar_doctor_token", token);
    $("login-panel").hidden = true;
    $("queue-panel").hidden = false;
    $("doctor-topbar-actions").hidden = false;
    await refresh();
    if (timer) clearInterval(timer);
    timer = setInterval(refresh, 5000);
    return true;
  }

  $("login-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    await performLogin($("token").value);
  });

  document.querySelectorAll(".quick-doc-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const doc = btn.dataset.doc;
      if (DOCTOR_TOKENS[doc]) {
        $("token").value = DOCTOR_TOKENS[doc];
        performLogin(DOCTOR_TOKENS[doc]);
      }
    });
  });

  $("refresh-btn").addEventListener("click", refresh);
  $("logout-btn").addEventListener("click", () => logout(""));

  // =========================================================================
  // MONITEUR TEMPS RÉEL DES CAPTEURS & MATÉRIEL (ESP32, ROS 2, LLM)
  // =========================================================================
  const DIAG_LABELS = {
    ok: "En ligne",
    warn: "Attention",
    error: "Erreur",
    offline: "Hors ligne",
    unknown: "Inconnu",
  };

  function normalizeStatus(st) {
    const s = String(st || "offline").toLowerCase();
    if (s === "ok" || s === "online" || s === "connected" || s === "ready") return "ok";
    if (s === "warn" || s === "warning" || s === "degraded") return "warn";
    if (s === "error" || s === "fault") return "error";
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
    detailEl.textContent = detail || "—";

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
      ? "IP Robot : " + (net.ip || "—") + " · Firmware : " + (data.firmware_diagnostics || "—") + " · Mis à jour à " + timeStr
      : "En attente du pont ROS 2 (hmi_websocket_bridge) · Vérifié à " + timeStr;

    const esp32 = (data && data.esp32) || {};
    const sensors = (data && data.sensors) || {};
    const rosNodes = (data && data.ros_nodes) || {};
    const llm = (data && data.llm) || {};

    const usFront = sensors.ultrasonic || {};
    const usLeft = sensors.ultrasonic_left || {};
    const usRight = sensors.ultrasonic_right || {};
    const temp = sensors.ds18b20 || {};
    const pulse = sensors.max30102 || {};
    const motors = sensors.motors || {};

    const cards = [
      makeDiagCard("🔌", "ESP32", esp32.status, esp32.detail || "Non connecté", esp32.port ? "Port : " + esp32.port : ""),
      makeDiagCard("⬆️", "Ultrason Avant (HC-SR04)", usFront.status, usFront.detail || "Inconnu", usFront.distance_cm != null ? "GPIO 13/34 · " + usFront.distance_cm + " cm" : "GPIO 13/34"),
      makeDiagCard("⬅️", "Ultrason Gauche (HC-SR04)", usLeft.status, usLeft.detail || "Inconnu", usLeft.distance_cm != null ? "GPIO 2/4 · " + usLeft.distance_cm + " cm" : "GPIO 2/4"),
      makeDiagCard("➡️", "Ultrason Droite (HC-SR04)", usRight.status, usRight.detail || "Inconnu", usRight.distance_cm != null ? "GPIO 5/16 · " + usRight.distance_cm + " cm" : "GPIO 5/16"),
      makeDiagCard("🌡️", "Température DS18B20", temp.status, temp.detail || "Inconnu", "Bus 1-Wire"),
      makeDiagCard("❤️", "Pouls / SpO2 MAX30102", pulse.status, pulse.detail || "Inconnu", "Bus I²C (0x57)"),
      makeDiagCard("⚙️", "Moteurs & Traction", motors.status, motors.detail || "Inconnu", motors.mode ? "Mode : " + motors.mode : ""),
      makeDiagCard("🤖", "Nœuds ROS 2", rosNodes.status, rosNodes.detail || "—", ""),
      makeDiagCard("🧠", "IA Vocale (LLM)", llm.status, llm.detail || "—", ""),
    ];

    grid.replaceChildren(...cards);
  }

  async function refreshDiagnostics() {
    try {
      const response = await fetch("/api/system/diagnostics");
      if (!response.ok) return;
      const data = await response.json();
      renderDiagnostics(data);
    } catch (_) {
      renderDiagnostics({ bridge_online: false });
    }
  }

  const diagBtn = $("diag-refresh-btn");
  if (diagBtn) diagBtn.addEventListener("click", refreshDiagnostics);
  refreshDiagnostics();
  setInterval(refreshDiagnostics, 3000);

  // Restauration automatique de session si jeton mémorisé
  const savedToken = localStorage.getItem("hiar_doctor_token");
  if (savedToken) {
    $("token").value = savedToken;
    performLogin(savedToken);
  }
})();
