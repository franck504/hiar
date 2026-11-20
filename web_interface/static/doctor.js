(() => {
  "use strict";

  let token = "";
  let pin = "";
  let currentDoctor = "A";
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
    if (!el) return;
    el.textContent = message || "";
    el.classList.toggle("error", Boolean(message));
  }

  async function api(url, options = {}) {
    const headers = {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    };
    if (token) headers["X-Doctor-Token"] = token;
    if (pin) headers["X-Web-PIN"] = pin;
    if (currentDoctor) headers["X-Doctor-Code"] = currentDoctor;

    const response = await fetch(url, {
      ...options,
      headers,
    });
    let body = {};
    try { body = await response.json(); } catch (_) { /* corps vide */ }
    if (response.status === 401) {
      lockQueue("Session expirée. Veuillez saisir le code PIN.");
      throw new Error("auth");
    }
    if (!response.ok) {
      throw new Error(body.error || "Erreur " + response.status);
    }
    return body;
  }

  function lockQueue(message) {
    clearInterval(timer);
    timer = null;
    localStorage.removeItem("hiar_web_pin");
    localStorage.removeItem("hiar_doctor_token");
    $("queue-panel").hidden = true;
    $("doctor-topbar-actions").hidden = true;
    $("login-panel").hidden = false;
    const digits = [ $("pin-1"), $("pin-2"), $("pin-3"), $("pin-4") ];
    digits.forEach(d => { if (d) d.value = ""; });
    if ($("token")) $("token").value = "";
    if (digits[0]) digits[0].focus();
    if (message) say("login-feedback", message);
  }

  function unlockQueue() {
    $("login-panel").hidden = true;
    $("queue-panel").hidden = false;
    $("doctor-topbar-actions").hidden = false;
    refresh();
    if (timer) clearInterval(timer);
    timer = setInterval(refresh, 5000);
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
    if (!box) return;
    box.replaceChildren();
    Object.keys(PERIODS).forEach((period) => {
      const found = (sessions || []).find((s) => s.period === period);
      const open = Boolean(found && found.is_open);
      const button = document.createElement("button");
      button.type = "button";
      button.className = "btn btn-outline btn-small";
      button.textContent = PERIODS[period] + " : " + (open ? "Ouvert (fermer)" : "Fermé (ouvrir)");
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
    if (!body) return;
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

      // Signes vitaux mesurés par HIAR (sans emojis dans les chaînes clés)
      const vitals = [];
      if (item.temperature_c != null) vitals.push("T° " + item.temperature_c + " °C");
      if (item.heart_rate_bpm != null) vitals.push("Pouls " + item.heart_rate_bpm + " bpm");
      if (item.spo2_percent != null) vitals.push("SpO2 " + item.spo2_percent + " %");
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
        api("/api/doctor/sessions?date=" + day + "&doctor=" + currentDoctor),
        api("/api/doctor/appointments?date=" + day + "&doctor=" + currentDoctor),
      ]);
      const title = $("queue-title");
      if (title) title.textContent = "Rendez-vous des patients — Médecin " + (queue.doctor || currentDoctor);
      const dateEl = $("queue-date");
      if (dateEl) dateEl.textContent = "Date : " + day;
      renderSessions(sessions.sessions || []);
      renderQueue(queue.appointments || []);
    } catch (err) {
      if (err.message !== "auth") say("queue-feedback", err.message);
    }
  }

  function initPinAndForm() {
    const form = $("login-form");
    const digits = [ $("pin-1"), $("pin-2"), $("pin-3"), $("pin-4") ];

    function getEnteredPin() {
      return digits.map(d => d ? d.value : "").join("");
    }

    function clearDigits() {
      digits.forEach(d => { if (d) d.value = ""; });
      if (digits[0]) digits[0].focus();
    }

    digits.forEach((d, i) => {
      if (!d) return;
      d.addEventListener("input", () => {
        if (d.value.length >= 1) {
          d.value = d.value.slice(-1);
          if (i < 3 && digits[i + 1]) digits[i + 1].focus();
          else if (getEnteredPin().length === 4) form.requestSubmit();
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
          for (let i = 0; i < 4; i++) {
            if (digits[i] && !digits[i].value) {
              digits[i].value = val;
              if (i < 3 && digits[i + 1]) digits[i + 1].focus();
              else if (getEnteredPin().length === 4) form.requestSubmit();
              break;
            }
          }
        }
      });
    });

    if (form) {
      form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const enteredPin = getEnteredPin();
        const fallbackToken = $("token") ? $("token").value.trim() : "";

        // Cas 1 : Connexion par code PIN 4 chiffres
        if (enteredPin.length === 4) {
          say("login-feedback", "");
          try {
            const res = await fetch("/api/auth/pin", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ pin: enteredPin }),
            });
            const data = await res.json();
            if (res.ok && data.ok) {
              pin = enteredPin;
              token = DOCTOR_TOKENS[currentDoctor] || DOCTOR_TOKENS.A;
              localStorage.setItem("hiar_web_pin", enteredPin);
              localStorage.setItem("hiar_doctor_token", token);
              unlockQueue();
              return;
            } else {
              say("login-feedback", data.error || "Code PIN incorrect.");
              clearDigits();
              return;
            }
          } catch (_) {
            say("login-feedback", "Erreur réseau. Veuillez réessayer.");
            return;
          }
        }

        // Cas 2 : Connexion de secours par jeton médecin (si token rempli)
        if (fallbackToken) {
          token = fallbackToken;
          pin = "";
          try {
            await api("/api/doctor/sessions?date=" + today());
            localStorage.setItem("hiar_doctor_token", token);
            unlockQueue();
          } catch (err) {
            say("login-feedback", "Jeton médecin invalide.");
          }
        } else {
          say("login-feedback", "Veuillez saisir les 4 chiffres du code PIN.");
        }
      });
    }

    document.querySelectorAll(".quick-doc-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const doc = btn.dataset.doc;
        currentDoctor = doc;
        document.querySelectorAll(".quick-doc-btn").forEach(b => {
          b.classList.toggle("btn-primary", b.dataset.doc === doc);
        });
        if (DOCTOR_TOKENS[doc]) {
          token = DOCTOR_TOKENS[doc];
        }
        refresh();
      });
    });

    const refreshBtn = $("refresh-btn");
    if (refreshBtn) refreshBtn.addEventListener("click", refresh);

    const logoutBtn = $("logout-btn");
    if (logoutBtn) {
      logoutBtn.addEventListener("click", () => {
        fetch("/api/auth/logout", { method: "POST" }).finally(() => {
          lockQueue();
        });
      });
    }

    // Restauration de session automatique si PIN mémorisé
    const savedPin = localStorage.getItem("hiar_web_pin");
    if (savedPin && savedPin.length === 4) {
      fetch("/api/auth/pin", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pin: savedPin }),
      }).then(r => r.json()).then(data => {
        if (data && data.ok) {
          pin = savedPin;
          token = DOCTOR_TOKENS[currentDoctor] || DOCTOR_TOKENS.A;
          unlockQueue();
        } else {
          localStorage.removeItem("hiar_web_pin");
        }
      }).catch(() => {});
    } else {
      const savedToken = localStorage.getItem("hiar_doctor_token");
      if (savedToken) {
        token = savedToken;
        unlockQueue();
      }
    }
  }

  document.addEventListener("DOMContentLoaded", initPinAndForm);
})();
