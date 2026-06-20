#!/usr/bin/env python3
"""
schedule_zernio.py — Schedule the repurposed videos to TikTok / YouTube (and
optionally Instagram) through the user's own Zernio account.

Zernio (zernio.com, formerly "Late") is a unified social-media API. The user
connects their accounts once in the Zernio dashboard and pastes their API key
into the skill's .env. This script then:

  1. Uploads each video via a presigned URL (POST /media/presign -> PUT file).
  2. Creates a scheduled post per platform (POST /posts) with the right caption,
     the scheduled time, and the platform-specific fields Zernio requires
     (YouTube title/visibility; TikTok privacy + legal consent flags).

Why one post PER platform instead of one multi-platform post: the videos and
captions differ by platform (TikTok says "link in bio", YouTube "link in
description"), so each platform gets its own media + content.

Auth: reads ZERNIO_API_KEY from the environment or from a .env file next to the
skill. Get the key at Zernio Dashboard -> Settings -> API Keys (format sk_...).

Usage
-----
  # See which accounts are connected and their IDs:
  python schedule_zernio.py --list-accounts

  # Validate the payloads without sending anything (always do this first):
  python schedule_zernio.py --job job.json --dry-run

  # Actually schedule:
  python schedule_zernio.py --job job.json

job.json shape (see assets/job.example.json):
{
  "timezone": "Europe/Istanbul",
  "posts": [
    {"platform": "tiktok",  "file": "output/clip__tiktok.mp4",
     "content": "caption ... link in bio 🔗", "scheduledFor": "2026-06-21T18:00:00"},
    {"platform": "youtube", "file": "output/clip__youtube.mp4",
     "content": "description ... https://link", "scheduledFor": "2026-06-21T18:00:00",
     "title": "Video title <=100 chars", "visibility": "public"}
  ]
}

Per-post optional fields:
  tiktok : privacy_level (default PUBLIC_TO_EVERYONE), allow_comment/duet/stitch
  youtube: title (<=100), visibility (public|unlisted|private)
  accountId: pin a specific Zernio account; otherwise resolved by platform.
"""
import argparse
import json
import mimetypes
import os
import sys
import urllib.error
import urllib.request

BASE = "https://zernio.com/api/v1"


# --- credentials ------------------------------------------------------------
def load_env_key():
    """ZERNIO_API_KEY from the environment, else from a .env file searched
    upward from this script (skill root) and the CWD."""
    key = os.environ.get("ZERNIO_API_KEY")
    if key:
        return key.strip()
    here = os.path.dirname(os.path.abspath(__file__))
    for d in (os.path.dirname(here), here, os.getcwd()):
        envp = os.path.join(d, ".env")
        if os.path.isfile(envp):
            with open(envp) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("ZERNIO_API_KEY"):
                        return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("ZERNIO_API_KEY not found. Add it to .env (see .env.example) or "
             "export it. Get the key at Zernio Dashboard -> Settings -> API Keys.")


def api(method, path, key, body=None, raw=None, content_type=None, full_url=None):
    """Minimal JSON/raw HTTP helper over urllib. Returns parsed JSON (or {})."""
    url = full_url or (BASE + path)
    headers = {"Authorization": f"Bearer {key}"}
    data = None
    if raw is not None:
        data = raw
        headers["Content-Type"] = content_type or "application/octet-stream"
    elif body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            txt = r.read().decode()
            return json.loads(txt) if txt.strip() else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        sys.exit(f"Zernio API {method} {url} failed [{e.code}]: {detail[:800]}")
    except urllib.error.URLError as e:
        sys.exit(f"Network error calling Zernio: {e}")


# --- accounts ---------------------------------------------------------------
def get_accounts(key):
    res = api("GET", "/accounts", key)
    # Tolerate either a bare list or {data:[...]}/{accounts:[...]} envelopes.
    if isinstance(res, dict):
        res = res.get("accounts") or res.get("data") or []
    return res


def account_id_for(accounts, platform):
    pl = platform.lower()
    for a in accounts:
        ap = str(a.get("platform", "")).lower()
        if ap == pl or ap.startswith(pl):
            return a.get("_id") or a.get("id") or a.get("accountId")
    return None


# --- media upload -----------------------------------------------------------
def upload_media(path, key):
    """Presign -> PUT file -> return the permanent publicUrl referenced in posts."""
    if not os.path.isfile(path):
        sys.exit(f"Media file not found: {path}")
    filename = os.path.basename(path)
    ctype = mimetypes.guess_type(filename)[0] or "video/mp4"
    pres = api("POST", "/media/presign", key,
               body={"filename": filename, "contentType": ctype})
    upload_url = pres.get("uploadUrl")
    public_url = pres.get("publicUrl")
    if not upload_url or not public_url:
        sys.exit(f"Unexpected presign response: {json.dumps(pres)[:400]}")
    with open(path, "rb") as f:
        api("PUT", "", key, raw=f.read(), content_type=ctype, full_url=upload_url)
    return public_url


# --- post building ----------------------------------------------------------
def build_post_body(post, public_url, default_tz):
    platform = post["platform"].lower()
    entry = {"platform": platform, "accountId": post["accountId"]}

    if platform == "youtube":
        title = (post.get("title") or post.get("content", "").splitlines()[0] or
                 "Untitled Video")[:100]
        entry["platformSpecificData"] = {
            "title": title,
            "visibility": post.get("visibility", "public"),
        }

    body = {
        "content": post.get("content", ""),
        "scheduledFor": post["scheduledFor"],
        "timezone": post.get("timezone", default_tz),
        "mediaItems": [{"url": public_url, "type": "video"}],
        "platforms": [entry],
    }

    if platform == "tiktok":
        # TikTok settings live at the TOP level (a Zernio special case). The two
        # consent flags are a TikTok legal requirement and must be true.
        body["tiktokSettings"] = {
            "privacy_level": post.get("privacy_level", "PUBLIC_TO_EVERYONE"),
            "allow_comment": post.get("allow_comment", True),
            "allow_duet": post.get("allow_duet", True),
            "allow_stitch": post.get("allow_stitch", True),
            "content_preview_confirmed": True,
            "express_consent_given": True,
        }
    return body


def main():
    ap = argparse.ArgumentParser(description="Schedule repurposed videos via Zernio.")
    ap.add_argument("--job", help="Path to job.json describing the posts.")
    ap.add_argument("--list-accounts", action="store_true",
                    help="Print connected Zernio accounts and their IDs, then exit.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Resolve accounts + build payloads but do not upload or post.")
    args = ap.parse_args()

    # A pure dry run validates job.json offline — no key or network required.
    pure_dry = args.dry_run and not args.list_accounts
    key = None if pure_dry else load_env_key()

    if args.list_accounts:
        accs = get_accounts(key)
        if not accs:
            print("No connected accounts. Connect TikTok + YouTube in the Zernio "
                  "dashboard first (https://zernio.com).")
            return
        print(f"{'PLATFORM':<12} {'ACCOUNT ID':<28} NAME")
        for a in accs:
            print(f"{str(a.get('platform','?')):<12} "
                  f"{str(a.get('_id') or a.get('id') or '?'):<28} "
                  f"{a.get('name') or a.get('username') or ''}")
        return

    if not args.job:
        sys.exit("Provide --job job.json (or use --list-accounts). See --help.")
    with open(args.job) as f:
        job = json.load(f)
    default_tz = job.get("timezone", "UTC")
    posts = job.get("posts", [])
    if not posts:
        sys.exit("job.json has no 'posts'.")

    # Resolve any missing account IDs by platform (skip the lookup on a pure dry
    # run so payloads can be checked with no key / no network).
    accounts = [] if pure_dry else get_accounts(key)
    for p in posts:
        if p.get("accountId"):
            continue
        if pure_dry:
            p["accountId"] = "<resolved-from-/accounts>"
            continue
        aid = account_id_for(accounts, p["platform"])
        if not aid:
            sys.exit(f"No connected Zernio account for platform "
                     f"'{p['platform']}'. Connect it in the dashboard, or set "
                     f"accountId in job.json. Run --list-accounts to inspect.")
        p["accountId"] = aid

    results = []
    for p in posts:
        plat = p["platform"]
        if args.dry_run:
            body = build_post_body(p, public_url="<uploaded-at-runtime>",
                                   default_tz=default_tz)
            print(f"\n--- DRY RUN: {plat} ---")
            print(json.dumps(body, indent=2))
            results.append({"platform": plat, "scheduledFor": p["scheduledFor"],
                            "status": "validated"})
            continue
        print(f"Uploading {plat}: {p['file']} ...")
        public_url = upload_media(p["file"], key)
        body = build_post_body(p, public_url, default_tz)
        res = api("POST", "/posts", key, body=body)
        post_id = res.get("_id") or res.get("id") or res.get("postId") or "?"
        results.append({"platform": plat, "scheduledFor": p["scheduledFor"],
                        "postId": post_id, "status": "scheduled"})

    # Confirmation table.
    print(f"\n{'PLATFORM':<12} {'WHEN':<22} {'STATUS':<12} POST ID")
    for r in results:
        print(f"{r['platform']:<12} {r['scheduledFor']:<22} "
              f"{r['status']:<12} {r.get('postId','-')}")
    if args.dry_run:
        print("\n(Dry run — nothing uploaded or scheduled. Re-run without "
              "--dry-run to publish.)")


if __name__ == "__main__":
    main()
