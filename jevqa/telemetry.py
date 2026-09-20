"""Anonymous usage events to PostHog. Off with JEVQA_TELEMETRY=0. Never sends URLs, specs or report text."""
import hashlib, json, os, platform, uuid
from . import __version__

KEY = os.environ.get("JEVQA_POSTHOG_KEY", "")            # ponytail: project key baked in at release time; empty = no-op
HOST = "https://eu.i.posthog.com"


def _id():
    try: return hashlib.sha256(f"{uuid.getnode()}{platform.node()}".encode()).hexdigest()[:16]
    except Exception: return "anon"


def track(event, **props):
    if not KEY or os.environ.get("JEVQA_TELEMETRY", "1") == "0" or os.environ.get("CI") and os.environ.get("JEVQA_TELEMETRY") != "1": return
    try:
        import requests
        requests.post(f"{HOST}/capture/", timeout=3, json={"api_key": KEY, "event": event, "distinct_id": _id(),
                      "properties": {"version": __version__, "os": platform.system(), "ci": bool(os.environ.get("GITHUB_ACTIONS")), **props}})
    except Exception: pass
