# Zernio setup (one time)

Zernio is the service that actually schedules your posts to TikTok and YouTube.
You connect your social accounts to it once, grab an API key, and the skill does
the rest. **The first 2 connected accounts are free** — that's exactly TikTok +
YouTube. Instagram auto-posting needs a 3rd connected account (paid), so by
default Instagram stays manual.

## Steps

1. **Create an account** at <https://zernio.com> and log in.

2. **Connect your accounts.** In the dashboard, add:
   - **TikTok** — authorize with the TikTok account you post from.
   - **YouTube** — authorize the channel you post Shorts to.
   - *(Optional, premium)* **Instagram** — only if you want the skill to schedule
     IG too. Otherwise you post the Instagram version by hand.

   > TikTok note: when you authorize, TikTok decides which privacy levels the API
   > may use for your account. If a scheduled post is rejected for privacy, set
   > `TikTok privacy` in `repurpose-config.md` to a value TikTok allows (often
   > `SELF_ONLY` until your app/account is approved for public posting).

3. **Create an API key.** Dashboard → **Settings → API Keys → Create key**. It
   looks like `sk_` followed by 64 characters. Copy it now (you won't see it again).

4. **Paste the key into `.env`.** In the skill folder, open `.env` (setup created
   it from `.env.example`) and set:
   ```
   ZERNIO_API_KEY=sk_xxxxxxxx...
   ```
   `.env` is gitignored — your key never gets committed or shared.

5. **Confirm it works.** From the skill folder:
   ```bash
   python scripts/schedule_zernio.py --list-accounts
   ```
   You should see your TikTok and YouTube accounts with their IDs. The skill saves
   these IDs into `repurpose-config.md` so it doesn't have to look them up again.

That's it. From now on the skill uploads each repurposed video and schedules it
for you. To re-customize anything (post times, privacy, which platforms), just
edit `repurpose-config.md` — never the code.

## How the skill uses Zernio (for reference)
- Base URL: `https://zernio.com/api/v1`, auth header `Authorization: Bearer <key>`.
- `GET /accounts` → your connected accounts + IDs.
- `POST /media/presign` → a one-hour upload URL; the skill `PUT`s the video, gets a
  permanent `publicUrl`.
- `POST /posts` → schedules the post (`content`, `scheduledFor`, `timezone`,
  `mediaItems`, `platforms`; TikTok settings go in a top-level `tiktokSettings`).
