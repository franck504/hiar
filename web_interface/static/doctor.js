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
    const digits = [ $("pin-1"), $("pin-2"), $("pin-3"), $("pin-4"), $("pin-5"), $("pin-6") ];
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
      cell(tr, item.contact || "-");
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
      if (title) title.textContent = "Rendez-vous des patients - Médecin " + (queue.doctor || currentDoctor);
      const dateEl = $("queue-date");
      if (dateEl) {
        const dObj = new Date(day + "T00:00:00");
        const niceDate = isNaN(dObj.getTime())
          ? day
          : dObj.toLocaleDateString("fr-FR", { weekday: "long", year: "numeric", month: "long", day: "numeric" });
        dateEl.textContent = "Date : " + niceDate;
      }
      renderSessions(sessions.sessions || []);
      renderQueue(queue.appointments || []);
    } catch (err) {
      if (err.message !== "auth") say("queue-feedback", err.message);
    }
  }

  function resolveDigit(e) {
    // 1. Pavé numérique / Numpad physique (fonctionne même si NumLock est désactivé)
    if (e.code && /^Numpad[0-9]$/.test(e.code)) {
      return e.code.replace("Numpad", "");
    }
    // 2. Chiffre direct standard
    if (e.key && /^[0-9]$/.test(e.key)) {
      return e.key;
    }
    // 3. Rangée supérieure physique Digit0 à Digit9 (ex. AZERTY sans Maj)
    if (e.code && /^Digit[0-9]$/.test(e.code)) {
      return e.code.replace("Digit", "");
    }
    // 4. Mappage AZERTY de secours
    const azertyMap = {
      "&": "1", "é": "2", "\"": "3", "'": "4", "(": "5",
      "-": "6", "è": "7", "_": "8", "ç": "9", "à": "0"
    };
    if (e.key && azertyMap[e.key]) {
      return azertyMap[e.key];
    }
    return null;
  }

  function initPinAndForm() {
    const form = $("login-form");
    const loginPanel = $("login-panel");
    const digits = [ $("pin-1"), $("pin-2"), $("pin-3"), $("pin-4"), $("pin-5"), $("pin-6") ];

    function getEnteredPin() {
      return digits.map(d => d ? d.value : "").join("");
    }

    function clearDigits() {
      digits.forEach(d => { if (d) d.value = ""; });
      if (digits[0]) {
        digits[0].focus();
        digits[0].select();
      }
    }

    async function submitPin() {
      const enteredPin = getEnteredPin();
      const fallbackToken = $("token") ? $("token").value.trim() : "";

      if (enteredPin.length === 6) {
        say("login-feedback", "Vérification du code PIN…");
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

      if (fallbackToken) {
        token = fallbackToken;
        pin = "";
        try {
          await api("/api/doctor/sessions?date=" + today());
          unlockQueue();
        } catch (err) {
          say("login-feedback", "Jeton médecin invalide.");
        }
      } else {
        say("login-feedback", "Veuillez saisir les 6 chiffres du code PIN.");
      }
    }

    // Gestion individuelle par case
    digits.forEach((d, i) => {
      if (!d) return;

      d.addEventListener("keydown", (e) => {
        const digit = resolveDigit(e);
        if (digit !== null) {
          e.preventDefault();
          d.value = digit;
          say("login-feedback", "");
          if (i < 5 && digits[i + 1]) {
            digits[i + 1].focus();
            digits[i + 1].select();
          }
          if (getEnteredPin().length === 6) {
            submitPin();
          }
          return;
        }

        if (e.key === "Backspace" || e.code === "Backspace") {
          e.preventDefault();
          if (d.value) {
            d.value = "";
          } else if (i > 0 && digits[i - 1]) {
            digits[i - 1].value = "";
            digits[i - 1].focus();
            digits[i - 1].select();
          }
          return;
        }

        if (e.key === "Delete" || e.code === "Delete") {
          e.preventDefault();
          d.value = "";
          return;
        }

        if (e.key === "ArrowLeft" && i > 0 && digits[i - 1]) {
          e.preventDefault();
          digits[i - 1].focus();
          digits[i - 1].select();
          return;
        }

        if (e.key === "ArrowRight" && i < 5 && digits[i + 1]) {
          e.preventDefault();
          digits[i + 1].focus();
          digits[i + 1].select();
          return;
        }

        if (e.key === "Enter" || e.code === "Enter" || e.code === "NumpadEnter") {
          e.preventDefault();
          submitPin();
          return;
        }
      });

      // Gestion de la saisie mobile / claviers virtuels
      d.addEventListener("input", () => {
        const clean = d.value.replace(/\D/g, "");
        if (clean) {
          d.value = clean.slice(-1);
          say("login-feedback", "");
          if (i < 5 && digits[i + 1]) {
            digits[i + 1].focus();
            digits[i + 1].select();
          }
          if (getEnteredPin().length === 6) {
            submitPin();
          }
        } else {
          d.value = "";
        }
      });

      // Gestion du coller (Ctrl+V)
      d.addEventListener("paste", (e) => {
        e.preventDefault();
        const text = (e.clipboardData || window.clipboardData).getData("text") || "";
        const clean = text.replace(/\D/g, "").slice(0, 6);
        if (!clean) return;
        for (let j = 0; j < 6; j++) {
          if (digits[j]) digits[j].value = clean[j] || "";
        }
        say("login-feedback", "");
        if (clean.length === 6) {
          digits[5].focus();
          submitPin();
        } else {
          const nextIdx = Math.min(clean.length, 5);
          if (digits[nextIdx]) digits[nextIdx].focus();
        }
      });

      d.addEventListener("focus", () => {
        d.select();
      });
    });

    // Capture clavier global sur le panneau de connexion pour rediriger vers les cases PIN
    if (loginPanel) {
      loginPanel.addEventListener("keydown", (e) => {
        if (digits.includes(document.activeElement)) return;
        const digit = resolveDigit(e);
        if (digit !== null) {
          e.preventDefault();
          let target = digits.find(d => !d.value) || digits[0];
          target.value = digit;
          say("login-feedback", "");
          const nextIdx = digits.indexOf(target) + 1;
          if (nextIdx < 6 && digits[nextIdx]) {
            digits[nextIdx].focus();
            digits[nextIdx].select();
          } else {
            target.focus();
          }
          if (getEnteredPin().length === 6) {
            submitPin();
          }
        } else if (e.key === "Backspace" || e.code === "Backspace") {
          e.preventDefault();
          for (let j = 5; j >= 0; j--) {
            if (digits[j] && digits[j].value) {
              digits[j].value = "";
              digits[j].focus();
              digits[j].select();
              break;
            }
          }
        } else if (e.key === "Enter" || e.code === "Enter" || e.code === "NumpadEnter") {
          e.preventDefault();
          submitPin();
        }
      });

      // Clic n'importe où sur le panneau -> donne le focus à la première case libre
      loginPanel.addEventListener("click", (e) => {
        if (!digits.includes(document.activeElement) && !e.target.closest("button")) {
          const target = digits.find(d => !d.value) || digits[0];
          if (target) target.focus();
        }
      });
    }

    // Pavé tactile / boutons écran
    document.querySelectorAll(".pin-key").forEach(btn => {
      btn.addEventListener("click", (e) => {
        e.preventDefault();
        const val = btn.dataset.val;
        if (val === "C") {
          clearDigits();
          say("login-feedback", "");
          return;
        }
        if (btn.id === "pin-submit-key") {
          submitPin();
          return;
        }
        if (val !== undefined && val !== "") {
          for (let i = 0; i < 6; i++) {
            if (digits[i] && !digits[i].value) {
              digits[i].value = val;
              say("login-feedback", "");
              if (i < 5 && digits[i + 1]) {
                digits[i + 1].focus();
                digits[i + 1].select();
              }
              if (getEnteredPin().length === 6) {
                submitPin();
              }
              break;
            }
          }
        }
      });
    });

    if (form) {
      form.addEventListener("submit", (e) => {
        e.preventDefault();
        submitPin();
      });
    }

    // Donner le focus au premier champ PIN au chargement
    if (digits[0]) {
      setTimeout(() => digits[0].focus(), 150);
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

    // Le formulaire de PIN reste actif par défaut pour demander la saisie explicite de l'utilisateur
  }

  document.addEventListener("DOMContentLoaded", initPinAndForm);
})();
