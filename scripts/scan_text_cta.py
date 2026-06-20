#!/usr/bin/env python3
"""
scan_text_cta.py — Find an on-screen TEXT call-to-action near the end of a video.

Audio transcription misses CTAs that are shown as text with no voiceover — an end
card like "Comment NANO 👇 to get the full guide" or "Link in bio". This OCRs the
final seconds frame by frame, finds where a CTA card first appears, and snaps the
cut to the hard scene change just before it so the trim is clean.

Returns JSON: {"found": bool, "card_start": float|null, "cut": float|null,
"matched": str, "trigger": str|null, "type": str}

Standalone usage:
    python scan_text_cta.py video.mp4 [--lookback 10] [--step 0.4]

Needs ffmpeg/ffprobe and tesseract on PATH.
"""
import argparse, json, os, re, subprocess, sys, tempfile

# Reuse the same CTA vocabulary the audio detector uses, adapted for OCR text.
CTA_KEYWORDS = re.compile(
    r"\bcomment\b|\blink in (my )?bio\b|\blink in (the )?desc|\bfollow me\b|"
    r"\bdm me\b|\bsend you\b|\bfull guide\b|\bswipe up\b|\bget the (full )?guide\b",
    re.IGNORECASE)
TRIGGER_AFTER_COMMENT = re.compile(r"\bcomment\s+\"?([A-Za-z0-9\-]{2,20})", re.IGNORECASE)


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def probe_duration(path):
    r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path])
    return float(r.stdout.strip())


def ocr_frame(path, t, tmp):
    img = os.path.join(tmp, "f.png")
    run(["ffmpeg", "-y", "-ss", f"{t:.2f}", "-i", path, "-frames:v", "1",
         "-vf", "scale=640:-1", img])
    if not os.path.exists(img):
        return ""
    r = run(["tesseract", img, "-", "--psm", "11"])  # psm 11: sparse text
    return r.stdout


def scene_cuts_in_window(path, start, end, thresh=0.25):
    """Hard scene-change timestamps within [start,end] (CTA cards usually begin on
    one). Used to snap the cut so we don't slice mid-shot."""
    r = run(["ffmpeg", "-ss", f"{start:.2f}", "-to", f"{end:.2f}", "-i", path,
             "-vf", f"select='gt(scene,{thresh})',showinfo", "-f", "null", "-"])
    times = [start + float(x) for x in re.findall(r"pts_time:([0-9.]+)", r.stderr)]
    return times


def find_text_cta(path, lookback=10.0, step=0.4):
    total = probe_duration(path)
    begin = max(0.0, total - lookback)
    with tempfile.TemporaryDirectory() as tmp:
        t = begin
        card_start = None
        matched = ""
        while t < total:
            text = ocr_frame(path, t, tmp)
            if CTA_KEYWORDS.search(text):
                card_start = t
                matched = " ".join(text.split())
                break
            t += step
        if card_start is None:
            return {"found": False, "card_start": None, "cut": None,
                    "matched": "", "trigger": None, "type": None}
        # Snap to the scene cut just before the first CTA frame (within step+0.3s),
        # so we cut exactly at the card boundary, not mid-shot.
        cuts = scene_cuts_in_window(path, max(0, card_start - step - 0.5),
                                    card_start + 0.2)
        cut = max([c for c in cuts if c <= card_start + 0.05], default=card_start)
        tm = TRIGGER_AFTER_COMMENT.search(matched)
        trig = tm.group(1) if tm else None
        ctype = "comment_dm" if re.search(r"comment|send you|full guide|dm me",
                                          matched, re.IGNORECASE) else "link_bio" \
            if re.search(r"link in", matched, re.IGNORECASE) else "follow"
        return {"found": True, "card_start": round(card_start, 2),
                "cut": round(cut, 2), "matched": matched[:160],
                "trigger": trig, "type": ctype}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--lookback", type=float, default=10.0)
    ap.add_argument("--step", type=float, default=0.4)
    args = ap.parse_args()
    print(json.dumps(find_text_cta(args.input, args.lookback, args.step), indent=2))


if __name__ == "__main__":
    main()
