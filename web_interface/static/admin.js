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

  function unlockAdmin() {
    $("login-panel").hidden = true;
    $("diagnostics-panel").hidden = false;
    $("admin-topbar-actions").hidden = false;
    refreshDiagnostics();
    if (!timer) timer = setInterval(refreshDiagnostics, 3000);
  }

  function lockAdmin(message) {
    clearInterval(timer);
    timer = null;
    localStorage.removeItem("hiar_web_pin");
    $("diagnostics-panel").hidden = true;
    $("admin-topbar-actions").hidden = true;
    $("login-panel").hidden = false;
    const digits = [ $("pin-1"), $("pin-2"), $("pin-3"), $("pin-4") ];
    digits.forEach(d => { if (d) d.value = ""; });
    if (digits[0]) digits[0].focus();
    if (message) say("login-feedback", message);
  }

  function initPinAuth() {
    const form = $("login-form");
    const digits = [ $("pin-1"), $("pin-2"), $("pin-3"), $("pin-4") ];
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

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const enteredPin = getEnteredPin();
      if (enteredPin.length !== 4) {
        say("login-feedback", "Veuillez saisir les 4 chiffres du code PIN.");
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
          localStorage.setItem("hiar_web_pin", enteredPin);
          unlockAdmin();
        } else {
          say("login-feedback", data.error || "Code PIN incorrect.");
          clearDigits();
        }
      } catch (_) {
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

    const refreshBtn = $("diag-refresh-btn");
    if (refreshBtn) refreshBtn.addEventListener("click", refreshDiagnostics);

    const refreshTopBtn = $("diag-refresh-top-btn");
    if (refreshTopBtn) refreshTopBtn.addEventListener("click", refreshDiagnostics);

    const savedPin = localStorage.getItem("hiar_web_pin");
    if (savedPin && savedPin.length === 4) {
      fetch("/api/auth/pin", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pin: savedPin }),
      }).then(r => r.json()).then(data => {
        if (data && data.ok) unlockAdmin();
        else localStorage.removeItem("hiar_web_pin");
      }).catch(() => {});
    }
  }

  document.addEventListener("DOMContentLoaded", initPinAuth);
})();
