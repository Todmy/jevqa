# 10 unsolicited reports (channel test 1)

Goal: reciprocity first. Run jevqa on 10 public vibe-coded apps, send each builder their report as a gist. No ask in the first message.

**Where to find targets:** Lovable "Launched" gallery, Bolt community showcase, r/vibecoding "I built…" posts, X search `"built with lovable"` / `"built with bolt.new"` last 7 days, Product Hunt launches tagged no-code/AI-built. Pick apps with a public URL and a README or landing copy that can serve as the spec.

**Run:** `jevqa run <url> --spec spec.md --out runs/<name>`; paste the landing page / About text into spec.md if there is no README. Read the report, delete obviously-wrong findings by hand before sending (this is a first impression, not a benchmark).

**Message (DM or reply, ≤ 80 words):**

> Ran an autonomous tester I'm building against <app> for 5 minutes, thought you'd want the output before anyone else finds it: <gist link>. 7 findings, I'd guess 2–3 are real (the missing edit on <page>, the date field that takes past dates). Ignore the rest. No ask, just figured it's more useful in your hands than mine.

**If they reply:** then, and only then: "It's `uvx jevqa run <url> --spec README.md` if you want to rerun after fixing. Would love to know which findings were real – that's the number I'm trying to improve."

**Signal:** ≥6 replies, ≥3 self-installs, ≥1 public post of their own report within 14 days.
**Kill:** <3 replies, or replies of the form "I knew all of that".

**Tracker:**

| # | app | builder | platform | sent | replied | installed | posted |
|---|---|---|---|---|---|---|---|
| 1 | | | | | | | |
| … | | | | | | | |
