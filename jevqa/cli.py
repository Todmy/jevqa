"""jevqa run <url> --spec <file>: autonomous pre-QA bug hunt, report.md + screenshots in --out."""
import argparse, os, sys, time
from pathlib import Path

GOAL = ("Explore this app like a manual tester hunting for bugs; try to complete every feature end to end "
        "(fill whole forms and submit, open details, use filters). The app was built from this spec: {spec}")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="jevqa", description="Jev-guided monkey tester: finds missing features, validation gaps and dead controls before QA does.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="test one deployed app")
    r.add_argument("url")
    r.add_argument("--spec", required=True, help="spec / README / PRD text file the app was built from")
    r.add_argument("--steps", type=int, default=50, help="action budget (default 50 ≈ 5 min, ~$0.35)")
    r.add_argument("--out", default="jevqa-runs")
    r.add_argument("--headed", action="store_true")
    c = sub.add_parser("config", help="set or show API keys (stored in ~/.config/jevqa/config.json)")
    c.add_argument("--reset", action="store_true", help="forget saved keys and ask again")
    a = ap.parse_args(argv)
    from . import config
    if a.cmd == "config":
        if a.reset and config.PATH.exists(): config.PATH.unlink()
        config.ensure(); config.show(); return
    config.ensure()
    from . import tester, report, telemetry
    telemetry.track("run_started", steps=a.steps, backend="cli" if not os.environ.get("ANTHROPIC_API_KEY") else "api")
    spec = Path(a.spec).read_text()
    argv = ["--base", a.url, "--goal", GOAL.format(spec=spec), "--steps", str(a.steps), "--out", a.out] + (["--headed"] if a.headed else [])
    t0 = time.time()
    run = tester.main(argv)
    path, n, usd = report.write_markdown(run, a.url)
    print(f"\n{n} findings -> {path}  ({time.time() - t0:.0f}s, ${usd:.2f})")
    telemetry.track("run_finished", steps=a.steps, findings=n, secs=round(time.time() - t0), usd=round(usd, 2))
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as fh: fh.write(f"report={path}\nfindings={n}\nrun_dir={run}\n")


if __name__ == "__main__":
    main()
