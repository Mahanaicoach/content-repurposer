---
name: content-repurposer
description: >-
  Turn one short-form video (an Instagram Reel or a TikTok) into platform-correct
  versions for Instagram, TikTok, and YouTube — then auto-schedule TikTok and
  YouTube through the user's own Zernio account. It transcribes the video and OCRs
  the frames to find the call-to-action, then TRANSLATES that CTA per platform:
  Instagram keeps "comment <word> and I'll send you the link" (the DM mechanic),
  while TikTok becomes "link in bio" and YouTube becomes "link in description" — in
  the on-screen text, the voiceover, AND the caption. If the CTA only lives in the
  description, it rewrites the description per platform instead. Use this whenever
  the user wants to repurpose, cross-post, or adapt a reel/TikTok for other
  platforms; fix or translate a CTA, outro, or ending across platforms; write
  per-platform captions; or schedule the same video to TikTok/YouTube. Trigger even
  if they don't say "CTA" — "post my reel everywhere", "make TikTok + YouTube
  versions and schedule them", or "repurpose this short" should all use this skill.
  On first use it runs a one-time SETUP that installs the (free) transcription
  tools and walks the user through connecting Zernio. The original file is never
  modified.
---

# Content Repurposer

One video, edited once, becomes three platform-correct posts — and TikTok +
YouTube get **scheduled automatically**. The thing that breaks when you cross-post
is the **call-to-action**: "comment WORD and I'll send the link" is right on
Instagram (DMs are the mechanic) but means nothing on TikTok or YouTube, where the
link lives in the bio / description. This skill detects the CTA and **translates**
it per platform — on the video and in the caption — then schedules the result.

The source file is **read-only**. Every output is a new file in a separate folder.

---

## Phase 0 — Setup (first run only)

Before anything else, check whether setup has been done. Look for **both**
`repurpose-config.md` and `.env` at the skill root.

- If either is missing → run setup now (below).
- If both exist → skip straight to Phase 1.

**Setup steps:**

1. **Install the tools.** Run:
   ```bash
   bash scripts/setup.sh
   ```
   This installs `ffmpeg`, `tesseract`, `faster-whisper`, and `Pillow` (all free,
   all local — `faster-whisper` is the no-key, no-cost transcription engine) and
   creates `.env` from the template. If it reports a failure, walk the user through
   `references/setup-guide.md` for their OS, then re-run it.

2. **Connect Zernio.** Read `references/zernio-setup.md` to the user and have them:
   create a Zernio account → connect **TikTok + YouTube** (first 2 accounts free) →
   copy their API key (`sk_…`) from Settings → API Keys → paste it into `.env` as
   `ZERNIO_API_KEY=…`. Confirm with:
   ```bash
   python scripts/schedule_zernio.py --list-accounts
   ```

3. **Write their config.** Interview the user for the values in
   `assets/repurpose-config.example.md` (handle, the link, default trigger word,
   timezone + default post time, TikTok privacy, YouTube visibility, whether
   Instagram is connected). Copy the example to `repurpose-config.md` at the skill
   root and fill it in. Paste the TikTok/YouTube account IDs from the
   `--list-accounts` output so later runs skip the lookup. Show a short summary to
   confirm.

Re-customizing later = editing `repurpose-config.md` or `.env`. Never edit code.

---

## Phase 1 — Analyze the video

Run **both** passes on the source (audio CTAs and on-screen-text CTAs are
different problems — always do both):

```bash
# Spoken CTA: transcript + classification + trigger word, into a report
python scripts/repurpose.py "PATH/TO/video.mp4" --out-dir output --dry-run

# On-screen text CTA: OCR the final seconds
python scripts/scan_text_cta.py "PATH/TO/video.mp4"
```

From the two reports, decide **where the CTA lives** — this drives everything:

- **Spoken** (in the voiceover) → `repurpose.py` found it (`cta_type`, `trigger_word`).
- **On-screen text** (a card / overlay) → `scan_text_cta.py` found it (`card_start`,
  `type`, `trigger`).
- **Description/caption only** (nothing on the video) → both report nothing; the
  video is reused as-is and only the captions change.

Also note the **source platform** (ask if unclear). The usual case is an
Instagram-style master (ends with "comment WORD"). If the source is already a
TikTok-style "link in bio" video, the translation runs the other direction (see the
table below) — the mechanics are symmetric.

---

## Phase 2 — Translate the CTA per platform (core logic)

The link delivery differs per platform, so the CTA must change to match:

| Platform | CTA the video/caption should end on |
|----------|--------------------------------------|
| **Instagram** | "comment {TRIGGER} and I'll send you the link" (the DM mechanic) |
| **TikTok** | "Link in bio" |
| **YouTube** | "Link in description" |

How you produce each platform's **video** depends on where the CTA lived:

### A. Spoken CTA
Use `repurpose.py`'s trim. Instagram **keeps** the spoken comment-CTA; TikTok and
YouTube get the tail trimmed (the CTA then lives only in their captions). The
defaults already do this:
```bash
python scripts/repurpose.py "PATH/TO/video.mp4" --out-dir output
# -> video__tiktok.mp4, video__youtube_shorts.mp4 (CTA trimmed), + report.json
# Instagram version = the original master (CTA kept).
```
Confirm the cut in `report.json` (`cut_if_removed` lands after the last real
sentence) before trusting the encode.

### B. On-screen text CTA
First look at the actual frame (`ffmpeg -ss <card_start> -i video.mp4 -frames:v 1
frame.png`) and get the caption's pixel box via Tesseract TSV (see the recipe in
the original engine docs / `scan_text_cta.py`). Then:

- **Standalone trailing card** (CTA is the whole screen) → treat like a spoken CTA:
  trim for TikTok/YouTube with `--cta-at <card_start>`; keep it for Instagram.
- **Caption overlaid on real content** (the video keeps playing under the card) →
  do **not** trim. Cover and replace the words per platform with `cover_cta.py`,
  one render per platform because the text differs:
  ```bash
  # TikTok
  python scripts/cover_cta.py video.mp4 output/video__tiktok.mp4 \
    --box X Y W H --window T0 T1 --line1 "Link in bio" --line2 "for the full guide"
  # YouTube
  python scripts/cover_cta.py video.mp4 output/video__youtube.mp4 \
    --box X Y W H --window T0 T1 --line1 "Link in description" --line2 "for the full guide"
  # Instagram keeps the original "comment {TRIGGER}" card (use the master as-is),
  # OR re-render it to the exact config phrasing if needed.
  ```
  Always extract a frame from each output and view it to confirm the old text is
  fully covered.

### C. Description/caption-only CTA
No video edit. The same master video file is scheduled to all platforms; only the
caption text changes (Phase 3).

Name outputs `*__instagram.mp4`, `*__tiktok.mp4`, `*__youtube.mp4`. If a platform
needs no edit (e.g. Instagram in cases A/C), reuse the original master for it.

---

## Phase 3 — Write the captions + descriptions

Using `references/caption-patterns.md`, `report.json` (real offer + trigger word),
and the voice sample in `repurpose-config.md`, write one caption per platform with
the right CTA baked in:

- **Instagram** — "comment {TRIGGER} and I'll send you the link".
- **TikTok** — "link in bio 🔗".
- **YouTube** — a **title** (≤100 chars) **and** a description with the link.

Keep the hook and topic identical across all three; only the CTA line changes. Save
them to `output/<name>__captions.md` so they're easy to copy.

---

## Phase 4 — Schedule TikTok + YouTube (Zernio)

Build a `job.json` (see `assets/job.example.json`) listing the TikTok and YouTube
posts — each with its `file`, `content` (caption/description), `scheduledFor`
(ISO 8601, derived from the user's requested date or the config's default time),
plus the YouTube `title`/`visibility` and TikTok privacy from `repurpose-config.md`.
Pull `timezone` from the config.

Validate first, then schedule:
```bash
python scripts/schedule_zernio.py --job job.json --dry-run   # check payloads
python scripts/schedule_zernio.py --job job.json             # upload + schedule
```
The script uploads each video (presigned URL), creates one scheduled post per
platform, and prints a table (platform · when · status · post id).

**Instagram** is **manual by default**: print the Instagram caption + the video
path and tell the user to post it themselves. Only schedule Instagram if the config
says it's connected (Zernio premium) — then add an `instagram` post to `job.json`.

---

## Reporting back

Give the user, per platform: where the CTA ended up (comment / bio / description),
the output path, and the scheduled time + Zernio post id (or "manual" for
Instagram). Then paste the three captions. Keep prose short — they can watch the
files themselves.

## Notes and limits
- CTA detection is keyword-based (transcript + OCR), tuned for "comment X", "link
  in bio", "follow me" endings. Novel phrasing may need `repurpose.py --cta-at`.
  Patterns live at the top of `repurpose.py` / `scan_text_cta.py`.
- Run **both** detection passes — audio detection misses silent on-screen text CTAs.
- `cover_cta.py` cleanly replaces a solid caption box; it's not built for text baked
  into busy footage (moving text, text over a face) — surface a frame and ask.
- Zernio's first 2 connected accounts are free (TikTok + YouTube). Instagram
  auto-scheduling needs a 3rd (paid) account; otherwise it stays manual.
- TikTok may restrict which `privacy_level` the API can use until the account is
  approved for public posting — if a post is rejected, lower it in the config.
