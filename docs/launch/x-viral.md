# X launch copy

## FINAL PICK (validated 2026-09-20: numbers vs BENCHMARK.md, no em dashes/arrows/hedges, char limits)

### Reply under Rafal (post first) = C-B, 234 chars

Built the open-source version: jevqa. No tests to write: URL + README, 5–6 minutes, $0.29–0.41/app. Across 20 apps it found 22% of 107 bugs. About 1 in 8 reports is real; weak on numbers and permissions. https://github.com/Todmy/jevqa

### Standalone post (30 min later) = A-B, 263 chars

Opus 5 found 17% of known bugs for $3.20/app. Tuned jevqa found 24% for $0.37 on the same 10 development apps.

Across all 20 apps, jevqa found 22%. About 1 in 8 reports is real. Weak on numbers and permissions.

No tests to write.

https://github.com/Todmy/jevqa

### Thread = A post 1 (trimmed) + B posts 2-5

1. Jev made browser testing cheap enough to run before QA.

I open-sourced a monkey tester that does it: 22% of 107 known bugs across 20 apps, $0.29–0.41 per app. About 1 in 8 reports is real.

2. This is for the app you made with Lovable, Bolt, Replit, or Claude Code and want to check before anyone sees it.

One command. A URL and the README you already have. No tests to write. The run takes 5–6 minutes; the report takes ninety seconds to skim.

3. The useful trick is absence.

If the spec says users can edit a post but no Edit control exists on any screen, jevqa reports it. Every tester can click a broken button. This one notices the button never shipped.

4. Same 10 development apps: tuned jevqa found 24% at $0.37/app. Opus 5 found 17% at $3.20; Sonnet 5 found 10% at $1.16. Caveat: jevqa was tuned there, they were not. On the untouched holdout it found 18–20%.

5. Local CLI or GitHub Action. No test suite required.

Code and the reproducible benchmark:

https://github.com/Todmy/jevqa

---

# Codex variants (source)

## A. Standalone post

### Variant A

Jev made browser testing cheap enough to run before QA.

On the same 10 development apps, tuned jevqa found 24% at $0.37/app. Opus 5 found 17% at $3.20.

Across all 20 apps: 22%. About 1 in 8 reports is real; weak on numbers and permissions.

https://github.com/Todmy/jevqa

### Variant B

Opus 5 found 17% of known bugs for $3.20/app. Tuned jevqa found 24% for $0.37 on the same 10 development apps.

Across all 20 apps, jevqa found 22%. About 1 in 8 reports is real. Weak on numbers and permissions.

No tests to write.

https://github.com/Todmy/jevqa

## B. Five-post thread

### Variant A

**Post 1**

Jev made browser testing cheap enough to run before QA.

Same 10 development apps: tuned jevqa found 24% at $0.37/app; Opus 5 found 17% at $3.20. Across all 20 apps, jevqa found 22%. About 1 in 8 reports is real.

I open-sourced it.

**Post 2**

Give jevqa a URL and the README you already have:

`uvx jevqa run <url> --spec README.md`

No tests or selectors to write. In 5–6 minutes it leaves a report you can skim in ninety seconds before showing the app to anyone.

**Post 3**

Most testers can only break controls they find.

jevqa also reports the Edit, Delete, or Save control named in the spec that never appears anywhere in the app. That absence path is where a lot of obvious defects hide.

**Post 4**

Jev is TypeSafe's System One model: it returns a probability or choice instead of text at $0.042 per million tokens, picks every action, and judges every screen; Claude reads the spec once to write the checklist.

It's weak on numeric correctness and permissions.

**Post 5**

It also runs as a GitHub Action. Code, raw methodology, and the public benchmark:

https://github.com/Todmy/jevqa

### Variant B

**Post 1**

Same 10 development apps: tuned jevqa found 24% of known bugs at $0.37/app. Opus 5 found 17% at $3.20; Sonnet 5 found 10% at $1.16.

Across all 20 apps, jevqa found 22%. About 1 in 8 reports is real. I open-sourced it.

**Post 2**

This is for the app you made with Lovable, Bolt, Replit, or Claude Code and want to check before anyone sees it.

One command. A URL and the README you already have. No tests to write. The run takes 5–6 minutes; the report takes ninety seconds to skim.

**Post 3**

The useful trick is absence.

If the spec says users can edit a post but no Edit control exists on any screen, jevqa reports it. Every tester can click a broken button. This one notices the button never shipped.

**Post 4**

The development comparison has a caveat: jevqa was tuned there; Opus and Sonnet weren't. On the untouched holdout, jevqa found 18–20%.

Jev returns a probability or choice instead of text at $0.042 per million tokens; Claude only writes the checklist.

**Post 5**

Local CLI or GitHub Action. No test suite required.

Code and the reproducible benchmark:

https://github.com/Todmy/jevqa

## C. Reply under Rafal's post

### Variant A

Open-sourced jevqa. Same 10 development apps: tuned jevqa found 24% at $0.37/app; Opus 5 found 17% at $3.20. All 20 apps: 22%. About 1 in 8 reports is real. Weak on numbers and permissions. https://github.com/Todmy/jevqa

### Variant B

Built the open-source version: jevqa. No tests to write: URL + README, 5–6 minutes, $0.29–0.41/app. Across 20 apps it found 22% of 107 bugs. About 1 in 8 reports is real; weak on numbers and permissions. https://github.com/Todmy/jevqa
