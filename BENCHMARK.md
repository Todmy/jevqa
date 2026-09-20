# Benchmark: autonomous bug finding on WebTestBench

No vendor in this category publishes recall. This page does, for jevqa and for every tester anyone cares to submit.

## Setup

- **Dataset**: [WebTestBench](https://github.com/friedrichor/WebTestBench) — 100 AI-generated web apps, each with a human-verified checklist of spec items and which of them fail. We use apps 1–10 (58 failing items) as the development split and apps 11–20 (49 failing items) as the **holdout**, never touched while tuning.
- **Budget**: 50 actions per app. One run per app per row unless stated.
- **Scoring**: an Opus 5 majority-vote matcher maps every report to a checklist item or to nothing. Report mapped to a *failing* item = **true positive** (counted once per item). Mapped to a *passing* item = **false positive**. Mapped to nothing = **unmatched**: noise, or a real defect the checklist does not list. Unmatched is not counted as a false positive.
- **Cost**: model tokens only (Jev at $0.042/MTok input, Claude at list price). Matcher cost excluded for every row.
- **Noise**: the same code run twice differs by up to 4 bugs out of 58; the same reports rescored differ by up to 4. **Any single-run difference under 4 bugs is noise.** Treat 1-bug deltas as ties.

## Leaderboard

| tester | split | bugs found | recall | precision | $/app | min/app | source |
|---|---|---|---|---|---|---|---|
| **jevqa v15** (Jev + Claude checklist) | apps 1–10 | 14/58 | 24% | 0.33 | 0.37 | 5.8 | this repo |
| Claude Opus 5 + Playwright MCP, free exploration | apps 1–10 | 10/58 | 17% | 0.33 | 3.20 | 5.3 | `bench/run.py --tool claude` |
| jevqa v14 (per-bug tuned) | apps 1–10 | 11–13/58 | 19–22% | 0.39–0.52 | 0.20–0.26 | 4.1 | 3 seeds |
| Claude Sonnet 5 + Playwright MCP | apps 1–10 | 6/58 | 10% | 0.22 | 1.16 | 3.6 | |
| gremlins.js (random monkey, console errors only) | apps 1–10 | 0/58 | 0% | — | 0.00 | 0.1 | |
| **jevqa v15** | **holdout 11–20** | 9/49, 10/49 | 18–20% | 0.16–0.18 | 0.29–0.41 | 5.0–5.6 | 2 seeds |
| jevqa v9 (no absence path) | holdout 11–20 | 8/49 | 16% | 0.29 | 0.34 | 5.0 | |
| jevqa v14 | holdout 11–20 | 6/49 | 12% | 0.21–0.25 | 0.30–0.34 | 4.2 | 2 seeds |

Opus and Sonnet agents were not run on the holdout split (cost). Submissions welcome.

Combined over 20 apps, jevqa v15 finds 23–24 of 107 known bugs (22%) at $0.29–0.41 per app. About 1 in 8 of its reports maps to a confirmed defect. We publish that number because a tool that hides it is lying to you.

## What we learned tuning it (so you do not repeat it)

- 15 versions, ~80 benchmark runs. Only two changes moved recall on the holdout: structured before/after diffs fed to the judge, and the **absence path** (a spec-named control that appears on no screen becomes a finding).
- Everything tuned per bug on apps 1–10 (8 targeted oracles and probes, +3 to +5 bugs there) gave **0** on the holdout. Judge every mechanism on a split it was not tuned on.
- Oracle-prompt tuning, risk triage, form auto-completion, widget drivers, report rewording, 3× sampling: no measurable gain. The recall ceiling (~20%) is on the action side, shared with the Opus agent, and is not the judge model.

## Submit a tester

Open a pull request adding a row. Include:
1. The exact command and version, and the split (1–10, 11–20 or both).
2. Raw reports per app (one JSON list of strings per app) so we can rescore them with the same matcher.
3. Token or dollar cost per app and wall-clock time.

We rescore every submission with the same matcher and add the row with a link to your raw reports. Rows with fewer than 10 apps are listed but marked as partial.

## By bug class (jevqa v15, apps 1–10 + holdout seed b, 24 bugs)

| WebTestBench class | found | of |
|---|---|---|
| functionality (missing or broken feature) | 16 | 56 |
| constraint (validation, business rule) | 5 | 29 |
| content (wrong or missing content) | 1 | 7 |
| interaction (UI behaviour, widgets) | 2 | 15 |

Missing or unreachable features are half of everything it finds. Interaction quality is where it is weakest.
