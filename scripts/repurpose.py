#!/usr/bin/env python3
"""
repurpose.py — Repurpose a finished Instagram reel for TikTok & YouTube Shorts by
removing the Instagram-specific end CTA.

The problem this solves: a reel is edited once for Instagram and ends with a
platform-specific call to action — usually "Comment <word> and I'll send you..."
(comment-to-DM), or "Follow me", "Link in bio", etc. Those mechanics don't exist
on TikTok or YouTube Shorts, so the CTA has to come off the video and move into
the post caption instead.

What it does:
  1. Transcribes the audio with word-level timestamps (faster-whisper).
  2. Finds where the end CTA begins by matching CTA phrasing in the trailing
     speech, then snaps the cut to the nearest silence so it doesn't clip a word.
  3. Trims the video to end just before the CTA.
  4. Exports a clean master and per-platform copies (TikTok, YouTube Shorts) at the
     source's native 9:16 spec.
  5. Writes report.json with the detected CTA, trigger word, offered resource, and
     cut time — so the caption can reference the same offer.

The format is left untouched (already 9:16) — this is CTA surgery, not reframing.

Usage
-----
python repurpose.py "edited_reel.mp4" --out-dir output
python repurpose.py reel.mp4 --cta-at 19.4          # skip detection, cut manually
python repurpose.py reel.mp4 --platforms tiktok      # one platform only
python repurpose.py reel.mp4 --dry-run               # detect + report, no export
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys

# --- CTA detection & classification -----------------------------------------
# CTAs are grouped by TYPE, because the right action differs by type and platform.
# A reel's ending usually contains exactly one of these.
#
#   comment_dm — "Comment RATE and I'll send you the guide." Instagram comment-to-
#                DM. The mechanic doesn't exist on TikTok or YouTube, so it must
#                come off the video everywhere. THIS IS THE PRIORITY CASE.
#   follow     — "Follow me for more." Native on TikTok and perfectly readable on
#                YouTube too (viewers treat follow == subscribe). Kept everywhere.
#   link_bio   — "Link in my bio." Bio-link phrasing fits TikTok/IG, not YouTube
#                (where it's the description). Keep TikTok, remove Shorts.
#   engagement — "Save this", "Smash like", "Share this". Generic; harmless
#                anywhere. Kept by default.
CTA_TYPES = {
    "comment_dm": [r"\bcomment\b", r"\bdm me\b",
                   r"\bi('?ll| will) send you\b", r"\bsend you (the|a|my)\b"],
    "follow":     [r"\bfollow me\b", r"\bfollow for\b", r"\bfollow along\b"],
    "link_bio":   [r"\blink in (my )?(bio|profile)\b"],
    "engagement": [r"\bsubscribe\b", r"\bsmash (that|the) like\b",
                   r"\bdouble tap\b", r"\bsave (this|it) for later\b",
                   r"\bshare this (video|reel|with)\b",
                   r"\blike and (subscribe|follow)\b"],
}
TYPE_RES = {t: re.compile("|".join(p), re.IGNORECASE) for t, p in CTA_TYPES.items()}
# Any-CTA matcher (used to find the boundary of the trailing CTA block).
CTA_RE = re.compile("|".join(p for ps in CTA_TYPES.values() for p in ps), re.IGNORECASE)

# Default policy: for each CTA type, what to do per platform. "remove" trims it
# off; "keep" leaves it on. Override at the CLI with --policy (see --help).
DEFAULT_POLICY = {
    "comment_dm": {"tiktok": "remove", "shorts": "remove"},
    "follow":     {"tiktok": "keep",   "shorts": "keep"},
    "link_bio":   {"tiktok": "keep",   "shorts": "remove"},
    "engagement": {"tiktok": "keep",   "shorts": "keep"},
    "unknown":    {"tiktok": "remove", "shorts": "remove"},
}

# Token right after "comment", i.e. the DM trigger word — "Comment RATE" -> rate.
TRIGGER_RE = re.compile(r"\bcomment\s+([A-Za-z0-9\-]{2,20})", re.IGNORECASE)


def classify_cta(text):
    """Pick the CTA type. comment_dm wins ties because it's the one that MUST be
    removed — better to over-remove an IG mechanic than leave it on the wrong
    platform."""
    for t in ("comment_dm", "follow", "link_bio", "engagement"):
        if TYPE_RES[t].search(text):
            return t
    return "unknown"


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def probe_duration(path):
    r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path])
    if r.returncode != 0:
        sys.exit(f"ffprobe failed: {r.stderr}")
    return float(r.stdout.strip())


def transcribe(path, model_size):
    """Return list of segments [{start,end,text}] with word timestamps."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        sys.exit("faster-whisper not installed. Run: pip install faster-whisper")
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, info = model.transcribe(path, word_timestamps=True)
    segs = [{"start": s.start, "end": s.end, "text": s.text.strip()} for s in segments]
    return segs, float(info.duration)


def detect_cta(segs, total):
    """Find the cut point: the start of the trailing CTA block.

    Scan from the end. Collect contiguous trailing segments that look like CTA.
    The CTA often spans two segments (e.g. "do not follow me" / "because I'll be
    giving you tools"), where only the first carries an obvious keyword — so once
    a CTA segment is found, the segments AFTER it (toward the end) are absorbed
    too, since nothing legitimate follows a CTA. Stop when we hit real content
    before the CTA. Returns (cut_time, matched_text, trigger, prev_content_end).
    If nothing matches, returns (None, "", None, None) and the clip is kept whole.
    """
    cta_start_idx = None
    # Find the earliest index from the end that begins the contiguous CTA tail.
    for i in range(len(segs) - 1, -1, -1):
        if CTA_RE.search(segs[i]["text"]):
            cta_start_idx = i
        elif cta_start_idx is not None:
            # Hit content that sits before an already-found CTA: stop.
            break
    if cta_start_idx is None:
        return None
    cut = segs[cta_start_idx]["start"]
    matched = " ".join(s["text"] for s in segs[cta_start_idx:]).strip()
    tm = TRIGGER_RE.search(matched)
    trigger = tm.group(1) if tm else None
    prev_end = segs[cta_start_idx - 1]["end"] if cta_start_idx > 0 else 0.0
    return {"cut": cut, "text": matched, "trigger": trigger,
            "prev_end": prev_end, "type": classify_cta(matched)}


def nearest_silence_before(path, t, lower_bound=0.0, window=1.2,
                           noise="-30dB", min_d=0.15):
    """Snap the cut to a silence just before the CTA so it lands in a gap, not
    mid-word — but never earlier than `lower_bound` (the end of the preceding
    content). Without that clamp, an earlier pause inside the content could pull
    the cut back and clip a real sentence. Returns the refined cut, or t.
    """
    r = run(["ffmpeg", "-i", path, "-af",
             f"silencedetect=noise={noise}:d={min_d}", "-f", "null", "-"])
    log = r.stderr
    starts = [float(x) for x in re.findall(r"silence_start: ([0-9.]+)", log)]
    floor = max(lower_bound, t - window)
    candidates = [s for s in starts if floor <= s <= t + 0.25]
    if candidates:
        return max(candidates)
    # No usable silence: cut exactly at the CTA onset (safe — never before content).
    return t


def export(src, dst, cut, fade=0.3, preset="veryfast"):
    """Write dst as src trimmed to [0, cut].

    When the cut keeps essentially the whole clip (a "keep" decision), there's
    nothing to trim — so stream-copy the source instead of re-encoding. That's
    near-instant and lossless. Only when we actually remove a CTA tail do we
    re-encode, applying a short audio fade so the new ending isn't abrupt.
    """
    total = probe_duration(src)
    if cut >= total - 0.10:
        # No meaningful trim: passthrough copy, no quality loss, fast.
        r = run(["ffmpeg", "-y", "-i", src, "-c", "copy",
                 "-movflags", "+faststart", dst])
        if r.returncode == 0:
            return
        # Fall through to re-encode if copy fails (rare container quirks).

    af = f"afade=t=out:st={max(0, cut-fade):.3f}:d={fade}"
    cmd = ["ffmpeg", "-y", "-i", src, "-t", f"{cut:.3f}",
           "-vf", "format=yuv420p", "-af", af,
           "-c:v", "libx264", "-profile:v", "high", "-crf", "20",
           "-preset", preset, "-movflags", "+faststart",
           "-c:a", "aac", "-b:a", "160k", dst]
    r = run(cmd)
    if r.returncode != 0:
        # retry without audio filter (clip may have no audio)
        cmd = ["ffmpeg", "-y", "-i", src, "-t", f"{cut:.3f}",
               "-vf", "format=yuv420p", "-c:v", "libx264", "-crf", "20",
               "-preset", preset, "-movflags", "+faststart", "-an", dst]
        r = run(cmd)
        if r.returncode != 0:
            sys.exit(f"ffmpeg export failed for {dst}:\n{r.stderr[-1500:]}")


PLATFORM_NAMES = {"tiktok": "tiktok", "shorts": "youtube_shorts",
                  "youtube_shorts": "youtube_shorts"}


def main():
    ap = argparse.ArgumentParser(
        description="Repurpose an edited IG reel for TikTok/Shorts by handling the end CTA per platform.")
    ap.add_argument("input")
    ap.add_argument("--platforms", default="tiktok,shorts",
                    help="Comma list: tiktok, shorts. Both export at the source's 9:16 spec.")
    ap.add_argument("--out-dir", default="output")
    ap.add_argument("--model", default="base",
                    help="Whisper size: tiny/base/small/medium. base is a good balance.")
    ap.add_argument("--cta-at", type=float, default=None,
                    help="Manual CTA start time (s). Skips detection; applies the "
                         "type given by --cta-type (default comment_dm).")
    ap.add_argument("--cta-type", default="comment_dm",
                    choices=list(DEFAULT_POLICY),
                    help="CTA type to assume when --cta-at is used.")
    ap.add_argument("--policy", default=None,
                    help="JSON overriding the per-type/per-platform policy, e.g. "
                         "'{\"follow\":{\"tiktok\":\"remove\"}}'. Merges over defaults.")
    ap.add_argument("--no-silence-snap", action="store_true",
                    help="Cut exactly at the detected CTA onset, don't snap to silence.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Detect + report only, no video export.")
    args = ap.parse_args()

    if not os.path.isfile(args.input):
        sys.exit(f"Not found: {args.input}")

    # --- SAFETY: never touch the original ----------------------------------
    # The script only ever reads `input` and writes into `out-dir`. Guard against
    # an out-dir that would let an output collide with the source file.
    in_abs = os.path.abspath(args.input)
    out_abs = os.path.abspath(args.out_dir)
    if out_abs == os.path.dirname(in_abs):
        sys.exit("Refusing to write into the source folder. Pick a separate "
                 "--out-dir so the original file is never at risk.")
    os.makedirs(args.out_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(args.input))[0]

    # Resolve policy (defaults + optional override).
    policy = {t: dict(p) for t, p in DEFAULT_POLICY.items()}
    if args.policy:
        for t, pp in json.loads(args.policy).items():
            policy.setdefault(t, {}).update(pp)

    total = probe_duration(args.input)
    report = {"input": args.input, "duration": round(total, 2),
              "original_untouched": True}

    # --- find the CTA (once) -----------------------------------------------
    if args.cta_at is not None:
        cta = {"cut": args.cta_at, "text": "(manual)", "trigger": None,
               "prev_end": 0.0, "type": args.cta_type}
        report["cta_source"] = "manual"
    else:
        segs, _ = transcribe(args.input, args.model)
        report["transcript_tail"] = segs[-6:]
        report["transcript_full"] = " ".join(s["text"] for s in segs).strip()
        cta = detect_cta(segs, total)
        report["cta_source"] = "auto"

    if cta is None:
        report.update(cta_detected=False,
                      note="No CTA phrasing found in trailing speech. Exporting "
                           "the clip whole for every platform. Use --cta-at to trim manually.")
    else:
        # Snap the removal cut to silence (clamped so it never enters content).
        raw = cta["cut"]
        cut = raw if args.no_silence_snap else nearest_silence_before(
            args.input, raw, lower_bound=cta["prev_end"])
        cta["cut_snapped"] = round(cut, 2)
        report.update(cta_detected=True, cta_type=cta["type"],
                      cta_text=cta["text"], trigger_word=cta["trigger"],
                      cta_start_speech=round(raw, 2), cut_if_removed=round(cut, 2))

    # --- per-platform decision + export ------------------------------------
    plats = [p.strip().lower() for p in args.platforms.split(",") if p.strip()]
    decisions = {}
    outputs = []
    for p in plats:
        tag = PLATFORM_NAMES.get(p, p)
        if cta is None:
            action, cut = "keep", total
        else:
            action = policy.get(cta["type"], {}).get(p, "keep")
            cut = cta["cut_snapped"] if action == "remove" else total
        decisions[p] = {"action": action, "cut_time": round(cut, 2),
                        "removed_seconds": round(total - cut, 2)}
        if not args.dry_run:
            dst = os.path.join(args.out_dir, f"{base}__{tag}.mp4")
            export(args.input, dst, cut)
            outputs.append(dst)

    report["decisions"] = decisions
    report["outputs"] = outputs

    with open(os.path.join(args.out_dir, f"{base}__report.json"), "w") as f:
        json.dump(report, f, indent=2)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
