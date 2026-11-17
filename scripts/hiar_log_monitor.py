#!/usr/bin/env python3
"""Moniteur de logs unifié HIAR pour Raspberry Pi.

Agrège et formate en temps réel tous les logs des nœuds ROS 2, du pont WebSocket
mobile, de l'ESP32, du LLM et de l'interface Web avec des tags de source clairs :
  [MOBILE], [ESP32], [OBSTACLE], [SUPERVISOR], [NAVIGATION],
  [HMI_REQ], [HMI_BRIDGE], [LLM], [WEB], [SYSTEM]
"""

import argparse
from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path
import re
import sys
import time
from typing import Dict, Iterable, List, Optional, Set, Tuple

# Mapping des noms de nœuds ROS 2 -> Tags courts normalisés
NODE_TO_TAG: Dict[str, str] = {
    "esp32_interface": "ESP32",
    "obstacle_detector": "OBSTACLE",
    "robot_supervisor": "SUPERVISOR",
    "navigation_decision": "NAVIGATION",
    "hmi_request_receiver": "HMI_REQ",
    "hmi_websocket_bridge": "HMI_BRIDGE",
    "launch": "SYSTEM",
}

TAG_COLORS: Dict[str, str] = {
    "MOBILE": "\033[1;36m",      # Cyan vif
    "ESP32": "\033[1;35m",       # Magenta vif
    "OBSTACLE": "\033[1;33m",    # Jaune vif
    "SUPERVISOR": "\033[1;34m",  # Bleu vif
    "NAVIGATION": "\033[1;32m",  # Vert vif
    "HMI_REQ": "\033[0;37m",     # Blanc
    "HMI_BRIDGE": "\033[0;36m",  # Cyan
    "LLM": "\033[0;35m",         # Magenta
    "WEB": "\033[0;32m",         # Vert
    "SYSTEM": "\033[0;90m",      # Gris
}

LEVEL_COLORS: Dict[str, str] = {
    "ERROR": "\033[1;31m",
    "FATAL": "\033[1;31m",
    "WARN": "\033[1;33m",
    "INFO": "\033[0;37m",
    "DEBUG": "\033[0;90m",
}

LEVEL_ORDER: Dict[str, int] = {
    "DEBUG": 10,
    "INFO": 20,
    "WARN": 30,
    "ERROR": 40,
    "FATAL": 50,
}

RESET = "\033[0m"
DIM = "\033[2m"

# Regex ROS 2 standard :
# [esp32_interface-1] [INFO] [1794940939.946829467] [esp32_interface]: Message...
RE_ROS_NODE_FULL = re.compile(
    r"^\[(?P<proc>[a-zA-Z0-9_]+)-\d+\]\s+"
    r"\[(?P<level>DEBUG|INFO|WARN|WARNING|ERROR|FATAL)\]\s+"
    r"\[(?P<epoch>\d+(?:\.\d+)?)\]\s+"
    r"\[(?P<logger>[^\]]+)\]:\s*(?P<msg>.*)$"
)

# Regex python logging à l'intérieur d'un nœud ROS 2 :
# [hmi_websocket_bridge-6] 2026-11-17 21:42:42,141 [INFO] connection open
RE_ROS_PYLOG = re.compile(
    r"^\[(?P<proc>[a-zA-Z0-9_]+)-\d+\]\s+"
    r"(?P<dt>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})(?:,\d+)?\s+"
    r"\[(?P<level>DEBUG|INFO|WARN|WARNING|ERROR|FATAL)\]\s*(?P<msg>.*)$"
)

# Regex générique préfixé par un processus launch :
# [esp32_interface-1] Texte brut...
RE_ROS_PROC_GENERIC = re.compile(
    r"^\[(?P<proc>[a-zA-Z0-9_]+)-\d+\]\s+(?P<msg>.*)$"
)

# Regex launch ROS 2 :
# [INFO] [launch]: ... ou [INFO] [esp32_interface-1]: process started with pid [3039]
RE_ROS_LAUNCH = re.compile(
    r"^\[(?P<level>DEBUG|INFO|WARN|WARNING|ERROR|FATAL)\]\s+"
    r"\[(?P<src>[^\]]+)\]:\s*(?P<msg>.*)$"
)

# Regex tag explicite en début de message : [MOBILE] ..., [ESP32] ..., [LLM] ...
RE_EXPLICIT_TAG = re.compile(
    r"^\[(?P<tag>MOBILE|ESP32|OBSTACLE|SUPERVISOR|NAVIGATION|HMI_REQ|HMI_BRIDGE|LLM|WEB|SYSTEM)\]\s*(?P<rest>.*)$"
)

# Regex Werkzeug / Flask HTTP access log :
# 192.168.43.1 - - [17/Nov/2026 21:42:42] "GET / HTTP/1.1" 200 -
RE_WERKZEUG = re.compile(
    r'^(?P<ip>\S+)\s+-\s+-\s+\[(?P<dt>[^\]]+)\]\s+"(?P<req>[^"]+)"\s+(?P<status>\d+)\s+.*$'
)

# Regex journalctl syslog prefix :
# Nov 17 21:42:20 cecilia-desktop hiar_start.sh[1234]: ...
RE_JOURNAL_PREFIX = re.compile(
    r"^[A-Z][a-z]{2}\s+\d+\s+\d{2}:\d{2}:\d{2}\s+\S+\s+\S+?:\s*(?P<rest>.*)$"
)


@dataclass
class LogEntry:
    timestamp: str
    level: str
    tag: str
    message: str


def _normalize_level(raw: str) -> str:
    upper = raw.upper()
    if upper == "WARNING":
        return "WARN"
    if upper in LEVEL_ORDER:
        return upper
    return "INFO"


def _epoch_to_hms(epoch_str: str) -> str:
    try:
        dt = datetime.fromtimestamp(float(epoch_str))
        return dt.strftime("%H:%M:%S")
    except Exception:
        return datetime.now().strftime("%H:%M:%S")


def _infer_tag_from_content(default_tag: str, message: str) -> Tuple[str, str]:
    """Détecte un tag explicite ([MOBILE], [LLM], [ESP32], etc.) ou le déduit du contenu."""
    match = RE_EXPLICIT_TAG.match(message.strip())
    if match:
        return match.group("tag"), match.group("rest").strip()

    lower = message.lower()
    if default_tag == "HMI_BRIDGE":
        if any(k in lower for k in (
            "client connected",
            "client disconnected",
            "tactile action",
            "mobile ui",
            "duplicate stt",
            "voix stt",
            "connection open",
            "connection closed",
        )):
            return "MOBILE", message
        if any(k in lower for k in ("llm", "qwen", "ollama")):
            return "LLM", message

    return default_tag, message


def parse_log_line(raw_line: str, source_hint: str = "ros2") -> Optional[LogEntry]:
    """Parse une ligne brute (ROS 2, Flask ou journald) en LogEntry unifiée."""
    line = raw_line.rstrip("\r\n").strip()
    if not line:
        return None

    # Retirer un éventuel préfixe syslog/journalctl
    j_match = RE_JOURNAL_PREFIX.match(line)
    if j_match:
        line = j_match.group("rest").strip()

    now_hms = datetime.now().strftime("%H:%M:%S")

    # 1. Source Web / Flask
    if source_hint == "web":
        w_match = RE_WERKZEUG.match(line)
        if w_match:
            status = int(w_match.group("status"))
            level = "ERROR" if status >= 500 else ("WARN" if status >= 400 else "INFO")
            # Extraire HH:MM:SS depuis [17/Nov/2026 21:42:42]
            dt_parts = w_match.group("dt").split()
            hms = dt_parts[1] if len(dt_parts) >= 2 else now_hms
            msg = f"{w_match.group('ip')} {w_match.group('req')} -> {status}"
            return LogEntry(timestamp=hms, level=level, tag="WEB", message=msg)

        level = "WARN" if "warning" in line.lower() else (
            "ERROR" if "error" in line.lower() or "traceback" in line.lower() else "INFO"
        )
        tag, clean_msg = _infer_tag_from_content("WEB", line)
        return LogEntry(timestamp=now_hms, level=level, tag=tag, message=clean_msg)

    # 2. ROS 2 nœud standard complet
    m = RE_ROS_NODE_FULL.match(line)
    if m:
        proc = m.group("proc")
        level = _normalize_level(m.group("level"))
        hms = _epoch_to_hms(m.group("epoch"))
        base_tag = NODE_TO_TAG.get(proc, proc.upper())
        tag, clean_msg = _infer_tag_from_content(base_tag, m.group("msg").strip())
        return LogEntry(timestamp=hms, level=level, tag=tag, message=clean_msg)

    # 3. Logging Python dans un nœud ROS 2 (ex: websockets, urllib, llm_intent_engine)
    m = RE_ROS_PYLOG.match(line)
    if m:
        proc = m.group("proc")
        level = _normalize_level(m.group("level"))
        hms = m.group("dt").split()[-1]
        base_tag = NODE_TO_TAG.get(proc, proc.upper())
        tag, clean_msg = _infer_tag_from_content(base_tag, m.group("msg").strip())
        return LogEntry(timestamp=hms, level=level, tag=tag, message=clean_msg)

    # 4. ROS 2 Launch lifecycle
    m = RE_ROS_LAUNCH.match(line)
    if m:
        level = _normalize_level(m.group("level"))
        src = re.sub(r"-\d+$", "", m.group("src"))
        base_tag = NODE_TO_TAG.get(src, "SYSTEM")
        tag, clean_msg = _infer_tag_from_content(base_tag, m.group("msg").strip())
        return LogEntry(timestamp=now_hms, level=level, tag=tag, message=clean_msg)

    # 5. Ligne préfixée par [nom_noeud-N] sans format rclpy (ex: print ou traceback)
    m = RE_ROS_PROC_GENERIC.match(line)
    if m:
        proc = m.group("proc")
        base_tag = NODE_TO_TAG.get(proc, proc.upper())
        msg = m.group("msg").strip()
        level = "ERROR" if any(k in msg.lower() for k in ("error", "exception", "traceback")) else "INFO"
        tag, clean_msg = _infer_tag_from_content(base_tag, msg)
        return LogEntry(timestamp=now_hms, level=level, tag=tag, message=clean_msg)

    # 6. Fallback générique
    tag, clean_msg = _infer_tag_from_content("SYSTEM", line)
    level = "ERROR" if "error" in clean_msg.lower() else ("WARN" if "warn" in clean_msg.lower() else "INFO")
    return LogEntry(timestamp=now_hms, level=level, tag=tag, message=clean_msg)


def format_entry(entry: LogEntry, use_color: bool = True) -> str:
    """Formate une LogEntry avec alignement fixe et couleurs ANSI optionnelles."""
    tag_padded = f"[{entry.tag}]".ljust(12)
    level_padded = f"[{entry.level:<5}]"
    if not use_color:
        return f"{entry.timestamp} {level_padded} {tag_padded} {entry.message}"

    t_color = TAG_COLORS.get(entry.tag, "\033[1;37m")
    l_color = LEVEL_COLORS.get(entry.level, "\033[0;37m")
    return (
        f"{DIM}{entry.timestamp}{RESET} "
        f"{l_color}{level_padded}{RESET} "
        f"{t_color}{tag_padded}{RESET} "
        f"{entry.message}"
    )


def discover_default_log_files() -> List[Tuple[Path, str]]:
    """Détecte automatiquement les fichiers de logs actifs sur le Raspberry Pi."""
    home = Path.home()
    sources: List[Tuple[Path, str]] = []

    ros_candidates = [
        home / "hiar_logs" / "latest.log",
        home / "ros2.log",
    ]
    # Choisir le fichier ROS 2 le plus récemment modifié parmi ceux existants
    existing_ros = [p for p in ros_candidates if p.exists()]
    if existing_ros:
        best_ros = max(existing_ros, key=lambda p: p.stat().st_mtime)
        sources.append((best_ros, "ros2"))

    web_candidates = [
        home / "hiar_logs" / "web_latest.log",
        home / "web_interface.log",
    ]
    existing_web = [p for p in web_candidates if p.exists()]
    if existing_web:
        best_web = max(existing_web, key=lambda p: p.stat().st_mtime)
        sources.append((best_web, "web"))

    return sources


class _FileTailer:
    """Suit un fichier en gérant automatiquement la rotation et les liens symboliques."""

    def __init__(self, path: Path, source_hint: str, initial_lines: int = 40):
        self.path = path
        self.source_hint = source_hint
        self.initial_lines = initial_lines
        self._fp = None
        self._inode: Optional[int] = None
        self._open(initial=True)

    def _open(self, initial: bool = False):
        self.close()
        if not self.path.exists():
            return
        try:
            st = os.stat(self.path)
            self._fp = open(self.path, "r", encoding="utf-8", errors="replace")
            self._inode = st.st_ino
            if initial and self.initial_lines >= 0:
                lines = self._fp.readlines()
                self._buffered = lines[-self.initial_lines:] if self.initial_lines > 0 else []
            else:
                self._buffered = []
        except OSError:
            self._fp = None
            self._inode = None
            self._buffered = []

    def read_new_lines(self) -> List[str]:
        out: List[str] = []
        if getattr(self, "_buffered", None):
            out.extend(self._buffered)
            self._buffered = []

        if self._fp is None:
            self._open(initial=False)
            if self._fp is None:
                return out

        # Vérifier rotation / remplacement du fichier ou symlink
        try:
            st = os.stat(self.path)
            if st.st_ino != self._inode or st.st_size < self._fp.tell():
                self._open(initial=False)
        except OSError:
            return out

        if self._fp is not None:
            while True:
                line = self._fp.readline()
                if not line:
                    break
                out.append(line)
        return out

    def close(self):
        if self._fp is not None:
            try:
                self._fp.close()
            except Exception:
                pass
            self._fp = None


def should_emit(entry: LogEntry, allowed_tags: Optional[Set[str]], min_level: int) -> bool:
    if LEVEL_ORDER.get(entry.level, 20) < min_level:
        return False
    if allowed_tags and entry.tag.upper() not in allowed_tags:
        return False
    return True


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Affiche les logs unifiés HIAR avec tags de source ([MOBILE], [ESP32], [NAVIGATION], etc.)."
    )
    parser.add_argument(
        "--tag",
        default="",
        help="Filtrer par tags séparés par des virgules (ex: MOBILE,ESP32,NAVIGATION).",
    )
    parser.add_argument(
        "--level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARN", "ERROR"],
        help="Niveau minimum de sévérité (défaut: INFO).",
    )
    parser.add_argument(
        "--lines",
        type=int,
        default=40,
        help="Nombre de dernières lignes à afficher par source au démarrage (défaut: 40).",
    )
    parser.add_argument(
        "--no-follow",
        action="store_true",
        help="Afficher les dernières lignes et quitter sans suivre en temps réel.",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Désactiver les couleurs ANSI.",
    )
    parser.add_argument("--ros-log", type=str, default="", help="Chemin explicite du fichier log ROS 2.")
    parser.add_argument("--web-log", type=str, default="", help="Chemin explicite du fichier log Web.")
    parser.add_argument(
        "--save",
        type=str,
        default="",
        help="Enregistrer également la sortie formatée (sans couleurs) dans ce fichier.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    allowed_tags: Optional[Set[str]] = None
    if args.tag.strip():
        allowed_tags = {t.strip().upper() for t in args.tag.split(",") if t.strip()}

    min_level = LEVEL_ORDER[args.level]
    use_color = (not args.no_color) and sys.stdout.isatty()

    sources: List[Tuple[Path, str]] = []
    if args.ros_log:
        sources.append((Path(args.ros_log), "ros2"))
    if args.web_log:
        sources.append((Path(args.web_log), "web"))
    if not sources:
        sources = discover_default_log_files()

    if not sources:
        print("Aucun fichier de log HIAR trouvé (~/hiar_logs/latest.log, ~/ros2.log, ~/web_interface.log).", file=sys.stderr)
        return 1

    save_fp = None
    if args.save:
        save_path = Path(args.save)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_fp = open(save_path, "a", encoding="utf-8")

    tailers = [_FileTailer(p, hint, initial_lines=args.lines) for p, hint in sources]

    header_tags = ",".join(sorted(allowed_tags)) if allowed_tags else "TOUS"
    sources_str = ", ".join(f"{hint}:{p}" for p, hint in sources)
    print(f"=== 📋 HIAR LOGS UNIFIÉS | Tags: {header_tags} | Niveau: {args.level}+ | Sources: {sources_str} ===", flush=True)

    try:
        while True:
            had_output = False
            for tailer in tailers:
                for raw_line in tailer.read_new_lines():
                    entry = parse_log_line(raw_line, source_hint=tailer.source_hint)
                    if entry is None:
                        continue
                    if not should_emit(entry, allowed_tags, min_level):
                        continue
                    print(format_entry(entry, use_color=use_color), flush=True)
                    if save_fp is not None:
                        save_fp.write(format_entry(entry, use_color=False) + "\n")
                        save_fp.flush()
                    had_output = True

            if args.no_follow:
                break
            if not had_output:
                time.sleep(0.2)
    except KeyboardInterrupt:
        pass
    finally:
        for t in tailers:
            t.close()
        if save_fp is not None:
            save_fp.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
