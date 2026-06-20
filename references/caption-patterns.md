# Caption + CTA patterns (per platform)

One video becomes three posts. The hook and topic stay identical — **only the CTA
mechanic changes**, because each platform delivers a link differently:

| Platform | How the link reaches the viewer | CTA line in the caption |
|----------|---------------------------------|-------------------------|
| Instagram | DM after they comment a keyword | "comment {TRIGGER} and I'll send you the link" |
| TikTok | link in bio | "link in bio 🔗" |
| YouTube | link in description (or pinned comment) | "link in the description 👇" |

Pull the real offer from `report.json` (`cta_text`, `trigger_word`) and from
`repurpose-config.md` (the exact CTA phrasing, the link, the trigger word, the
voice sample). **Never promise a resource the clip didn't actually offer.**

## Instagram (the comment-to-DM original)
The native mechanic. Keep it. The CTA line:
> comment **{TRIGGER}** and I'll send you the link

Example — offer is a rate-limit guide, trigger word `RATE`:
> A bad rate limit cost one company $500M.
> Comment **RATE** and I'll send you the full guide.
> #claudecode #ai #buildinpublic

## TikTok (link in bio)
There's no comment-to-DM on TikTok, so the link sits in the bio.
> [One-line restatement of the value]. Full [resource] — link in my bio 🔗

Example:
> A bad rate limit cost one company $500M. The full guide on avoiding it is in my bio 🔗

## YouTube (title + description)
YouTube needs a **title** (≤100 chars) and a **description**. The link goes in the
description; viewers read "follow" as "subscribe."

- **Title** (≤100): tighten the hook into a headline.
  > The rate-limit mistake that cost $500M
- **Description**: restate the value, then the link.
  > A bad rate limit cost one company $500M. Full guide linked below 👇
  > https://yourlink.com

## Caption structure (all platforms)
1. **Hook** — reuse or tighten the video's opening line.
2. **One or two lines** of payoff/context.
3. **The CTA line** — the only thing that differs by platform (table above).
4. **3–5 specific hashtags** — TikTok and YouTube reward specific over generic
   (`#claudecode` over `#ai`).

## When the CTA was on the video (not just spoken)
If the original ended with an on-screen card ("Comment RATE 👇"), the video itself
is edited per platform (see SKILL.md → `cover_cta.py` / trim), so the on-screen
words match the caption: Instagram keeps "comment {TRIGGER}", TikTok shows "Link in
bio", YouTube shows "Link in description". Keep the caption CTA consistent with
whatever the video now shows.

## When the CTA was ONLY in the description/caption
No video edit at all — just write the three captions above. The same master video
file is scheduled to every platform; only the caption text changes.
