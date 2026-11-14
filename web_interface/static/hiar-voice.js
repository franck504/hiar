
(() => {
  "use strict";

  const splash = document.getElementById("hiar-splash");
  const home = document.getElementById("home");
  const bar = document.getElementById("hiar-voice-bar");
  const mic = document.getElementById("hiar-mic");
  const repeat = document.getElementById("hiar-repeat");
  const stop = document.getElementById("hiar-stop");
  const status = document.getElementById("hiar-voice-status");
  const transcript = document.getElementById("hiar-voice-transcript");

  if (!splash || !home || !bar) return;

  let started = false;
  let listening = false;
  let lastSpoken = "Bonjour et bienvenue ! Que puis-je faire pour vous aujourd'hui ?";
  let recognition = null;

  function updateMicButton() {
    mic.classList.toggle("is-listening", listening);
    mic.setAttribute(
      "aria-label",
      listening ? "Arrêter l'écoute vocale" : "Démarrer l'écoute vocale"
    );
    mic.setAttribute("aria-pressed", String(listening));
    mic.title = listening ? "Arrêter l'écoute" : "Parler";
  }

  updateMicButton();

  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;

  function speak(text) {
    lastSpoken = text;
    if (!("speechSynthesis" in window)) {
      status.textContent = "La synthèse vocale n'est pas disponible sur ce navigateur.";
      return;
    }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "fr-FR";
    utterance.rate = 0.95;
    utterance.volume = 1;
    utterance.onstart = () => { status.textContent = "HIAR parle…"; };
    utterance.onend = () => {
      if (!listening) status.textContent = "";
    };
    utterance.onerror = () => { status.textContent = "La lecture vocale n'a pas pu aboutir."; };
    window.speechSynthesis.speak(utterance);
  }

  function enterHome() {
    if (started) return;
    started = true;
    splash.classList.remove("active");
    home.classList.add("active");
    bar.hidden = false;
    document.body.classList.add('hiar-voice-enabled');
    speak(lastSpoken);
  }

  splash.addEventListener("pointerdown", enterHome, { once: true });
  splash.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") enterHome();
  });

  repeat.addEventListener("click", () => speak(lastSpoken));

  stop.addEventListener("click", () => {
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    status.textContent = "Voix arrêtée.";
  });

  function navigate(selector) {
    const target = document.querySelector(selector);
    if (target) {
      target.click();
      return true;
    }
    return false;
  }

  function handleCommand(raw) {
    const command = raw.toLocaleLowerCase("fr-FR")
      .normalize("NFD").replace(/[\u0300-\u036f]/g, "")
      .replace(/[.!?,;:]/g, "").trim();

    if (["orientation", "ouvrir orientation", "menu orientation"].includes(command)) {
      navigate('[data-goto="menu-ORIENTATION"]');
      status.textContent = "Menu Orientation.";
    } else if (["information", "informations", "renseignement", "renseignements", "ouvrir informations"].includes(command)) {
      navigate('[data-goto="menu-INFORMATION"]');
      status.textContent = "Menu Informations.";
    } else if (["consultation", "ouvrir consultation", "menu consultation"].includes(command)) {
      navigate('[data-goto="menu-CONSULTATION"]');
      status.textContent = "Menu Consultation.";
    } else if (["retour a l accueil", "retour accueil", "accueil", "revenir a l accueil"].includes(command)) {
      navigate('[data-goto="home"]');
      status.textContent = "Retour à l'accueil.";
    } else if (["repete", "repeter", "repetez"].includes(command)) {
      speak(lastSpoken);
    } else if (["arrete la voix", "arreter la voix", "stop voix"].includes(command)) {
      if ("speechSynthesis" in window) window.speechSynthesis.cancel();
      status.textContent = "Voix arrêtée.";
    } else if (["arrete l ecoute", "arreter l ecoute", "stop ecoute"].includes(command)) {
      stopListening();
    } else {
      status.textContent = "Je n'ai pas bien compris. Répétez ou choisissez une option sur l'écran.";
      speak("Je n'ai pas bien compris. Pouvez-vous répéter ou choisir une option sur l'écran ?");
    }
  }

  function stopListening() {
    if (recognition && listening) recognition.stop();
    listening = false;
    updateMicButton();
    status.textContent = "Écoute arrêtée.";
  }

  mic.addEventListener("click", () => {
    if (listening) {
      stopListening();
      return;
    }
    if (!Recognition) {
      status.textContent = "La reconnaissance vocale n'est pas prise en charge. Utilisez l'écran tactile.";
      return;
    }
    try {
      recognition = new Recognition();
      recognition.lang = "fr-FR";
      recognition.continuous = false;
      recognition.interimResults = false;

      recognition.onstart = () => {
        listening = true;
        updateMicButton();
        status.textContent = "Je vous écoute…";
      };
      recognition.onresult = (event) => {
        const result = event.results[0][0];
        const spokenText = (result.transcript || "").trim();

        if (transcript && spokenText) {
          transcript.textContent = "Vous : " + spokenText;
          transcript.hidden = false;
        }

        handleCommand(spokenText);
      };
      recognition.onerror = (event) => {
        status.textContent = "Reconnaissance vocale : " + event.error + ". Vous pouvez utiliser l'écran tactile.";
      };
      recognition.onend = () => {
        listening = false;
        updateMicButton();
      };
      recognition.start();
    } catch (error) {
      listening = false;
      updateMicButton();
      status.textContent = "Impossible de démarrer le microphone. Vérifiez l'autorisation du navigateur.";
    }
  });
})();
