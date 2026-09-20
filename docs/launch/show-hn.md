# Show HN

Post Tue–Thu, 08:00 US Eastern (14:00 Kyiv). Benchmark page must be live. Ping the warm list at post time: 30–50 upvotes in the first hour is the whole game.

**Title (78 chars max):**
Show HN: jevqa – a $0.35 monkey tester that found 22% of known bugs in 20 apps

**URL:** https://github.com/Todmy/jevqa

**First comment (post immediately after submitting):**

Hi HN, I built this after ~80 benchmark runs trying to make an autonomous web tester that is cheap enough to run on every preview deploy.

What it does: `uvx jevqa run <url> --spec README.md`. It reads your spec once (Claude), then explores the app on its own. Every decision on every screen – which element to act on, does this screen look broken – is a typed judgment from Jev, TypeSafe's "System One" model, which returns a probability instead of text at $0.042/MTok. A full 50-action run is 5–6 minutes and $0.29–0.41. Output is report.md with a sentence and a screenshot per finding.

Numbers, because nobody in this category publishes any: on WebTestBench (20 AI-generated apps, 107 human-verified bugs) it finds 22% of the known bugs. A Claude Opus 5 + Playwright MCP agent on the same apps: 17% at $3.20/app. About 1 in 8 of jevqa's findings maps to a confirmed bug; the rest is noise or bugs the checklist does not list. Methodology, noise protocol and per-version table: https://github.com/Todmy/jevqa/blob/main/BENCHMARK.md

What it is good at: missing or unreachable features (no edit/delete/search, a role that can only view) – half of everything it finds. Validation gaps. Dead buttons. Data lost on reload.

What it is bad at: sliders and drag, wrong numbers, permissions, long flows. It is a pre-QA smoke bot, not a QA replacement.

Things I would love to hear: whether the 1-in-8 is tolerable for a 5-minute report you skim, and whether anyone has a tester I can put on the leaderboard – submissions are a PR.

MIT, Python, bring your own keys (TypeSafe + Anthropic, or your Claude Code CLI).

**Answers to have ready:**
- "Why not just use Playwright MCP + Claude?" → we did, it is the $3.20 row. Same recall band, 9× the cost, and it needs a frontier model in the loop for every click.
- "1 in 8 is terrible" → for a tool that pages you, yes. For a 90-second skim before QA, it is the trade. Findings are ordered: missing features first, those are the reliable ones. Ranking by Jev's calibrated confidence is next.
- "Is Jev just a small LLM?" → it does not generate text; it returns typed answers with calibrated probabilities. Near-deterministic in our runs (spread ≤0.13 across repeats), which is why 3× sampling bought nothing.
- "Recall ceiling 20%?" → yes, and the Opus agent hits the same wall. The bottleneck is action coverage (role switching, deep flows), not the judge.
- "Will TypeSafe raise prices?" → unknown; the judgment interface is swappable and I say so in the README.
