"""Keys live in ~/.config/jevqa/config.json (env vars override). `ensure()` runs before every `jevqa run`:
all set -> continue silently; something missing -> ask interactively (or fail with instructions when there is no TTY, e.g. CI)."""
import getpass, json, os, shutil, sys
from pathlib import Path

PATH = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "jevqa" / "config.json"
KEYS = {"TYPESAFE_API_KEY": "TypeSafe (Jev) API key — https://console.typesafe.ai",
        "ANTHROPIC_API_KEY": "Anthropic API key — https://console.anthropic.com (or leave empty to use the Claude Code CLI)"}


def load():
    try: return json.loads(PATH.read_text())
    except (OSError, ValueError): return {}


def save(cfg):
    PATH.parent.mkdir(parents=True, exist_ok=True)
    PATH.write_text(json.dumps(cfg, indent=1)); PATH.chmod(0o600)


def _ask(key, cfg):
    print(f"\n{key} is not set. {KEYS[key]}")
    if key == "ANTHROPIC_API_KEY" and shutil.which("claude"):
        print("  1) enter an Anthropic API key (recommended, ~$0.25 per app)\n  2) use the logged-in Claude Code CLI (billed to your subscription)\n  3) quit")
        c = input("choice [1]: ").strip() or "1"
        if c == "2": cfg["CLAUDE_BACKEND"] = "cli"; return True
        if c != "1": return False
    v = getpass.getpass(f"{key}: ").strip()
    if not v: return False
    cfg[key] = v; return True


def ensure():
    cfg = load()
    for k, v in cfg.items():
        if k in KEYS and v: os.environ.setdefault(k, v)
    missing = [k for k in KEYS if not os.environ.get(k)]
    if "ANTHROPIC_API_KEY" in missing and (os.environ.get("CLAUDE_BACKEND") or cfg.get("CLAUDE_BACKEND")) == "cli" and shutil.which("claude"): missing.remove("ANTHROPIC_API_KEY")
    if not missing: return
    if not sys.stdin.isatty():
        sys.exit("missing: " + ", ".join(missing) + f". Set them as env vars / secrets (or CLAUDE_BACKEND=cli to use the Claude Code CLI), or run `jevqa config` once on a machine with a terminal (stored in {PATH}).")
    from . import telemetry; telemetry.track("keys_prompted", missing=missing)
    changed = False
    for k in missing:
        if not _ask(k, cfg): sys.exit("cannot run without it")
        changed = True
    if changed and (input(f"save to {PATH}? [Y/n]: ").strip().lower() or "y") == "y": save(cfg)
    for k in KEYS:
        if cfg.get(k): os.environ.setdefault(k, cfg[k])


def show():
    cfg = load()
    for k in KEYS:
        src = "env" if os.environ.get(k) else ("config" if cfg.get(k) else "-")
        print(f"{k:20s} {src}")
    print(f"{'claude backend':20s} {'cli' if cfg.get('CLAUDE_BACKEND') == 'cli' and not os.environ.get('ANTHROPIC_API_KEY') else 'api'}")
    print(f"file: {PATH}")
