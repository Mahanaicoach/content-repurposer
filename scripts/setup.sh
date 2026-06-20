#!/usr/bin/env bash
# setup.sh — one-time install of the local, free tools this skill needs:
#   ffmpeg + ffprobe  (video trim / overlay / probe)
#   tesseract         (OCR for on-screen CTA detection)
#   faster-whisper    (local speech-to-text, no API key, no per-use cost)
#   Pillow            (renders the replacement CTA panel)
#
# Everything here runs locally and is free. Nothing leaves the machine until you
# choose to schedule a post via Zernio (that's the only paid/external piece, and
# its first 2 connected accounts are free).
#
# Safe to re-run: it skips anything already installed.
set -u
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fail=0

say()  { printf "\n\033[1m%s\033[0m\n" "$1"; }
ok()   { printf "  ✓ %s\n" "$1"; }
warn() { printf "  ! %s\n" "$1"; }

# --- pick a system package manager ------------------------------------------
OS="$(uname -s)"
if   command -v brew >/dev/null 2>&1; then PM="brew"
elif command -v apt-get >/dev/null 2>&1; then PM="apt"
elif command -v dnf >/dev/null 2>&1; then PM="dnf"
else PM=""; fi

sys_install() { # $1 = package name
  case "$PM" in
    brew) brew install "$1" ;;
    apt)  sudo apt-get update -y && sudo apt-get install -y "$1" ;;
    dnf)  sudo dnf install -y "$1" ;;
    *)    return 1 ;;
  esac
}

say "1/3  System tools (ffmpeg, tesseract)"
if command -v ffmpeg >/dev/null 2>&1; then ok "ffmpeg present";
else
  warn "installing ffmpeg via ${PM:-?}"; sys_install ffmpeg || { warn "could not auto-install ffmpeg"; fail=1; }
fi
if command -v tesseract >/dev/null 2>&1; then ok "tesseract present";
else
  # Debian/Ubuntu package is tesseract-ocr; brew/dnf use tesseract.
  pkg="tesseract"; [ "$PM" = "apt" ] && pkg="tesseract-ocr"
  warn "installing $pkg via ${PM:-?}"; sys_install "$pkg" || { warn "could not auto-install tesseract"; fail=1; }
fi

say "2/3  Python packages (faster-whisper, Pillow)"
PY="$(command -v python3 || command -v python)"
if [ -z "$PY" ]; then warn "python3 not found — install Python 3.9+"; fail=1;
else
  "$PY" - <<'PYCHK' 2>/dev/null && ok "faster-whisper present" || {
import importlib.util, sys
sys.exit(0 if importlib.util.find_spec("faster_whisper") else 1)
PYCHK
    warn "installing faster-whisper + Pillow"
    "$PY" -m pip install --user faster-whisper Pillow 2>/dev/null \
      || "$PY" -m pip install --break-system-packages faster-whisper Pillow \
      || { warn "pip install failed — see references/setup-guide.md"; fail=1; }
  }
fi

say "3/3  Credentials file"
if [ -f "$SKILL_DIR/.env" ]; then ok ".env already exists";
else
  cp "$SKILL_DIR/.env.example" "$SKILL_DIR/.env" 2>/dev/null \
    && ok "created .env from template — paste your Zernio key into it" \
    || warn "could not create .env (copy .env.example -> .env manually)"
fi

# --- verify ------------------------------------------------------------------
say "Verifying"
command -v ffmpeg    >/dev/null 2>&1 && ok "ffmpeg"    || { warn "ffmpeg MISSING";    fail=1; }
command -v ffprobe   >/dev/null 2>&1 && ok "ffprobe"   || { warn "ffprobe MISSING";   fail=1; }
command -v tesseract >/dev/null 2>&1 && ok "tesseract" || { warn "tesseract MISSING"; fail=1; }
[ -n "${PY:-}" ] && "$PY" -c "import faster_whisper, PIL" 2>/dev/null \
  && ok "faster-whisper + Pillow" || { warn "python deps MISSING"; fail=1; }

if [ "$fail" -ne 0 ]; then
  printf "\n\033[1mSome tools could not be auto-installed.\033[0m Follow the manual\n"
  printf "steps for your OS in references/setup-guide.md, then re-run this script.\n"
  exit 1
fi
printf "\n\033[1mSetup complete.\033[0m Next: connect TikTok + YouTube in Zernio and\n"
printf "paste your API key into .env  (see references/zernio-setup.md).\n"
