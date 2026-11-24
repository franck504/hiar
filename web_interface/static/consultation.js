(function () {
  "use strict";

  const TITLES = {
    1: "Motif de consultation",
    2: "Consultations disponibles",
    3: "Vos informations",
    4: "Signes vitaux",
    5: "Vérification",
    6: "Rendez-vous enregistré",
  };

  const REASONS = {
    consultation_generale: "Consultation générale",
    suivi_medical: "Suivi médical",
    autre_motif: "Autre motif",
  };

  const PERIODS = {
    MAT: "Matin (08 h - 12 h)",
    AM: "Après-midi (13 h - 18 h)",
  };

  const PILL = {
    "en attente": ["En attente", "pill-wait"],
    "en cours": ["En cours", "pill-run"],
    "valide": ["Valide", "pill-ok"],
    "indisponible": ["Indisponible", "pill-off"],
  };

  const VITALS = [
    ["temp", "temperature_c", "°C"],
    ["hr", "heart_rate_bpm", "bpm"],
    ["spo2", "spo2_percent", "%"],
  ];

  function freshState() {
    return {
      step: 1,
      date: "",
      reasonCode: null,
      session: null,
      sessions: [],
      vitals: null,
      submitting: false,
      vitalsRunning: false,
      sessionRequest: 0,
      ticketTimer: null,
      countdown: 60,
    };
  }

  let state = freshState();
  const byId = id => document.getElementById(id);

  function setMessage(el, text, kind) {
    el.textContent = text;
    el.className = "feedback" + (kind === "info" ? " info" : "");
  }

  function pad(n) {
    return String(n).padStart(2, "0");
  }

  // ---- Date du ROBOT (et non du navigateur) : c'est elle qui date les rendez-vous ----
  let serverDay = null;
  let clockSkewMs = 0;

  async function syncServerClock() {
    try {
      const res = await fetch("/api/server/time", { cache: "no-store" });
      const body = await res.json();
      if (!body.ok) return;
      serverDay = body.date;
      clockSkewMs = Date.now() - body.epoch_ms;
      showClockWarning();
    } catch (_) { /* hors ligne : on garde la date du navigateur */ }
  }

  function showClockWarning() {
    const id = "hiar-clock-warning";
    let box = document.getElementById(id);
    if (Math.abs(clockSkewMs) < 5 * 60 * 1000) {
      if (box) box.remove();
      return;
    }
    if (!box) {
      box = document.createElement("div");
      box.id = id;
      box.setAttribute("role", "alert");
      box.style.cssText = "margin:12px auto;max-width:1040px;padding:10px 14px;border-radius:12px;" +
        "background:#FEF3C7;color:#B45309;border:1px solid #F59E0B;font-weight:600;font-size:14px";
      const main = document.querySelector("main") || document.body;
      main.prepend(box);
    }
    const robotDate = new Date(serverDay + "T00:00:00").toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric" });
    const days = Math.round(Math.abs(clockSkewMs) / 86400000);
    const ecart = days >= 1 ? days + " jour(s)" : Math.round(Math.abs(clockSkewMs) / 60000) + " minute(s)";
    box.textContent = "⚠ L'horloge du robot indique le " + robotDate + " (écart de " + ecart +
      " avec cet appareil). Les rendez-vous sont affichés à la date du robot. Faites recaler l'heure du Raspberry Pi.";
  }

  function todayISO() {
    return serverDay || new Date().toLocaleDateString("sv-SE", { timeZone: "Indian/Antananarivo" });
  }

  function formatDate(iso) {
    const d = new Date(iso + "T00:00:00");
    return d.toLocaleDateString("fr-FR", {
      weekday: "long",
      day: "numeric",
      month: "long",
      year: "numeric",
    });
  }

  function periodLabel(period) {
    return PERIODS[period] || period;
  }

  function doctorLabel(session) {
    return session.doctor_name ? "Dr " + session.doctor_name : "Médecin " + session.doctor_code;
  }

  function goStep(n) {
    state.step = n;

    document.querySelectorAll("#appointment-screen .consult-step").forEach(el => {
      el.classList.toggle("active", Number(el.dataset.step) === n);
    });

    byId("consult-title").textContent = TITLES[n];

    const progress = byId("consult-progress");
    progress.hidden = n > 5;
    if (n <= 5) {
      progress.textContent = "Étape " + n + " sur 5";
    }

    window.scrollTo(0, 0);
  }

  function fillList(dl, rows) {
    dl.replaceChildren();

    rows.forEach(row => {
      const dt = document.createElement("dt");
      dt.textContent = row[0];

      const dd = document.createElement("dd");
      dd.textContent = row[1];

      dl.append(dt, dd);
    });
  }

  // Étape 1 : choix du motif
  function selectReason(code, button) {
    state.reasonCode = code;

    byId("reason-list").querySelectorAll(".reason-card").forEach(card => {
      const selected = card === button;
      card.classList.toggle("selected", selected);
      card.setAttribute("aria-pressed", selected ? "true" : "false");
    });

    byId("step1-next").disabled = false;
    setMessage(byId("reason-feedback"), "", "info");
  }

  // Étape 2 : sessions de consultation
  function renderSessions() {
    const list = byId("session-list");
    list.replaceChildren();

    state.sessions.forEach(session => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "slot-card";
      button.setAttribute("aria-pressed", "false");

      const title = document.createElement("span");
      title.className = "slot-time";
      title.textContent = doctorLabel(session);

      const period = document.createElement("span");
      period.className = "slot-doctor";
      period.textContent = periodLabel(session.period);

      const waiting = document.createElement("span");
      waiting.className = "slot-state";
      const count = Number(session.waiting_count);
      waiting.textContent = count + (count > 1 ? " patient(s) en attente" : " patient en attente");

      button.append(title, period, waiting);

      button.addEventListener("click", () => {
        state.session = session;

        list.querySelectorAll(".slot-card").forEach(card => {
          card.classList.remove("selected");
          card.setAttribute("aria-pressed", "false");
        });

        button.classList.add("selected");
        button.setAttribute("aria-pressed", "true");
        byId("step2-next").disabled = false;
        setMessage(byId("session-feedback"), "", "info");
      });

      list.appendChild(button);
    });
  }

  async function loadSessions(notice) {
    const feedback = byId("session-feedback");
    const request = ++state.sessionRequest;

    state.session = null;
    state.sessions = [];

    byId("step2-next").disabled = true;
    byId("session-list").replaceChildren();

    if (state.date !== todayISO()) {
      setMessage(feedback, "Les inscriptions sont limitées à aujourd'hui.", "error");
      return;
    }

    setMessage(feedback, "Chargement des consultations disponibles…", "info");

    try {
      const response = await fetch(
        "/api/consultation/sessions?date=" + encodeURIComponent(state.date)
      );
      const data = await response.json();

      if (request !== state.sessionRequest) return;

      if (!response.ok || !data.ok) {
        setMessage(
          feedback,
          data.error || "Impossible de charger les consultations.",
          "error"
        );
        return;
      }

      state.sessions = Array.isArray(data.sessions) ? data.sessions : [];
      renderSessions();

      if (notice) {
        setMessage(feedback, notice, "error");
      } else if (state.sessions.length === 0) {
        setMessage(
          feedback,
          "Aucune session n'accepte actuellement de nouvelles inscriptions.",
          "info"
        );
      } else {
        setMessage(feedback, "", "info");
      }
    } catch (err) {
      if (request !== state.sessionRequest) return;

      setMessage(
        feedback,
        "Le serveur HIAR ne répond pas. Réessayez.",
        "error"
      );
    }
  }

  // Étape 3 : informations du patient
  function readInfo() {
    return {
      name: byId("consult-name").value.trim(),
      contact: byId("consult-contact").value.trim(),
    };
  }

  function validateInfo() {
    const info = readInfo();
    const feedback = byId("info-feedback");

    if (!info.name) {
      setMessage(feedback, "Saisissez votre nom complet.", "error");
      return false;
    }

    if (info.contact.replace(/\D/g, "").length < 8) {
      setMessage(feedback, "Saisissez un numéro de téléphone valide.", "error");
      return false;
    }

    setMessage(feedback, "", "info");
    return true;
  }

  // Étape 4 : constantes réelles, sans valeur simulée
  function setVitals(stateName, values) {
    const pill = PILL[stateName] || PILL["indisponible"];

    VITALS.forEach(item => {
      const pillEl = byId("vital-" + item[0] + "-pill");
      pillEl.textContent = pill[0];
      pillEl.className = "pill " + pill[1];

      const raw = values ? values[item[1]] : null;
      const show = stateName === "valide"
        && typeof raw === "number"
        && isFinite(raw);

      byId("vital-" + item[0] + "-value").textContent =
        show ? raw + " " + item[2] : "-";
    });
  }

  async function acquireVitals() {
    if (state.vitalsRunning) return;

    state.vitalsRunning = true;

    const button = byId("vitals-start");
    const message = byId("vitals-message");

    button.disabled = true;
    setVitals("en cours");
    setMessage(message, "Mesure en cours…", "info");

    try {
      const response = await fetch("/api/vitals/acquire", {
        method: "POST",
      });
      const data = await response.json();

      if (!response.ok || !data.ok || !PILL[data.state]) {
        state.vitals = null;
        setVitals("indisponible");
        setMessage(
          message,
          "La mesure est indisponible pour le moment.",
          "error"
        );
        return;
      }

      state.vitals = data;
      setVitals(data.state, data.values);

      if (data.state === "indisponible") {
        setMessage(
          message,
          data.reason || "Mesure indisponible.",
          "error"
        );
      } else {
        setMessage(message, "", "info");
      }
    } catch (err) {
      state.vitals = null;
      setVitals("indisponible");
      setMessage(message, "Le serveur HIAR ne répond pas.", "error");
    } finally {
      state.vitalsRunning = false;
      button.disabled = false;
    }
  }

  function vitalsSummary() {
    if (!state.vitals || state.vitals.state !== "valide") {
      return "Non mesurés";
    }

    return VITALS.map(item => {
      const raw = state.vitals.values
        ? state.vitals.values[item[1]]
        : null;

      return typeof raw === "number"
        ? raw + " " + item[2]
        : "-";
    }).join(" / ");
  }

  // Étape 5 : récapitulatif
  function buildRecap() {
    const info = readInfo();

    fillList(byId("recap"), [
      ["Motif", REASONS[state.reasonCode] || "Non précisé"],
      ["Date", formatDate(state.date)],
      ["Médecin", doctorLabel(state.session)],
      ["Période", periodLabel(state.session.period)],
      ["Nom", info.name],
      ["Téléphone", info.contact],
      ["Signes vitaux", vitalsSummary()],
    ]);

    setMessage(byId("confirm-feedback"), "", "info");
  }

  function clearTicketTimer() {
    if (state.ticketTimer !== null) {
      window.clearInterval(state.ticketTimer);
      state.ticketTimer = null;
    }
  }

  function finishConsultation() {
    clearTicketTimer();

    state = freshState();

    byId("consult-name").value = "";
    byId("consult-contact").value = "";

    byId("success-message").textContent = "";
    byId("success-queue").textContent = "-";
    byId("queue-block").hidden = false;
    byId("success-recap").replaceChildren();
    byId("ticket-countdown").textContent = "";

    byId("reason-list").querySelectorAll(".reason-card").forEach(card => {
      card.classList.remove("selected");
      card.setAttribute("aria-pressed", "false");
    });

    byId("step1-next").disabled = true;
    byId("step2-next").disabled = true;

    setMessage(byId("reason-feedback"), "", "info");
    setMessage(byId("session-feedback"), "", "info");
    setMessage(byId("info-feedback"), "", "info");
    setMessage(byId("vitals-message"), "", "info");

    setVitals("en attente");
    show("home");
  }

  function startTicketCountdown() {
    clearTicketTimer();
    state.countdown = 60;

    const display = byId("ticket-countdown");

    function updateCountdown() {
      display.textContent =
        "Retour à l'accueil dans " + state.countdown + " secondes.";

      if (state.countdown <= 0) {
        finishConsultation();
        return;
      }

      state.countdown -= 1;
    }

    updateCountdown();
    state.ticketTimer = window.setInterval(updateCountdown, 1000);
  }

  function showSuccess(data) {
    const ticketLabel = data.ticket_label;

    if (typeof ticketLabel === "string" && ticketLabel.trim()) {
      byId("success-queue").textContent = ticketLabel;
      byId("queue-block").hidden = false;
    } else {
      byId("success-queue").textContent = "Indisponible";
      byId("queue-block").hidden = false;
    }

    byId("success-message").textContent =
      data.message || "Votre inscription est enregistrée.";

    fillList(byId("success-recap"), [
      ["Référence", String(data.appointment_id || "-")],
      ["Date", formatDate(state.date)],
      ["Médecin", doctorLabel(state.session)],
      ["Période", periodLabel(state.session.period)],
    ]);

    goStep(6);
    startTicketCountdown();
  }

  function vitalValue(field) {
    if (!state.vitals || state.vitals.state !== "valide" || !state.vitals.values) {
      return null;
    }

    const value = state.vitals.values[field];
    return typeof value === "number" && isFinite(value) ? value : null;
  }

  // Enregistrement auprès de la nouvelle API
  async function submitAppointment() {
    if (state.submitting || !state.session || !state.reasonCode) return;

    state.submitting = true;

    const button = byId("step5-confirm");
    const feedback = byId("confirm-feedback");

    button.disabled = true;
    setMessage(feedback, "Enregistrement en cours…", "info");

    const info = readInfo();

    const payload = {
      patient_name: info.name,
      contact: info.contact,
      reason_code: state.reasonCode,
      requested_date: state.date,
      doctor_code: state.session.doctor_code,
      period: state.session.period,
      temperature_c: vitalValue("temperature_c"),
      heart_rate_bpm: vitalValue("heart_rate_bpm"),
      spo2_percent: vitalValue("spo2_percent"),
    };

    try {
      const response = await fetch("/api/consultation/appointments", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      let data = null;
      try {
        data = await response.json();
      } catch (err) {
        data = null;
      }

      if (response.status === 201 && data && data.ok) {
        showSuccess(data);
        return;
      }

      const code = data && data.code;
      const error = (data && data.error)
        || "Impossible d'enregistrer cette consultation.";

      if (code === "duplicate_phone") {
        setMessage(
          feedback,
          "Ce numéro a déjà une inscription ce jour-là. Utilisez un autre numéro ou contactez l'accueil.",
          "error"
        );
      } else if (code === "session_closed" || code === "registration_closed") {
        goStep(2);
        await loadSessions(
          "Cette session n'accepte plus d'inscriptions. Choisissez une autre session."
        );
      } else if (code === "invalid_phone") {
        goStep(3);
        setMessage(byId("info-feedback"), error, "error");
      } else if (code === "same_day_only") {
        goStep(2);
        setMessage(byId("session-feedback"), error, "error");
      } else {
        setMessage(feedback, error, "error");
      }
    } catch (err) {
      setMessage(
        feedback,
        "Le serveur HIAR ne répond pas. Vérifiez la connexion avant de réessayer.",
        "error"
      );
    } finally {
      state.submitting = false;
      button.disabled = false;
    }
  }

  // Point d'entrée appelé par hmi.js
  window.startConsultation = function () {
    clearTicketTimer();
    state = freshState();

    byId("consult-name").value = "";
    byId("consult-contact").value = "";

    byId("reason-list").querySelectorAll(".reason-card").forEach(card => {
      card.classList.remove("selected");
      card.setAttribute("aria-pressed", "false");
    });

    byId("step1-next").disabled = true;
    byId("step2-next").disabled = true;

    setMessage(byId("reason-feedback"), "", "info");
    setMessage(byId("session-feedback"), "", "info");
    setMessage(byId("info-feedback"), "", "info");
    setMessage(byId("vitals-message"), "", "info");
    setMessage(byId("confirm-feedback"), "", "info");

    setVitals("en attente");

    state.date = todayISO();
    byId("consult-date-label").textContent = formatDate(state.date);

    goStep(1);
    show("appointment-screen");
  };

  // Gestionnaires des motifs
  byId("reason-list").querySelectorAll(".reason-card").forEach(button => {
    button.addEventListener("click", () => {
      selectReason(button.dataset.reason, button);
    });
  });

  byId("step1-next").addEventListener("click", async () => {
    if (!state.reasonCode) return;

    goStep(2);
    await loadSessions();
  });

  // Gestionnaires des sessions
  byId("step2-back").addEventListener("click", () => goStep(1));

  byId("step2-next").addEventListener("click", () => {
    if (!state.session) return;
    goStep(3);
  });

  // Gestionnaires des coordonnées
  byId("step3-back").addEventListener("click", () => goStep(2));

  byId("step3-next").addEventListener("click", () => {
    if (!validateInfo()) return;
    goStep(4);
  });

  // Gestionnaires des constantes
  byId("vitals-start").addEventListener("click", acquireVitals);
  byId("step4-back").addEventListener("click", () => goStep(3));

  byId("step4-next").addEventListener("click", () => {
    buildRecap();
    goStep(5);
  });

  // Confirmation et ticket
  byId("step5-back").addEventListener("click", () => goStep(4));
  byId("step5-confirm").addEventListener("click", submitAppointment);
  byId("finish-consultation").addEventListener("click", finishConsultation);

  const show = window.show || function(id) {
    document.querySelectorAll(".screen").forEach(el => el.classList.toggle("active", el.id === id));
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      syncServerClock().finally(function () {
        if (typeof window.startConsultation === "function") {
          window.startConsultation();
        }
      });
    });
  } else {
    syncServerClock().finally(function () { window.startConsultation(); });
  }
})();
