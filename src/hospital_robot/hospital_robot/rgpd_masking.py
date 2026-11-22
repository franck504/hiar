"""Utilitaires de pseudonymisation et masquage des données de santé (RGPD Art. 9).

Fournit des fonctions de masquage pour les logs, alertes et affichages publics :
- Masquage des noms et prénoms (ex: "Jean Dupont" -> "J*** D***")
- Masquage des numéros de téléphone (ex: "0601020304" -> "06****0304")
"""

import re
from typing import Optional


def mask_patient_name(name: Optional[str]) -> str:
    """Masque un nom pour la journalisation (RGPD Art. 9)."""
    if not name or not isinstance(name, str):
        return "—"
    parts = name.strip().split()
    if not parts:
        return "—"
    masked_parts = []
    for p in parts:
        if len(p) <= 1:
            masked_parts.append(p)
        else:
            masked_parts.append(f"{p[0]}***")
    return " ".join(masked_parts)


def mask_phone_number(phone: Optional[str]) -> str:
    """Masque un numéro de téléphone pour la journalisation (RGPD Art. 9)."""
    if not phone or not isinstance(phone, str):
        return "—"
    clean = re.sub(r"\s+", "", phone.strip())
    if len(clean) <= 4:
        return "****"
    if len(clean) <= 6:
        return f"{clean[:1]}****{clean[-1:]}"
    return f"{clean[:2]}****{clean[-4:]}"
