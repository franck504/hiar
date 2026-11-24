"""Surveillance et recalage de l'horloge du Raspberry Pi à partir de l'heure de la tablette.

Le Raspberry Pi n'a pas de pile d'horloge (RTC) : sans Internet (point d'accès Wi-Fi du robot),
il redémarre à la dernière date connue. Or c'est SON horloge qui date les rendez-vous
(`requested_date`, `created_at`) : un Pi resté au 18/11 enregistre les patients du 24/11 au 18/11,
et l'onglet « Rendez-vous » du web ne les montre pas.

La tablette Android, elle, est à l'heure (réseau mobile / NTP) et envoie son heure dans chaque
message WebSocket (`ts`, en millisecondes). Ce module :
  * mesure l'écart entre les deux horloges ;
  * recale le Pi (`sudo -n date -s @<epoch>`) si l'écart dépasse 2 minutes, au plus une fois
    toutes les 10 minutes, jamais pendant une mission de guidage. Sans règle sudoers, la commande
    échoue sans rien bloquer : l'écart reste signalé dans les diagnostics.
"""

from dataclasses import dataclass, field
import logging
import os
import subprocess
import time
from typing import Callable, List, Optional

logger = logging.getLogger("hospital_robot.clock_sync")

SKEW_THRESHOLD_S = 120.0           # en dessous : écart normal (latence, horloges légèrement différentes)
RESYNC_MIN_INTERVAL_S = 600.0      # au plus un recalage toutes les 10 minutes
# Bornes de plausibilité : protège contre un `ts` de test (12345) ou d'un appareil lui-même déréglé
MIN_PLAUSIBLE_EPOCH = 1_704_067_200    # 2024-01-01
MAX_PLAUSIBLE_EPOCH = 4_102_444_800    # 2100-01-01


def client_epoch_seconds(ts) -> Optional[float]:
    """Heure du client en secondes Unix (accepte secondes ou millisecondes), ou None si invraisemblable."""
    if isinstance(ts, bool) or not isinstance(ts, (int, float)):
        return None
    value = float(ts)
    if value > 1e11:  # millisecondes
        value /= 1000.0
    if not MIN_PLAUSIBLE_EPOCH <= value <= MAX_PLAUSIBLE_EPOCH:
        return None
    return value


def describe_skew(skew_s: float) -> str:
    """« en retard de 6 j 3 h » / « en avance de 4 min » (skew = client - robot)."""
    sens = "en retard" if skew_s > 0 else "en avance"
    s = abs(int(skew_s))
    days, rest = divmod(s, 86400)
    hours, rest = divmod(rest, 3600)
    minutes = rest // 60
    if days:
        amount = f"{days} j {hours} h" if hours else f"{days} j"
    elif hours:
        amount = f"{hours} h {minutes} min" if minutes else f"{hours} h"
    else:
        amount = f"{max(minutes, 1)} min"
    return f"{sens} de {amount}"


def _default_runner(cmd: List[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=5)


@dataclass
class ClockGuard:
    """Mesure l'écart d'horloge et décide du recalage."""

    enabled: bool = field(default_factory=lambda: os.environ.get("HIAR_CLOCK_SYNC_FROM_MOBILE", "1") != "0")
    now: Callable[[], float] = time.time
    runner: Callable[[List[str]], subprocess.CompletedProcess] = _default_runner
    last_skew_s: Optional[float] = None
    last_seen_at: Optional[float] = None
    last_sync_at: Optional[float] = None
    last_error: Optional[str] = None
    synced: bool = False

    def observe(self, ts, *, mission_active: bool = False) -> Optional[str]:
        """Enregistre l'heure d'un client. Retourne un message à journaliser si une action a eu lieu."""
        client = client_epoch_seconds(ts)
        if client is None:
            return None
        server = self.now()
        self.last_skew_s = client - server
        self.last_seen_at = server
        if abs(self.last_skew_s) < SKEW_THRESHOLD_S:
            return None
        if not self.enabled:
            return f"Horloge du robot {describe_skew(self.last_skew_s)} (recalage automatique désactivé)."
        if mission_active:
            return f"Horloge du robot {describe_skew(self.last_skew_s)} : recalage reporté (mission en cours)."
        if self.last_sync_at is not None and server - self.last_sync_at < RESYNC_MIN_INTERVAL_S:
            return None
        return self._sync(client)

    def _sync(self, client_epoch: float) -> str:
        before = describe_skew(self.last_skew_s or 0.0)
        self.last_sync_at = self.now()
        try:
            result = self.runner(["sudo", "-n", "date", "-s", f"@{int(round(client_epoch))}"])
        except Exception as exc:  # sudo absent, délai dépassé…
            self.last_error = str(exc)
            return f"Horloge du robot {before} : recalage impossible ({exc})."
        if result.returncode != 0:
            self.last_error = (result.stderr or "").strip() or f"code {result.returncode}"
            return (
                f"Horloge du robot {before} : recalage refusé ({self.last_error}). "
                "Lancez scripts/hiar_setup_clock.sh sur le Raspberry Pi."
            )
        self.synced = True
        self.last_error = None
        self.last_skew_s = 0.0
        return f"Horloge du robot recalée sur la tablette (elle était {before})."

    def diagnostics(self) -> dict:
        if self.last_skew_s is None:
            return {"status": "unknown", "skew_s": None, "detail": "En attente de la tablette"}
        if abs(self.last_skew_s) < SKEW_THRESHOLD_S:
            detail = "À l'heure" + (" (recalée sur la tablette)" if self.synced else "")
            return {"status": "ok", "skew_s": round(self.last_skew_s, 1), "detail": detail}
        detail = f"{describe_skew(self.last_skew_s).capitalize()} sur la tablette"
        if self.last_error:
            detail += " — recalage refusé (voir scripts/hiar_setup_clock.sh)"
        return {"status": "warn", "skew_s": round(self.last_skew_s, 1), "detail": detail}
