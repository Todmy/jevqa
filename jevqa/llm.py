"""Claude calls via the Anthropic SDK (replaces `claude -p` CLI): JSON in, parsed JSON out, cost tracked in USAGE."""
import json, os, re, subprocess

MODELS = {"sonnet": "claude-sonnet-5", "haiku": "claude-haiku-4-5-20251001"}
PRICE = {"sonnet": (3.0, 15.0), "haiku": (1.0, 5.0)}      # $/MTok in, out
USAGE = {"claude_usd": 0.0, "claude_calls": 0}
_client = None


def _parse(body):
    fence = re.search(r"```(?:json)?\s*(.*?)```", body, re.S)
    for cand in ([fence.group(1)] if fence else []) + [body] + [m.group() for m in re.finditer(r"[\[{].*[\]}]", body, re.S)]:
        try: return json.loads(cand)
        except ValueError: pass
    return None


def _cli(prompt, model):
    """Fallback when ANTHROPIC_API_KEY is absent: the user's logged-in Claude Code CLI (subscription billing)."""
    out = subprocess.run(["claude", "-p", "--output-format", "json", "--model", model], input=prompt, text=True, capture_output=True).stdout
    try: res = json.loads(out)
    except ValueError: return None
    if not isinstance(res, dict): return None
    USAGE["claude_usd"] += res.get("total_cost_usd", 0); USAGE["claude_calls"] += 1
    return _parse(res.get("result", ""))


def claude_json(prompt, model="haiku", max_tokens=8000):
    global _client
    if not os.environ.get("ANTHROPIC_API_KEY"): return _cli(prompt, model)
    if _client is None:
        import anthropic
        _client = anthropic.Anthropic()                 # ANTHROPIC_API_KEY from env
    r = _client.messages.create(model=os.environ.get(f"JEVQA_{model.upper()}", MODELS[model]), max_tokens=max_tokens,
                                messages=[{"role": "user", "content": prompt}])
    pi, po = PRICE[model]
    USAGE["claude_usd"] += r.usage.input_tokens / 1e6 * pi + r.usage.output_tokens / 1e6 * po; USAGE["claude_calls"] += 1
    return _parse("".join(b.text for b in r.content if b.type == "text"))
