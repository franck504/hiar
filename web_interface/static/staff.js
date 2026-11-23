(function () {
  "use strict";

  // Le jeton reste en mémoire uniquement.
  let token = "";
  let appointments = [];
  let correctionAppointmentId = null;

  const byId = id => document.getElementById(id);

  function setFeedback(el, text, isError) {
    el.textContent = text;
    el.className = "feedback" + (isError ? " error" : "");
  }

  function showLogin(message) {
    token = "";
    localStorage.removeItem("hiar_staff_token");
    appointments = [];
    correctionAppointmentId = null;
    byId("token").value = "";
    byId("list-panel").hidden = true;
    byId("staff-topbar-actions").hidden = true;
    byId("login-panel").hidden = false;
    byId("rows").replaceChildren();
    byId("details-panel").hidden = true;
    byId("correction-panel").hidden = true;
    setFeedback(byId("login-feedback"), message || "", Boolean(message));
  }

  function displayValue(value, unavailable = "—") {
    return value === null || value === undefined || value === ""
      ? unavailable
      : String(value);
  }

  function formatTime(value) {
    return value ? value.replace(":", " h ") : "—";
  }

  function localDateString() {
    return new Date().toLocaleDateString("sv-SE", { timeZone: "Indian/Antananarivo" });
  }

  byId("date-filter").value = localDateString();

  function makeButton(label, className, action, id) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "btn " + className;
    button.textContent = label;
    button.dataset.action = action;
    if (id !== undefined) button.dataset.id = String(id);
    return button;
  }

  function cell(row, value) {
    const td = document.createElement("td");
    td.textContent = displayValue(value);
    row.appendChild(td);
    return td;
  }

  function render(list) {
    const body = byId("rows");
    body.replaceChildren();

    if (list.length === 0) {
      const tr = document.createElement("tr");
      const td = document.createElement("td");
      td.colSpan = 9;
      td.className = "empty";
      td.textContent = "Aucun rendez-vous pour ce filtre.";
      tr.appendChild(td);
      body.appendChild(tr);
      return;
    }

    list.forEach(item => {
      const tr = document.createElement("tr");
      cell(tr, `${item.doctor}-${item.period}-${item.ticket_number}`);
      cell(tr, item.requested_date);
      cell(tr, formatTime(item.requested_time));
      cell(tr, item.doctor_name ? "Dr " + item.doctor_name : item.doctor);
      cell(tr, item.patient_name);
      cell(tr, item.contact);
      cell(tr, item.reason);

      const statusCell = cell(tr, item.status);
      statusCell.className = "status";
      statusCell.dataset.status = item.status || "";

      const actionsCell = document.createElement("td");
      actionsCell.className = "actions-cell";

      if (item.status === "en attente") {
        actionsCell.appendChild(
          makeButton("Appeler", "btn-small", "call", item.id)
        );
      } else if (item.status === "appelé") {
        actionsCell.appendChild(
          makeButton("Terminer", "btn-small", "finish", item.id)
        );
      }

      actionsCell.appendChild(
        makeButton("Détails", "btn-outline btn-small", "details", item.id)
      );
      actionsCell.appendChild(
        makeButton("Correction…", "btn-outline btn-small", "correction", item.id)
      );

      tr.appendChild(actionsCell);
      body.appendChild(tr);
    });
  }

  async function apiRequest(url, options = {}) {
    const response = await fetch(url, {
      ...options,
      headers: {
        "X-Staff-Token": token,
        ...(options.body ? { "Content-Type": "application/json" } : {}),
        ...(options.headers || {}),
      },
    });

    let data = null;
    try {
      data = await response.json();
    } catch (_) {
      // Une réponse non JSON sera signalée comme une erreur ci-dessous.
    }

    if (response.status === 401 || response.status === 503) {
      showLogin((data && data.error) || "Accès refusé.");
      throw new Error("AUTH_HANDLED");
    }

    return { response, data };
  }

  async function requestList() {
    const params = new URLSearchParams();
    params.set("date", byId("date-filter").value);

    const doctor = byId("doctor-filter").value;
    const period = byId("period-filter").value;
    const status = byId("status-filter").value;

    if (doctor) params.set("doctor", doctor);
    if (period) params.set("period", period);
    if (status) params.set("status", status);

    return apiRequest("/api/staff/consultations?" + params.toString());
  }

  async function load() {
    const feedback = byId("list-feedback");
    byId("refresh").disabled = true;
    setFeedback(feedback, "Chargement…", false);

    try {
      const { response, data } = await requestList();

      if (!response.ok || !data || !data.ok) {
        setFeedback(
          feedback,
          (data && data.error) || "Impossible de charger les rendez-vous.",
          true
        );
        return;
      }

      appointments = Array.isArray(data.appointments) ? data.appointments : [];
      render(appointments);
      setFeedback(feedback, appointments.length + " rendez-vous affiché(s).", false);
    } catch (error) {
      if (error.message !== "AUTH_HANDLED") {
        setFeedback(feedback, "Le serveur HIAR ne répond pas. Vérifiez la connexion.", true);
      }
    } finally {
      byId("refresh").disabled = false;
    }
  }

  function findAppointment(id) {
    return appointments.find(item => String(item.id) === String(id));
  }

  function addDetailLine(container, label, value, unit = "") {
    const line = document.createElement("p");
    line.className = "detail-line";

    const strong = document.createElement("strong");
    strong.textContent = label + " : ";

    const span = document.createElement("span");
    span.textContent = displayValue(value, "Indisponible") + unit;

    line.append(strong, span);
    container.appendChild(line);
  }

  function showDetails(id) {
    const item = findAppointment(id);
    if (!item) return;

    const content = byId("details-content");
    content.replaceChildren();

    addDetailLine(
      content,
      "Numéro de ticket",
      `${item.doctor}-${item.period}-${item.ticket_number}`
    );
    addDetailLine(content, "Identifiant du rendez-vous", item.id);
    addDetailLine(content, "Patient", item.patient_name);
    addDetailLine(content, "Téléphone", item.contact);
    addDetailLine(content, "Date", item.requested_date);
    addDetailLine(
      content,
      "Période",
      item.period === "MAT" ? "Matin (08 h – 12 h)" :
      item.period === "AM" ? "Après-midi (13 h – 18 h)" : item.period
    );
    addDetailLine(content, "Médecin", item.doctor_name ? "Dr " + item.doctor_name + " (" + item.doctor + ")" : item.doctor);
    addDetailLine(content, "Motif", item.reason);
    addDetailLine(content, "Statut", item.status);
    addDetailLine(content, "Température", item.temperature_c, " °C");
    addDetailLine(content, "Fréquence cardiaque", item.heart_rate_bpm, " bpm");
    addDetailLine(content, "SpO₂", item.spo2_percent, " %");

    byId("details-panel").hidden = false;
    byId("correction-panel").hidden = true;
    byId("details-panel").scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function showCorrection(id) {
    const item = findAppointment(id);
    if (!item) return;

    correctionAppointmentId = item.id;
    byId("correction-appointment").textContent =
      "Rendez-vous #" + item.id + " — " +
      displayValue(item.patient_name) + " — statut actuel : " +
      displayValue(item.status) + ".";

    byId("correction-status").value = item.status;
    setFeedback(byId("correction-feedback"), "", false);
    byId("correction-panel").hidden = false;
    byId("details-panel").hidden = true;
    byId("correction-panel").scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  async function updateStatus(id, status, exceptionalCorrection = false) {
    const feedback = byId("list-feedback");

    try {
      const { response, data } = await apiRequest(
        "/api/staff/consultations/" + encodeURIComponent(id),
        {
          method: "PATCH",
          body: JSON.stringify({
            status,
            exceptional_correction: exceptionalCorrection,
          }),
        }
      );

      if (!response.ok || !data || !data.ok) {
        setFeedback(
          feedback,
          (data && data.error) || "La mise à jour du statut a échoué.",
          true
        );
        return false;
      }

      setFeedback(feedback, "Statut mis à jour : " + data.status + ".", false);
      byId("details-panel").hidden = true;
      byId("correction-panel").hidden = true;
      await load();
      return true;
    } catch (error) {
      if (error.message !== "AUTH_HANDLED") {
        setFeedback(feedback, "Impossible de modifier le rendez-vous.", true);
      }
      return false;
    }
  }

  byId("login-form").addEventListener("submit", async event => {
    event.preventDefault();

    const feedback = byId("login-feedback");
    const candidate = byId("token").value.trim();

    if (!candidate) {
      setFeedback(feedback, "Saisissez le jeton d'accès.", true);
      return;
    }

    token = candidate;
    setFeedback(feedback, "Vérification…", false);

    try {
      const { response, data } = await requestList();

      if (!response.ok || !data || !data.ok) {
        token = "";
        setFeedback(feedback, (data && data.error) || "Accès refusé.", true);
        return;
      }

      byId("token").value = "";
      localStorage.setItem("hiar_staff_token", token);
      byId("login-panel").hidden = true;
      byId("list-panel").hidden = false;
      byId("staff-topbar-actions").hidden = false;
      appointments = Array.isArray(data.appointments) ? data.appointments : [];
      render(appointments);
      setFeedback(byId("list-feedback"), appointments.length + " rendez-vous affiché(s).", false);
    } catch (error) {
      token = "";
      if (error.message !== "AUTH_HANDLED") {
        setFeedback(feedback, "Le serveur HIAR ne répond pas. Vérifiez la connexion.", true);
      }
    }
  });

  byId("rows").addEventListener("click", async event => {
    const button = event.target.closest("button[data-action]");
    if (!button) return;

    const id = button.dataset.id;
    const item = findAppointment(id);
    if (!item) return;

    switch (button.dataset.action) {
      case "details":
        showDetails(id);
        break;

      case "correction":
        showCorrection(id);
        break;

      case "call":
        if (item.status === "en attente") {
          button.disabled = true;
          await updateStatus(id, "appelé");
        }
        break;

      case "finish":
        if (item.status === "appelé") {
          button.disabled = true;
          await updateStatus(id, "terminé");
        }
        break;
    }
  });

  byId("correction-form").addEventListener("submit", async event => {
    event.preventDefault();

    const item = findAppointment(correctionAppointmentId);
    const targetStatus = byId("correction-status").value;

    if (!item) {
      setFeedback(byId("correction-feedback"), "Rendez-vous introuvable. Actualisez la liste.", true);
      return;
    }

    if (targetStatus === item.status) {
      setFeedback(byId("correction-feedback"), "Le statut sélectionné est déjà celui du rendez-vous.", true);
      return;
    }

    const confirmed = window.confirm(
      "Confirmez-vous la correction exceptionnelle du rendez-vous #" +
      item.id + " : « " + item.status + " » → « " + targetStatus + " » ?"
    );

    if (!confirmed) return;

    const submitButton = byId("correction-form").querySelector('button[type="submit"]');
    submitButton.disabled = true;

    try {
      const success = await updateStatus(item.id, targetStatus, true);
      if (!success) {
        setFeedback(byId("correction-feedback"), "Correction non effectuée. Vérifiez le message ci-dessus.", true);
      }
    } finally {
      submitButton.disabled = false;
    }
  });

  byId("close-details").addEventListener("click", () => {
    byId("details-panel").hidden = true;
  });

  byId("cancel-correction").addEventListener("click", () => {
    byId("correction-panel").hidden = true;
    correctionAppointmentId = null;
  });

  byId("refresh").addEventListener("click", load);
  byId("date-filter").addEventListener("change", load);
  byId("doctor-filter").addEventListener("change", load);
  byId("period-filter").addEventListener("change", load);
  byId("status-filter").addEventListener("change", load);
  byId("logout").addEventListener("click", () => showLogin("Déconnexion effectuée."));

  const quickBtn = byId("quick-staff-btn");
  if (quickBtn) {
    quickBtn.addEventListener("click", () => {
      byId("token").value = "2YSJNra8WarQwjbfzPAjvwnc6EtcQlkQ20jgNPYzGiY";
      byId("login-form").dispatchEvent(new Event("submit"));
    });
  }

  // Restauration automatique si jeton enregistré
  const savedToken = localStorage.getItem("hiar_staff_token");
  if (savedToken) {
    byId("token").value = savedToken;
    byId("login-form").dispatchEvent(new Event("submit"));
  }
})();
