#!/usr/bin/env python3
"""Générateur du logo officiel HIAR (Tête de robot céramique transparente).

Génère le logo au format PNG avec canal alpha transparent (aucun arrière-plan),
puis l'exporte dans toutes les résolutions nécessaires pour l'application Mobile (Flutter / Android)
et l'interface Web (Favicon, Navbar, En-têtes).
"""

import os
import subprocess
from pathlib import Path
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent

SVG_CONTENT = '''<svg width="1024" height="1024" viewBox="-360 -340 720 720" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <!-- Dégradé coque céramique blanche 3D -->
    <radialGradient id="shellGradient" cx="46%" cy="28%" r="72%" fx="42%" fy="22%">
      <stop offset="0%" stop-color="#FFFFFF" />
      <stop offset="58%" stop-color="#F6FAFD" />
      <stop offset="86%" stop-color="#E3EEF6" />
      <stop offset="100%" stop-color="#CBDCEB" />
    </radialGradient>

    <!-- Reflet spéculaire supérieur sur la coque -->
    <linearGradient id="topHighlight" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#FFFFFF" stop-opacity="0.95" />
      <stop offset="100%" stop-color="#FFFFFF" stop-opacity="0.0" />
    </linearGradient>

    <!-- Dégradé oreilles acoustiques latérales -->
    <linearGradient id="earGradient" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#F7FBFE" />
      <stop offset="50%" stop-color="#DCE9F3" />
      <stop offset="100%" stop-color="#B9D0E2" />
    </linearGradient>

    <!-- Accent sarcelle / bleu HIAR -->
    <linearGradient id="tealAccent" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#14B8A6" />
      <stop offset="100%" stop-color="#0B4F7C" />
    </linearGradient>

    <!-- Visière sombre profonde -->
    <radialGradient id="visorGradient" cx="50%" cy="35%" r="70%">
      <stop offset="0%" stop-color="#15324B" />
      <stop offset="55%" stop-color="#0B1C2E" />
      <stop offset="100%" stop-color="#06101B" />
    </radialGradient>

    <!-- Reflet vitré diagonal subtil sur la visière -->
    <linearGradient id="visorGlassSheen" x1="15%" y1="0%" x2="75%" y2="100%">
      <stop offset="0%" stop-color="#FFFFFF" stop-opacity="0.16" />
      <stop offset="38%" stop-color="#FFFFFF" stop-opacity="0.04" />
      <stop offset="42%" stop-color="#FFFFFF" stop-opacity="0.0" />
      <stop offset="100%" stop-color="#22D3EE" stop-opacity="0.04" />
    </linearGradient>

    <!-- Halo lumineux cyan des yeux et du sourire -->
    <filter id="luminousGlow" x="-30%" y="-30%" width="160%" height="160%">
      <feGaussianBlur stdDeviation="5" result="blur1" />
      <feGaussianBlur stdDeviation="12" result="blur2" />
      <feMerge>
        <feMergeNode in="blur2" />
        <feMergeNode in="blur1" />
        <feMergeNode in="SourceGraphic" />
      </feMerge>
    </filter>

    <!-- Ombre douce interne de la visière -->
    <filter id="visorInsetShadow" x="-10%" y="-10%" width="120%" height="120%">
      <feDropShadow dx="0" dy="4" stdDeviation="6" flood-color="#030911" flood-opacity="0.65" />
    </filter>

    <!-- Joues chaleureuses lors du sourire -->
    <radialGradient id="cheekBlush" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#2DD4BF" stop-opacity="0.36" />
      <stop offset="60%" stop-color="#22D3EE" stop-opacity="0.12" />
      <stop offset="100%" stop-color="#22D3EE" stop-opacity="0.0" />
    </radialGradient>

    <!-- Découpe de la visière -->
    <clipPath id="visorClip">
      <rect x="-215" y="-128" width="430" height="256" rx="116" ry="116" />
    </clipPath>
  </defs>

  <!-- 1. Base / Cou minimaliste -->
  <g id="neckAssembly" transform="translate(0, 218)">
    <path d="M -68 -14 C -68 18, 68 18, 68 -14 C 48 -6, -48 -6, -68 -14 Z" fill="url(#earGradient)" />
    <ellipse cx="0" cy="-14" rx="68" ry="12" fill="#B5CCE0" />
    <path d="M -52 2 Q 0 14 52 2" fill="none" stroke="#0A7C78" stroke-width="3.5" stroke-linecap="round" opacity="0.65" />
  </g>

  <!-- 2. Oreilles acoustiques latérales -->
  <g id="leftEar" transform="translate(-268, 8)">
    <rect x="-24" y="-58" width="42" height="116" rx="21" fill="url(#earGradient)" stroke="#C6D9E8" stroke-width="2.5" />
    <rect x="-12" y="-34" width="8" height="68" rx="4" fill="url(#tealAccent)" opacity="0.85" />
  </g>

  <g id="rightEar" transform="translate(268, 8)">
    <rect x="-18" y="-58" width="42" height="116" rx="21" fill="url(#earGradient)" stroke="#C6D9E8" stroke-width="2.5" />
    <rect x="4" y="-34" width="8" height="68" rx="4" fill="url(#tealAccent)" opacity="0.85" />
  </g>

  <!-- 3. Coque principale céramique blanche arrondie -->
  <rect x="-262" y="-198" width="524" height="396" rx="182" ry="182" fill="url(#shellGradient)" stroke="#D5E4F0" stroke-width="3" />

  <!-- Liseré supérieur sarcelle discret -->
  <path d="M -46 -196 Q 0 -199 46 -196" fill="none" stroke="#0A7C78" stroke-width="4" stroke-linecap="round" opacity="0.60" />

  <!-- Reflet crânien supérieur doux -->
  <ellipse cx="0" cy="-145" rx="165" ry="38" fill="url(#topHighlight)" opacity="0.85" />

  <!-- 4. Petite croix médicale JAUNE officielle HIAR sur le front -->
  <g id="foreheadCross" transform="translate(0, -152)">
    <rect x="-4.5" y="-13" width="9" height="26" rx="3.5" fill="#FBBF24" stroke="#F59E0B" stroke-width="1.2" />
    <rect x="-13" y="-4.5" width="26" height="9" rx="3.5" fill="#FBBF24" stroke="#F59E0B" stroke-width="1.2" />
  </g>

  <!-- 5. Cadre satiné de la visière -->
  <rect x="-224" y="-137" width="448" height="274" rx="125" ry="125" fill="#DCE8F2" />
  <rect x="-221" y="-134" width="442" height="268" rx="122" ry="122" fill="#F8FBFE" opacity="0.75" />

  <!-- 6. Visière sombre profonde -->
  <rect x="-215" y="-128" width="430" height="256" rx="116" ry="116" fill="url(#visorGradient)" filter="url(#visorInsetShadow)" />

  <!-- 7. Contenu interne de la visière clippée -->
  <g clip-path="url(#visorClip)">
    <!-- Reflet de verre courbé -->
    <path d="M -230 -140 L 110 -140 L -30 140 L -230 140 Z" fill="url(#visorGlassSheen)" />
    <path d="M -175 -102 Q 0 -122 175 -102" fill="none" stroke="#FFFFFF" stroke-width="3" stroke-linecap="round" opacity="0.14" />

    <!-- Joues lumineuses souriantes -->
    <ellipse cx="-126" cy="44" rx="38" ry="22" fill="url(#cheekBlush)" opacity="0.70" />
    <ellipse cx="126" cy="44" rx="38" ry="22" fill="url(#cheekBlush)" opacity="0.70" />

    <!-- ŒIL GAUCHE -->
    <g id="leftEye" transform="translate(-96, -10)">
      <ellipse cx="0" cy="0" rx="24" ry="34" fill="#22D3EE" stroke="#67E8F9" stroke-width="2" filter="url(#luminousGlow)" />
      <circle cx="-8" cy="-11" r="7.5" fill="#FFFFFF" opacity="0.95" />
      <circle cx="8" cy="9" r="3.2" fill="#FFFFFF" opacity="0.70" />
    </g>

    <!-- ŒIL DROIT -->
    <g id="rightEye" transform="translate(96, -10)">
      <ellipse cx="0" cy="0" rx="24" ry="34" fill="#22D3EE" stroke="#67E8F9" stroke-width="2" filter="url(#luminousGlow)" />
      <circle cx="-8" cy="-11" r="7.5" fill="#FFFFFF" opacity="0.95" />
      <circle cx="8" cy="9" r="3.2" fill="#FFFFFF" opacity="0.70" />
    </g>

    <!-- BOUCHE SOURIANTE CHALEUREUSE -->
    <path d="M -44 34 Q 0 72 44 34" fill="none" stroke="#22D3EE" stroke-width="7" stroke-linecap="round" filter="url(#luminousGlow)" />
  </g>
</svg>
'''


def generate_pngs():
    tmp_svg = PROJECT_ROOT / "scripts" / "hiar_robot_head.svg"
    tmp_html = PROJECT_ROOT / "scripts" / "hiar_robot_head.html"
    master_png = PROJECT_ROOT / "scripts" / "hiar_robot_head_1024.png"

    with open(tmp_svg, "w", encoding="utf-8") as f:
        f.write(SVG_CONTENT)

    html_wrapper = f"""<!DOCTYPE html>
<html>
<head>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html, body {{
    background: transparent !important;
    width: 1024px;
    height: 1024px;
    overflow: hidden;
  }}
  svg {{
    width: 100%;
    height: 100%;
    display: block;
  }}
</style>
</head>
<body>
{SVG_CONTENT}
</body>
</html>"""

    with open(tmp_html, "w", encoding="utf-8") as f:
        f.write(html_wrapper)

    cmd = [
        "google-chrome",
        "--headless=new",
        f"--screenshot={master_png}",
        "--default-background-color=00000000",
        "--window-size=1024,1024",
        f"file://{tmp_html.resolve()}",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"Chrome screenshot failed: {res.stderr}")

    im = Image.open(master_png).convert("RGBA")
    print(f"Master image generated: {im.size}, mode: {im.mode}")

    # Vérification stricte de la transparence
    corners = [im.getpixel((0, 0)), im.getpixel((0, 1023)), im.getpixel((1023, 0)), im.getpixel((1023, 1023))]
    alphas = [c[3] for c in corners]
    assert all(a == 0 for a in alphas), f"Corners must be 100% transparent! Got alphas: {alphas}"
    print("Transparence des 4 coins validée (alpha = 0).")

    # Cibles d'exportation
    targets = {
        # Mobile Flutter assets
        PROJECT_ROOT / "hiar_mobile" / "assets" / "icon" / "app_icon.png": 1024,
        PROJECT_ROOT / "hiar_mobile" / "assets" / "icon" / "app_icon_512.png": 512,

        # Web Interface assets
        PROJECT_ROOT / "web_interface" / "static" / "img" / "robot_logo.png": 512,
        PROJECT_ROOT / "web_interface" / "static" / "img" / "robot_logo_192.png": 192,
        PROJECT_ROOT / "web_interface" / "static" / "favicon.png": 48,

        # Android Launcher Icons (mipmap)
        PROJECT_ROOT / "hiar_mobile" / "android" / "app" / "src" / "main" / "res" / "mipmap-mdpi" / "ic_launcher.png": 48,
        PROJECT_ROOT / "hiar_mobile" / "android" / "app" / "src" / "main" / "res" / "mipmap-mdpi" / "ic_launcher_round.png": 48,
        PROJECT_ROOT / "hiar_mobile" / "android" / "app" / "src" / "main" / "res" / "mipmap-mdpi" / "ic_launcher_foreground.png": 48,

        PROJECT_ROOT / "hiar_mobile" / "android" / "app" / "src" / "main" / "res" / "mipmap-hdpi" / "ic_launcher.png": 72,
        PROJECT_ROOT / "hiar_mobile" / "android" / "app" / "src" / "main" / "res" / "mipmap-hdpi" / "ic_launcher_round.png": 72,
        PROJECT_ROOT / "hiar_mobile" / "android" / "app" / "src" / "main" / "res" / "mipmap-hdpi" / "ic_launcher_foreground.png": 72,

        PROJECT_ROOT / "hiar_mobile" / "android" / "app" / "src" / "main" / "res" / "mipmap-xhdpi" / "ic_launcher.png": 96,
        PROJECT_ROOT / "hiar_mobile" / "android" / "app" / "src" / "main" / "res" / "mipmap-xhdpi" / "ic_launcher_round.png": 96,
        PROJECT_ROOT / "hiar_mobile" / "android" / "app" / "src" / "main" / "res" / "mipmap-xhdpi" / "ic_launcher_foreground.png": 96,

        PROJECT_ROOT / "hiar_mobile" / "android" / "app" / "src" / "main" / "res" / "mipmap-xxhdpi" / "ic_launcher.png": 144,
        PROJECT_ROOT / "hiar_mobile" / "android" / "app" / "src" / "main" / "res" / "mipmap-xxhdpi" / "ic_launcher_round.png": 144,
        PROJECT_ROOT / "hiar_mobile" / "android" / "app" / "src" / "main" / "res" / "mipmap-xxhdpi" / "ic_launcher_foreground.png": 144,

        PROJECT_ROOT / "hiar_mobile" / "android" / "app" / "src" / "main" / "res" / "mipmap-xxxhdpi" / "ic_launcher.png": 192,
        PROJECT_ROOT / "hiar_mobile" / "android" / "app" / "src" / "main" / "res" / "mipmap-xxxhdpi" / "ic_launcher_round.png": 192,
        PROJECT_ROOT / "hiar_mobile" / "android" / "app" / "src" / "main" / "res" / "mipmap-xxxhdpi" / "ic_launcher_foreground.png": 192,
    }

    for path, size in targets.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        if size == 1024:
            resized = im
        else:
            resized = im.resize((size, size), Image.Resampling.LANCZOS)
        resized.save(path, format="PNG")
        print(f"  [OK] Exporté: {path.relative_to(PROJECT_ROOT)} ({size}x{size})")

    # Nettoyage temporaires
    tmp_html.unlink(missing_ok=True)


if __name__ == "__main__":
    generate_pngs()
