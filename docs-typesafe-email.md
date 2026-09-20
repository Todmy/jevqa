To: hello@typesafe.ai
Subject: jevqa — an open-source bug hunter built on Jev, with a published benchmark

Hi,

Your launch post asked where Jev works and where it falls short. Here is one answer with numbers.

jevqa is an MIT-licensed autonomous tester for web apps. Jev makes every decision: which element to act on next (choice), whether the screen after an action looks broken (noul oracles), how likely each spec expectation is to fail (score). Claude reads the spec once for a checklist; everything else is Jev, about 150 calls per app.

Measured on WebTestBench (20 AI-generated apps, 107 known bugs): it finds 22% of them at $0.29–0.41 and 5–6 minutes per app. A Claude Opus 5 + Playwright MCP agent on the same apps: 17% at $3.20. Nobody else in the QA-tool category publishes recall at all, so the benchmark page is the launch: <repo>/BENCHMARK.md

Where Jev fell short, honestly: recall plateaus around 20% and the ceiling is on the action side, not the judge. Jev's answers were near-deterministic (spread ≤0.13 across repeats), so 3× sampling bought nothing; oracle-prompt tuning bought nothing either. The judge is not the bottleneck, which is a good problem for you to have.

Two asks:
1. Is the $0.042/MTok price durable past early access? The whole cost story rests on it.
2. If a benchmarked, open-source Jev application is useful to you as a showcase, I would like to be it. Launching on Hacker News in two weeks.

Repo: <repo>   Report example: <repo>/examples/blog-app/report.md

Dmytro Tolok
