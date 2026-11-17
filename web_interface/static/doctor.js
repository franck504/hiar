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

  // Restauration automatique de session si jeton mémorisé
  const savedToken = localStorage.getItem("hiar_doctor_token");
  if (savedToken) {
    $("token").value = savedToken;
    performLogin(savedToken);
  }
})();
