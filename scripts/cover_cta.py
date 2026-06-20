#!/usr/bin/env python3
"""
cover_cta.py — Cover an on-screen text CTA with a matching box and write a new,
platform-appropriate CTA in its place.

Used for the hard case where a "Comment X / full guide" caption is overlaid on
real content (a repo reveal, a talking head) — trimming would destroy the content,
so instead we paint over just the caption and replace the words. The replacement
box is a rounded black panel (built with PIL) to match the original's look, shown
only for the caption's time window.

Usage:
  python cover_cta.py in.mp4 out.mp4 --box X Y W H --window T0 T1 \
      --line1 "Link in bio" --line2 "for the full guide"
"""
import argparse, os, subprocess, sys, tempfile
from PIL import Image, ImageDraw, ImageFont

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]

def font(sz):
    for f in FONT_CANDIDATES:
        if os.path.exists(f):
            return ImageFont.truetype(f, sz)
    return ImageFont.load_default()

def make_panel(w, h, line1, line2, radius=18, pad=6):
    """Render a rounded black panel PNG (transparent outside) with two centered
    white lines, sized to w x h."""
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w-1, h-1], radius=radius, fill=(0, 0, 0, 255))
    # pick a font size that fits both lines vertically
    fs = max(14, int((h - 3*pad) / 2))
    while fs > 10:
        ft = font(fs)
        l1w = d.textlength(line1, font=ft); l2w = d.textlength(line2, font=ft)
        lh = (d.textbbox((0,0), "Ag", font=ft)[3])
        if max(l1w, l2w) <= w - 2*pad and 2*lh + pad <= h - 2*pad:
            break
        fs -= 1
    ft = font(fs)
    l1w = d.textlength(line1, font=ft); l2w = d.textlength(line2, font=ft)
    lh = d.textbbox((0,0),"Ag",font=ft)[3]
    total = 2*lh + pad
    y = (h - total)//2
    d.text(((w-l1w)//2, y), line1, font=ft, fill=(255,255,255,255))
    d.text(((w-l2w)//2, y+lh+pad), line2, font=ft, fill=(255,255,255,255))
    return img

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input"); ap.add_argument("output")
    ap.add_argument("--box", nargs=4, type=int, required=True, metavar=("X","Y","W","H"))
    ap.add_argument("--window", nargs=2, type=float, required=True, metavar=("T0","T1"))
    ap.add_argument("--line1", required=True)
    ap.add_argument("--line2", default="")
    ap.add_argument("--radius", type=int, default=18)
    args = ap.parse_args()

    x, y, w, h = args.box
    t0, t1 = args.window
    with tempfile.TemporaryDirectory() as tmp:
        panel = make_panel(w, h, args.line1, args.line2, radius=args.radius)
        ppath = os.path.join(tmp, "panel.png")
        panel.save(ppath)
        # Overlay panel at (x,y) only during [t0,t1].
        fc = f"[0:v][1:v]overlay={x}:{y}:enable='between(t,{t0},{t1})'[v]"
        cmd = ["ffmpeg", "-y", "-i", args.input, "-i", ppath,
               "-filter_complex", fc, "-map", "[v]", "-map", "0:a?",
               "-c:v", "libx264", "-crf", "20", "-preset", "veryfast",
               "-pix_fmt", "yuv420p", "-movflags", "+faststart",
               "-c:a", "copy", args.output]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit(f"ffmpeg failed:\n{r.stderr[-1500:]}")
    print(f"Wrote {args.output}")

if __name__ == "__main__":
    main()
