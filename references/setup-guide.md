# Manual setup (fallback)

`scripts/setup.sh` installs everything automatically. Use this page only if it
reported a tool it couldn't install. All of these are free and run locally.

## What's needed
| Tool | Why | Check |
|------|-----|-------|
| ffmpeg + ffprobe | trim / overlay / probe video | `ffmpeg -version` |
| tesseract | OCR to find on-screen CTAs | `tesseract --version` |
| Python 3.9+ | runs the scripts | `python3 --version` |
| faster-whisper | local speech-to-text (no key, no cost) | `python3 -c "import faster_whisper"` |
| Pillow | renders the replacement CTA panel | `python3 -c "import PIL"` |

## macOS (Homebrew)
```bash
brew install ffmpeg tesseract
python3 -m pip install --user faster-whisper Pillow
```
No Homebrew? Install it from <https://brew.sh>, then run the above.

## Debian / Ubuntu
```bash
sudo apt-get update
sudo apt-get install -y ffmpeg tesseract-ocr python3-pip
python3 -m pip install --user faster-whisper Pillow
# If pip refuses on a managed system, add: --break-system-packages
```

## Fedora / RHEL
```bash
sudo dnf install -y ffmpeg tesseract python3-pip
python3 -m pip install --user faster-whisper Pillow
```

## Windows
- Install **ffmpeg**: <https://www.gyan.dev/ffmpeg/builds/> and add its `bin` to PATH.
- Install **Tesseract**: <https://github.com/UB-Mannheim/tesseract/wiki> and add to PATH.
- Then: `python -m pip install faster-whisper Pillow`
- (Or use WSL and follow the Ubuntu steps — usually smoother.)

## Notes
- The **first** Whisper run downloads the model (~150 MB for `base`); it's cached
  afterward, so later runs are fast and fully offline.
- After fixing anything here, re-run `scripts/setup.sh` to confirm all green.
- The font used for the replacement CTA panel (`cover_cta.py`) looks for DejaVu
  Sans. On macOS without it, Pillow falls back to a default font — fine for most
  cases. To match a specific look, install DejaVu fonts or edit `FONT_CANDIDATES`
  at the top of `scripts/cover_cta.py`.
