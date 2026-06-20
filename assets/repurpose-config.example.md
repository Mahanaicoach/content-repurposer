# Repurpose Config

This is your personal, plain-English settings file. The skill reads it on every
run, so editing it here changes how every future video is repurposed and
scheduled — no code edits, ever. Copy this to `repurpose-config.md` at the skill
root and fill it in (the setup phase does this for you and interviews you for the
values).

## Identity
- Handle: @yourhandle
- Default trigger word: GUIDE        # the word people comment on Instagram

## Where the link lives (used to translate the CTA)
- Bio link (Instagram + TikTok): https://yourlink.com
- YouTube description link: https://yourlink.com

## CTA phrasing per platform
- Instagram CTA: "comment {TRIGGER} and I'll send you the link"
- TikTok CTA: "link in bio 🔗"
- YouTube CTA: "link in the description 👇"

## Scheduling (Zernio)
- Timezone: Europe/Istanbul          # IANA tz name
- Default post time: 18:00           # used when you don't give a date/time per run
- TikTok account ID: <filled in during setup from GET /accounts>
- YouTube account ID: <filled in during setup from GET /accounts>
- Instagram account ID:              # leave blank unless you connected IG (premium)

## Platform options
- TikTok privacy: PUBLIC_TO_EVERYONE   # or MUTUAL_FOLLOW_FRIENDS / FOLLOWER_OF_CREATOR / SELF_ONLY
- TikTok allow comment / duet / stitch: yes / yes / yes
- YouTube visibility: public           # public / unlisted / private
- Publish Instagram automatically: no  # "yes" only if Instagram is connected in Zernio (premium)

## Voice (for captions)
- Caption voice sample: "someone finally did it. a free tool that does X. it's free."
- Language: English
- Hashtag style: specific over generic (e.g. #claudecode over #ai)
