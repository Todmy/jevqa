# X launch copy

## A. Standalone post

### Variant A

Jev made browser testing cheap enough to run before QA.

jevqa takes a URL and a spec. It found 22% of 107 known bugs across 20 apps for $0.29–0.41/app.

About 1 in 8 reports is real. It's weak on numeric correctness and permissions.

https://github.com/Todmy/jevqa

### Variant B

Claude Opus 5 with Playwright MCP cost $3.20/app and found 17% of known bugs on our development split.

The Jev-guided monkey found 24% for $0.37/app.

I open-sourced it. About 1 in 8 reports is real. Weak on numeric correctness and permissions.

https://github.com/Todmy/jevqa

## B. Five-post thread

### Variant A

**Post 1**

Jev made adversarial browser testing cheap enough to run before QA.

I built jevqa, an open-source monkey tester that reads the spec and tries to break the deployed app. The benchmark is public, including the ugly numbers.

**Post 2**

Give it a URL and the README or PRD the app was built from.

Jev picks actions and judges each screen. Claude reads the spec once to make the checklist. No selectors or test scripts to maintain.

**Post 3**

On WebTestBench, jevqa found 22% of 107 known bugs across 20 apps. A run takes 5–6 minutes and costs $0.29–0.41.

Claude Opus 5 with Playwright MCP found 17% at $3.20/app on the development split.

**Post 4**

About 1 in 8 reports maps to a confirmed defect. It's weak on numeric correctness and permissions.

That's acceptable for a pre-QA report I can skim in ninety seconds. It isn't a QA replacement.

**Post 5**

Code, install instructions, raw methodology, and the benchmark:

https://github.com/Todmy/jevqa

### Variant B

**Post 1**

Most browser testers can only break controls they find.

jevqa also reports the edit or delete control named in the spec that never appears. That absence path helped it find 22% of 107 known bugs across 20 apps. I open-sourced it.

**Post 2**

The command is:

`uvx jevqa run http://localhost:3000 --spec README.md`

It explores for up to 50 actions, replays suspected failures, then writes a report with one sentence and a screenshot per finding.

**Post 3**

A full run takes 5–6 minutes and costs $0.29–0.41.

We also ran Claude Opus 5 with Playwright MCP on the development split. It found 17% at $3.20/app. Same rough recall band, much more money.

**Post 4**

The catch is precision. About 1 in 8 reports is a confirmed defect. It's also weak on numeric correctness and permissions.

Use it to clear obvious failures before QA, not to replace QA.

**Post 5**

MIT, source, GitHub Action, and the public benchmark:

https://github.com/Todmy/jevqa

## C. Reply under Rafal's post

### Variant A

I built the open-source version: jevqa. It found 22% of 107 known bugs across 20 apps at $0.29–0.41/app. About 1 in 8 reports is real; it's weak on numeric correctness and permissions. Public benchmark: https://github.com/Todmy/jevqa

### Variant B

This is now open source as jevqa: URL plus spec, then Jev tries to break the app. 22% of 107 known bugs across 20 apps. About 1 in 8 reports is real; numeric correctness and permissions are weak. https://github.com/Todmy/jevqa
