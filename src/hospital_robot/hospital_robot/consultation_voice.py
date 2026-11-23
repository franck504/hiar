"""Déroulé vocal de la prise de rendez-vous (consultation) pour le pont WebSocket HMI.

Ce mixin ajoute à `HMIWebSocketBridgeNode` un dialogue guidé, étape par étape, qui reproduit
tout ce que permet l'écran tactile : motif, médecin, nom, téléphone, constantes, confirmation.

Principes
---------
* Le serveur reste la mémoire du dialogue (`_current_consultation_data`, `_current_step`) ; le mobile
  la lui renvoie à chaque changement (`ui/state`) et applique les `fields` que le serveur lui envoie.
* Une donnée vocale remplie fait avancer à la première étape incomplète (`first_missing_step`).
* Le nom et le téléphone ne passent JAMAIS par le LLM (cloud) : ils sont recueillis localement.
* Une action destructrice (annuler) demande confirmation quand la demande est ambiguë (« non »).
* Aucun message ne contient de donnée personnelle ni de constante vitale lue à voix haute.
"""

import re
import time
from typing import Any, Dict, List, Optional

try:
    from hospital_robot import consultation_catalog as catalog
    from hospital_robot.voice_intent_parser import VoiceIntentParser, normalize_text
    from hospital_robot.rgpd_masking import mask_patient_name, mask_phone_number
except ImportError:  # exécution hors paquet installé
    import consultation_catalog as catalog  # type: ignore
    from voice_intent_parser import VoiceIntentParser, normalize_text  # type: ignore
    from rgpd_masking import mask_patient_name, mask_phone_number  # type: ignore

VITALS_GUIDE_SPEECH = (
    "Prise des signes vitaux. Veuillez tenir la sonde de température dans votre main et poser votre "
    "index sur le capteur d'oxymétrie, puis appuyez sur Démarrer la mesure ou dites Mesurer."
)
# Un « annuler » explicite quitte tout de suite (comme le bouton) ; un simple « non » demande confirmation.
CANCEL_WORDS = re.compile(r"\b(annul\w*|quitter|abandon\w*|laisse(?:r)? tomber|je ne veux plus)\b")
PHONE_FRAGMENT_WINDOW_S = 12.0   # durée pendant laquelle des chiffres dictés en plusieurs fois se cumulent
VITALS_MAX_WAIT_S = 40.0         # au-delà, on considère la mesure terminée (délai ESP32 : 32 s)
DRIVEN_STEP_WINDOW_S = 6.0       # le mobile confirme un saut d'étape piloté par le serveur dans ce délai


class ConsultationVoiceMixin:
    """À placer AVANT `Node` dans les bases de `HMIWebSocketBridgeNode`."""

    # ------------------------------------------------------------------ état

    def _init_consultation_dialog(self) -> None:
        self._identity_stage: Optional[str] = None      # name | phone | confirm | which
        self._phone_buffer: str = ""
        self._phone_buffer_at: float = 0.0
        self._phone_failures: int = 0
        self._pending_cancel: bool = False
        self._driven_step: Optional[tuple] = None        # (étape, instant monotone)

    def _reset_consultation_dialog(self, *, clear_data: bool = True) -> None:
        self._identity_stage = None
        self._phone_buffer = ""
        self._phone_buffer_at = 0.0
        self._phone_failures = 0
        self._pending_cancel = False
        self._driven_step = None
        if clear_data:
            self._current_consultation_data.clear()

    def _vitals_measure_running(self) -> bool:
        started = getattr(self, "_vitals_started_at", None)
        return started is not None and time.monotonic() - started < VITALS_MAX_WAIT_S

    def _merge_mobile_form(self, incoming: Dict[str, Any]) -> None:
        """Intègre le formulaire renvoyé par le mobile (saisie tactile).

        Les valeurs vides sont ignorées : le mobile ne peut pas effacer une donnée dictée que son écran
        n'a pas encore appliquée (course entre l'instruction du serveur et son prochain rapport).
        """
        for key, value in (incoming or {}).items():
            if value is None or (isinstance(value, str) and not value.strip()):
                continue
            self._current_consultation_data[key] = value

    def _consult_form(self) -> Dict[str, Optional[str]]:
        return catalog.form_from_data(self._current_consultation_data)

    def _consult_set(
        self,
        *,
        reason: Optional[str] = None,
        doctor: Optional[str] = None,
        name: Optional[str] = None,
        phone: Optional[str] = None,
    ) -> None:
        data = self._current_consultation_data
        if reason:
            data["reason_code"] = data["selected_reason"] = reason
        if doctor:
            period = catalog.doctor_period(doctor)
            data["doctor_code"] = data["selected_doctor"] = doctor
            data["period"] = data["selected_period"] = period
        if name is not None:
            data["patient_name"] = name
        if phone is not None:
            data["contact"] = data["patient_phone"] = phone

    # ------------------------------------------------------------------ émission

    async def _consult_say(
        self,
        speech: str,
        *,
        step: Optional[int] = None,
        fields: Optional[Dict[str, Any]] = None,
        hints: Optional[List[str]] = None,
        action: Optional[str] = None,
        status: str = "Consultation",
        expression: str = "speaking",
    ) -> None:
        """Diffuse une instruction (+ voix) vers le mobile. Sans `step` ni `action`, l'écran ne bouge pas."""
        instruction: Dict[str, Any] = {
            "origin": "voice",
            "text_to_speak": speech,
            "speech_priority": "normal",
            "robot_status": {"face_expression": expression, "status_label": status},
        }
        if step is not None or action is not None:
            ui: Dict[str, Any] = {"screen": "consultation", "require_confirmation": False}
            if step is not None:
                ui["step"] = step
                self._current_step = step
                self._current_screen = "consultation"
                self._driven_step = (step, time.monotonic())
            if action:
                ui["action"] = action
            instruction["instruction_ui"] = ui
        if fields:
            instruction["fields"] = fields
        if hints:
            instruction["voice_hints"] = hints
        await self.broadcast("server/instruction", instruction)
        if speech:
            await self.broadcast(
                "voice/tts/request",
                {"text": speech, "priority": "normal", "screen": "consultation"},
            )

    def _hints_for_step(self, step: int) -> List[str]:
        if step == 1:
            return ["Générale", "Suivi", "Autre", "Annuler"]
        if step == 2:
            return [catalog.doctor_name(c) for c in catalog.DOCTORS] + ["Annuler"]
        if step == 3:
            return ["Suivant", "Précédent", "Annuler"]
        if step == 4:
            return ["Mesurer", "Passer", "Précédent"]
        if step == 5:
            return ["Confirmer", "Précédent", "Annuler"]
        return ["Terminer", "Accueil"]

    # ------------------------------------------------------------------ phrases d'entrée d'étape

    def _identity_prompt(self, form: Dict[str, Optional[str]]) -> str:
        """Phrase de l'étape 3 ; positionne aussi l'étape du dialogue d'identité."""
        if not form.get("name"):
            self._identity_stage = "name"
            return "Quel est votre nom complet ? Vous pouvez aussi le saisir à l'écran."
        if not form.get("phone"):
            self._identity_stage = "phone"
            return "Quel est votre numéro de téléphone ?"
        self._identity_stage = None
        return "Vos coordonnées sont déjà saisies. Dites Suivant pour continuer."

    def _entry_speech(self, step: int, form: Dict[str, Optional[str]]) -> str:
        if step != 3:
            self._identity_stage = None
        if step == 1:
            return "Quel est le motif de votre consultation ? " + catalog.reason_choice_speech()
        if step == 2:
            return "Avec quel médecin souhaitez-vous consulter ? " + catalog.doctors_choice_speech()
        if step == 3:
            return self._identity_prompt(form)
        if step == 4:
            return VITALS_GUIDE_SPEECH
        if step == 5:
            return catalog.recap_speech(form)
        return "Dites Terminer pour revenir à l'accueil."

    async def _consult_goto(self, step: int, lead: str = "") -> None:
        """Passe à `step`, annonce son invite et pousse l'état du formulaire vers le mobile."""
        form = self._consult_form()
        speech = " ".join(part for part in (lead.strip(), self._entry_speech(step, form)) if part)
        await self._consult_say(
            speech,
            step=step,
            fields=catalog.form_fields(form) or None,
            hints=self._hints_for_step(step),
            status=f"Étape {step} sur 5" if step <= 5 else "Rendez-vous enregistré",
        )

    async def _consult_advance_after_fill(self, lead: str) -> None:
        """Après une donnée dictée : première étape incomplète, sinon constantes (ou étape courante)."""
        form = self._consult_form()
        missing = catalog.first_missing_step(form)
        if missing is not None:
            target = missing
        else:
            target = self._current_step if self._current_step >= 4 else 4
        await self._consult_goto(target, lead)

    # ------------------------------------------------------------------ démarrage / annulation

    def _consult_begin(self) -> None:
        """Nouvelle consultation : aucune donnée d'un patient précédent ne doit subsister."""
        self._reset_consultation_dialog(clear_data=True)
        self._current_screen = "consultation"
        self._current_step = 1

    async def _consult_cancel(self) -> None:
        self._reset_consultation_dialog(clear_data=True)
        self._current_screen = "home"
        self._current_step = 1
        speech = "Consultation annulée. Retour à l'accueil."
        await self.broadcast("server/instruction", {
            "origin": "voice",
            "text_to_speak": speech,
            "speech_priority": "normal",
            "instruction_ui": {"screen": "home", "require_confirmation": False},
            "robot_status": {"face_expression": "neutral", "status_label": "Robot prêt"},
            "voice_hints": ["Orientation", "Renseignements", "Consultation"],
        })
        await self.broadcast("voice/tts/request", {"text": speech, "priority": "normal", "screen": "home"})

    # ------------------------------------------------------------------ aiguillage des intentions

    async def _consult_dispatch(self, intent: Any, raw_text: str) -> bool:
        """Traite les intentions de consultation. Retourne True si la réponse a été entièrement émise."""
        if self._pending_orientation:
            return False  # une confirmation de guidage en cours est prioritaire
        kind = intent.intent_type
        in_consult = self._current_screen == "consultation"

        if kind not in ("CONFIRM_YES", "CONFIRM_NO"):
            self._pending_cancel = False

        if in_consult and kind in ("GREETING", "START"):
            # Ces intentions renvoient normalement à l'accueil : un patient qui dit « bonjour » en pleine
            # saisie ne doit pas perdre son dossier.
            return await self._consult_reprompt("Bonjour !" if kind == "GREETING" else "On continue votre rendez-vous.")
        if kind in ("CONSULTATION_REASON", "CONSULTATION_DOCTOR", "CONSULTATION_PERIOD"):
            return await self._consult_fill_intent(intent, in_consult)
        if kind == "CONSULTATION":
            return await self._consult_open(intent, in_consult)
        if not in_consult:
            return False
        if kind == "CONSULTATION_STEP":
            return await self._consult_step(intent.target_value or "next")
        if kind == "CONFIRM_YES":
            return await self._consult_yes()
        if kind == "CONFIRM_NO":
            return await self._consult_no(raw_text)
        if kind == "CONSULTATION_TICKET":
            await self._consult_say(
                "Votre ticket s'affiche à l'écran après la confirmation du rendez-vous.",
                status="Consultation",
            )
            return True
        if kind == "UNKNOWN" and not str(intent.details.get("llm_text_to_speak") or "").strip():
            # Le LLM n'a rien à dire (prompt : étape 3) mais la phrase n'est ni un nom ni un numéro valide :
            # on rappelle simplement ce qui est attendu plutôt que de rester muet.
            return await self._consult_reprompt("Je n'ai pas bien compris.")
        return False

    async def _consult_reprompt(self, lead: str = "") -> bool:
        step = self._current_step
        form = self._consult_form()
        speech = " ".join(p for p in (lead.strip(), self._entry_speech(step, form)) if p)
        await self._consult_say(speech, hints=self._hints_for_step(step), status=f"Étape {step} sur 5")
        return True

    async def _consult_open(self, intent: Any, in_consult: bool) -> bool:
        if intent.ros_request:
            self._publish_hmi_request(intent.ros_request)
        if in_consult:
            if self._current_step >= 6:
                await self._consult_say(
                    "Votre rendez-vous est déjà enregistré. Dites Terminer pour accueillir le patient suivant.",
                    hints=self._hints_for_step(6),
                )
                return True
            return await self._consult_reprompt("Vous êtes déjà dans la prise de rendez-vous.")
        self._consult_begin()
        await self._consult_goto(1, "Très bien, prenons votre rendez-vous.")
        return True

    async def _consult_fill_intent(self, intent: Any, in_consult: bool) -> bool:
        kind = intent.intent_type
        starting = not in_consult
        if starting:
            self._consult_begin()
        if kind == "CONSULTATION_REASON":
            reason = intent.target_value
            if not reason:
                if starting:
                    await self._consult_goto(1, "Je n'ai pas compris le motif.")
                else:
                    await self._consult_reprompt("Je n'ai pas compris le motif.")
                return True
            self._consult_set(reason=reason)
            lead = f"Motif noté : {catalog.REASONS[reason]['label'].lower()}."
        elif kind == "CONSULTATION_DOCTOR":
            code = intent.target_value
            if code not in catalog.DOCTORS:
                lead = "Je n'ai pas reconnu ce médecin."
                if starting:
                    await self._consult_goto(1, lead)
                else:
                    await self._consult_say(
                        f"{lead} {catalog.doctors_choice_speech()} Lequel choisissez-vous ?",
                        hints=self._hints_for_step(2),
                        status="Choix du médecin",
                    )
                return True
            self._consult_set(doctor=code)
            lead = f"Très bien, {catalog.doctor_spoken(code)}, {catalog.PERIODS[catalog.doctor_period(code)]['spoken']}."
        else:  # CONSULTATION_PERIOD
            period = intent.target_value
            speech = (
                f"{catalog.doctors_of_period_speech(period)} Lequel préférez-vous ?"
                if period in catalog.PERIODS
                else catalog.doctors_choice_speech()
            )
            step = 2 if self._consult_form().get("reason") else None
            if step is not None:
                await self._consult_say(speech, step=2, fields=catalog.form_fields(self._consult_form()) or None,
                                        hints=self._hints_for_step(2), status="Choix du médecin")
            elif starting:
                await self._consult_goto(1, "Très bien, prenons votre rendez-vous.")
            else:
                await self._consult_say(speech, hints=self._hints_for_step(2), status="Choix du médecin")
            return True
        await self._consult_advance_after_fill(lead)
        return True

    # ------------------------------------------------------------------ navigation par étapes

    async def _consult_step(self, direction: str) -> bool:
        step = self._current_step
        form = self._consult_form()
        if direction == "prev":
            if step <= 1:
                await self._consult_say(
                    "Vous êtes à la première étape. Dites Annuler pour quitter la consultation.",
                    hints=self._hints_for_step(1),
                )
            elif step >= 6:
                await self._consult_say("Le rendez-vous est enregistré. Dites Terminer pour revenir à l'accueil.",
                                        hints=self._hints_for_step(6))
            else:
                await self._consult_goto(step - 1)
            return True

        # suivant
        if step >= 6:
            await self._consult_say("Votre rendez-vous est déjà enregistré. Dites Terminer pour revenir à l'accueil.",
                                    hints=self._hints_for_step(6))
            return True
        if step == 5:
            return await self._consult_book()
        if step == 4 and self._vitals_measure_running():
            await self._consult_say(
                "La mesure est en cours. Restez immobile, je vous préviens dès qu'elle est terminée.",
                hints=["Annuler"], status="Mesure en cours",
            )
            return True
        missing = catalog.first_missing_step(form)
        if step <= 3 and missing is not None and missing <= step:
            self._identity_stage = None
            if missing == step:
                if step == 3:
                    speech = catalog.validation_message(3, form) + " " + self._identity_prompt(form)
                else:
                    speech = catalog.validation_message(step, form)  # contient déjà les choix
                await self._consult_say(speech, hints=self._hints_for_step(step), status="Information manquante")
            else:
                await self._consult_goto(missing, catalog.validation_message(missing, form, with_choices=False))
            return True
        await self._consult_goto(step + 1)
        return True

    async def _consult_yes(self) -> bool:
        if self._pending_cancel:
            await self._consult_cancel()
            return True
        if self._current_step == 5:
            return await self._consult_book()
        return await self._consult_reprompt("Je n'ai rien à confirmer pour le moment.")

    async def _consult_no(self, raw_text: str) -> bool:
        if self._pending_cancel:
            self._pending_cancel = False
            return await self._consult_reprompt("D'accord, on continue.")
        if CANCEL_WORDS.search(normalize_text(raw_text)) or self._current_step >= 6:
            if self._current_step >= 6:
                await self._consult_say("Dites Terminer pour revenir à l'accueil.", hints=self._hints_for_step(6))
                return True
            await self._consult_cancel()
            return True
        if self._current_step == 5:
            await self._consult_say(
                "D'accord, je ne valide pas. Dites Précédent pour modifier, ou Annuler pour quitter.",
                hints=self._hints_for_step(5),
            )
            return True
        self._pending_cancel = True
        await self._consult_say(
            "Voulez-vous annuler la consultation ? Dites oui pour annuler, ou non pour continuer.",
            hints=["Oui", "Non"],
            status="Annuler la consultation ?",
        )
        return True

    async def _consult_book(self) -> bool:
        form = self._consult_form()
        missing = catalog.first_missing_step(form)
        if missing is not None:
            await self._consult_goto(missing, catalog.validation_message(missing, form, with_choices=False))
            return True
        await self._handle_ui_action({"action_id": "consult.confirm", "args": {}})
        return True

    # ------------------------------------------------------------------ erreurs de réservation

    async def _consult_booking_failed(self, res: Dict[str, Any]) -> None:
        """Garde les données saisies et renvoie le patient à l'étape qui corrige l'erreur."""
        code = res.get("code")
        error = str(res.get("error") or "Impossible d'enregistrer le rendez-vous.")
        data = self._current_consultation_data
        step, lead, extra = 5, f"Attention : {error}", {"booking_error": error}
        if code == "missing_reason":
            step = 1
        elif code in ("missing_doctor", "session_closed", "registration_closed"):
            step = 2
            if code != "missing_doctor":
                lead = f"{error} Choisissez un autre médecin."
        elif code in ("missing_identity", "invalid_phone", "duplicate_phone"):
            step = 3
            if code in ("invalid_phone", "duplicate_phone"):
                lead = f"{error} Donnez-moi un autre numéro de téléphone, ou saisissez-le à l'écran."
                data.pop("contact", None)
                data.pop("patient_phone", None)
                extra["patient_phone"] = ""
        form = self._consult_form()
        speech = lead if step != 5 else f"{lead} Dites Précédent pour modifier, ou Annuler pour quitter."
        if step == 3:
            self._identity_prompt(form)  # positionne l'étape (nom ou téléphone manquant)
            if self._identity_stage is None:
                self._identity_stage = "phone"
        else:
            self._identity_stage = None
        fields = {**catalog.form_fields(form), **extra}
        await self._consult_say(
            speech, step=step, fields=fields, hints=self._hints_for_step(step), status="Erreur d'inscription",
            expression="thinking",
        )

    # ------------------------------------------------------------------ saisie vocale de l'identité

    def _log_identity(self, what: str) -> None:
        self.get_logger().info(f"[IDENTITÉ] {what} (valeurs masquées dans les journaux)")

    async def _consult_identity_voice(self, text: str) -> bool:
        """Recueille nom et téléphone à l'étape 3 SANS appeler le LLM. True si la phrase est traitée."""
        if self._current_screen != "consultation" or self._current_step != 3:
            return False
        norm = normalize_text(text)
        if re.search(VoiceIntentParser.STOP_REGEX, norm):
            return False  # le réflexe d'arrêt d'urgence garde la priorité
        stage = self._identity_stage

        command = catalog.closed_command(text)
        if command == "next":
            return await self._consult_step("next")
        if command == "prev":
            return await self._consult_step("prev")
        if command == "cancel":
            await self._consult_cancel()
            return True

        if stage == "confirm":
            return await self._identity_confirm(norm)
        if stage == "which":
            return await self._identity_which(text)

        digits = catalog.spoken_to_digits(text)
        if stage == "phone" or (stage in (None, "name") and len(digits) >= 8 and not catalog.has_name_intro(text)):
            if digits:
                return await self._identity_phone(digits)
            if not catalog.has_name_intro(text):
                return False  # ni chiffres ni « je m'appelle… » : laisser le LLM décider
        name = catalog.clean_name(text)
        if name and (stage == "name" or catalog.has_name_intro(text)):
            return await self._identity_name(name)
        return False

    async def _identity_name(self, name: str) -> bool:
        self._consult_set(name=name)
        self._log_identity(f"nom reçu {mask_patient_name(name)}")
        form = self._consult_form()
        if form.get("phone"):
            return await self._identity_read_back()
        self._identity_stage = "phone"
        await self._consult_say(
            f"Merci {name}. Quel est votre numéro de téléphone ?",
            fields=catalog.form_fields(form),
            hints=self._hints_for_step(3),
            status="Étape 3 sur 5",
        )
        return True

    async def _identity_phone(self, digits: str) -> bool:
        now = time.monotonic()
        national = catalog.national_phone(digits)  # un numéro complet redit d'un coup remplace tout fragment
        if national is None and self._phone_buffer and now - self._phone_buffer_at <= PHONE_FRAGMENT_WINDOW_S:
            national = catalog.national_phone(self._phone_buffer + digits)
            candidate = self._phone_buffer + digits
        else:
            candidate = digits
        if national is not None:
            self._phone_buffer, self._phone_failures = "", 0
            display = catalog.format_phone_display(national)
            self._consult_set(phone=display)
            self._log_identity(f"téléphone reçu {mask_phone_number(display)}")
            form = self._consult_form()
            if not form.get("name"):
                self._identity_stage = "name"
                await self._consult_say(
                    "Merci. Quel est votre nom complet ?",
                    fields=catalog.form_fields(form), hints=self._hints_for_step(3), status="Étape 3 sur 5",
                )
                return True
            return await self._identity_read_back()

        plausible_prefix = candidate.startswith(("0", "26", "00261"))
        if plausible_prefix and len(candidate) < 10:
            # Numéro dicté en plusieurs fois : on cumule et on invite à continuer.
            self._phone_buffer, self._phone_buffer_at = candidate, now
            await self._consult_say(
                f"J'ai noté {len(candidate)} chiffres : {', '.join(candidate)}. Continuez, je vous écoute.",
                hints=self._hints_for_step(3),
                status="Numéro incomplet",
            )
            return True

        self._phone_buffer = ""
        self._phone_failures += 1
        speech = "Je n'ai pas bien saisi le numéro. Redites-le chiffre par chiffre, en commençant par zéro."
        if self._phone_failures >= 2:
            speech += " Vous pouvez aussi le saisir à l'écran."
        await self._consult_say(speech, hints=self._hints_for_step(3), status="Numéro non compris")
        return True

    async def _identity_read_back(self) -> bool:
        form = self._consult_form()
        national = catalog.national_phone(form.get("phone") or "") or (form.get("phone") or "")
        self._identity_stage = "confirm"
        await self._consult_say(
            f"J'ai noté : {form.get('name')}, téléphone {catalog.format_phone_spoken(national)}. Est-ce correct ?",
            fields=catalog.form_fields(form),
            hints=["Oui", "Non"],
            status="Vérification des coordonnées",
        )
        return True

    async def _identity_confirm(self, norm: str) -> bool:
        yes = bool(re.search(VoiceIntentParser.CONFIRM_YES_REGEX, norm))
        no = bool(re.search(VoiceIntentParser.CONFIRM_NO_REGEX, norm))
        if yes and not no:
            self._identity_stage = None
            await self._consult_goto(4, "Merci, vos coordonnées sont enregistrées.")
            return True
        if no:
            self._identity_stage = "which"
            await self._consult_say(
                "D'accord. Que faut-il corriger : le nom, le numéro, ou les deux ?",
                hints=["Le nom", "Le numéro", "Les deux"],
                status="Correction",
            )
            return True
        await self._consult_say("Dites oui si c'est correct, ou non pour corriger.", hints=["Oui", "Non"])
        return True

    async def _identity_which(self, text: str) -> bool:
        which = catalog.which_field_to_correct(text)
        if which is None:
            await self._consult_say("Voulez-vous corriger le nom, le numéro, ou les deux ?",
                                    hints=["Le nom", "Le numéro", "Les deux"])
            return True
        data = self._current_consultation_data
        if which in ("name", "both"):
            data.pop("patient_name", None)
            self._identity_stage = "name"
            speech = "Très bien. Quel est votre nom complet ?"
            fields = {"patient_name": ""}
        if which in ("phone", "both"):
            data.pop("contact", None)
            data.pop("patient_phone", None)
            self._phone_buffer = ""
            fields = {**(fields if which == "both" else {}), "patient_phone": ""}
            if which == "phone":
                self._identity_stage = "phone"
                speech = "Très bien. Quel est votre numéro de téléphone ?"
        await self._consult_say(speech, fields=fields, hints=self._hints_for_step(3), status="Étape 3 sur 5")
        return True
