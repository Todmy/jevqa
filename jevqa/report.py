"""Deterministic bug-report sentences per finding (the benchmark's REPORTS=template stage) + markdown writer."""
import hashlib, json, os, requests
from pathlib import Path

WHAT = {"zeros": "a chart, total or summary shows zero/empty values although data exists", "count_mismatch": "a counter or badge does not match the number of visible items",
        "wrong_page": "the app shows the wrong page or view for the action", "wrong_item": "a different item than the one acted on is shown or changed", "empty_list": "a list that should contain items is empty",
        "placeholder": "placeholder, garbled or untranslated text is visible", "duplicate": "a duplicate entry or record appeared", "stale": "old values remain after the update/delete",
        "missing_feedback": "no confirmation or feedback appeared after the action", "missing_control": "a control or content the spec requires on this page is absent", "other": "something else"}
VAGUE = {"initial_broken", "inconsistent_state", "broken_content", "expectation_violated", "page_incomplete"}

def what_is_wrong(f, cache):
    """Post-hoc Jev choice on the stored evidence: name the concrete defect for vague flags."""
    ev = f.get("evidence") or {}
    if not (set(f.get("flags") or []) & VAGUE) or not (ev.get("after") or {}).get("text"): return None
    key = hashlib.md5((f.get("action", "") + ev["after"]["text"][:1500]).encode()).hexdigest()
    if key not in cache:
        st = {"action": f.get("action"), "flags": f.get("flags"), "expectation": f.get("expectation"), "before": (ev.get("before") or {}).get("text", "")[:1500], "after": ev["after"]["text"][:2500], "diff": f.get("diff")}
        r = requests.post("https://api.typesafe.ai/v1/systemone", headers={"Authorization": f"Bearer {os.environ['TYPESAFE_API_KEY']}"}, timeout=30,
                          json={"model": "jev-latest", "state": st, "questions": {"what": {"type": "choice", "criteria": WHAT,
                                "instructions": "An oracle flagged this state with `flags`. Judging `after` (and `diff`, `expectation`), which single description names what is CONCRETELY wrong on the page?"}}})
        r.raise_for_status(); a = r.json()["answers"]["what"]
        cache[key] = a["choice"] if a["confidence"] >= 0.3 and a["choice"] != "other" else None
    return cache[key]

def template_report(f, cache):
    ev, d = f.get("evidence") or {}, f.get("diff") or {}
    PHRASE = {"action_ignored": "clicking/using it had no visible effect (the UI did not react as the control's label promises)", "invalid_accepted": "an INVALID value was accepted without any validation error", "valid_rejected": "a valid submission was rejected or ignored", "form_values_mangled": "after submitting, the form shows values that are neither the defaults nor what was entered (silently normalized instead of validated)", "detail_mismatch": "the opened detail view shows a value contradicting the one in the clicked card/link", "cap_below_capacity": "the +/- control stops at a limit lower than the availability/capacity the page states", "permission_leak": "a control/content that the spec reserves for another role is visible on this screen", "duplicate_banner": "the success/confirmation message appears twice (the effect fired more than once)",
              "error_shown": "an error message or failure notice appeared", "inconsistent_state": "the page then showed self-contradictory data (counts, items or page not matching the action)", "broken_content": "the page showed placeholder/garbled/missing content",
              "dead_end": "the user was left with no way to continue", "expectation_violated": "the spec expectation for this step was NOT met", "initial_broken": "the initial page renders wrong seed data/summary", "page_incomplete": "the page lacks content/controls the spec requires here",
              "role_leak": "a control reserved for another role is visible", "filter_unchanged": "the list did not change after the filter/search/sort", "filter_inconsistent": "items inconsistent with the selected filter remained", "value_not_propagated": "the submitted record did not appear where it should",
              "effect_magnitude": "one click changed a counter by 2 or more (double-fire)", "dead_link": "the link led nowhere (URL and page unchanged)", "blank_page": "the page went blank", "js_exception": "a JavaScript exception was thrown", "http_error": "an HTTP error response occurred", "expectation_unreachable": "the feature the spec requires could not be found anywhere"}
    flags = f.get("flags") or []
    if "expectation_unreachable" in flags:
        return f'BUG (missing feature): the spec requires "{f.get("expectation")}", but no control, page or content implementing it exists in the app — the tester searched for it over several steps (last page {f.get("page")}) and found nothing to click, fill or read for it.'
    what = what_is_wrong(f, cache)
    out = f'BUG: on {f.get("page")}, after "{f.get("action")}", ' + "; ".join(PHRASE.get(k, k) for k in flags) + (f' — concretely: {WHAT[what]}' if what else "") + "."
    if f.get("repeated"): out += f' The control was pressed {f["repeated"]["presses"]} times in a row and the value stopped changing (see counters below).'
    if f.get("expectation"): out += f' Expected (spec): {f["expectation"]}.'
    d = f.get("diff") or {}
    if d: out += f' Actual: url_changed={d.get("url_changed")}; text that appeared: {json.dumps(d.get("added_lines", [])[:6], ensure_ascii=False)[:400]}; counters: {d.get("counters_changed")}.'
    out += f' Details: the tester did: {f.get("action")}.'
    if f.get("values"): out += f' Submitted values: {json.dumps(f["values"], ensure_ascii=False)[:400]}.'
    if f.get("rule"): out += f' The payload deliberately violated the rule: {f["rule"]}.'
    if f.get("expectation"): out += f' Spec expectation for this step: {f["expectation"]}.'
    out += f' Oracle verdict: {", ".join(f.get("flags") or [])}.'
    if d: out += f' Observed: url_changed={d.get("url_changed")}; added text: {json.dumps(d.get("added_lines", [])[:6], ensure_ascii=False)[:400]}; counters: {d.get("counters_changed")}.'
    else: out += f' Visible text after: {(ev.get("after") or {}).get("text", "")[:300]!r}.'
    for k in ("console_errors", "js_exceptions", "http_errors"):
        if ev.get(k): out += f' {k}: {json.dumps(ev[k])[:200]}.'
    return out




def reports_for(rep):
    """[(finding, sentence)] for a finished run: replay filter, absence/page errors verbatim, template for the rest."""
    cache, out = {}, []
    for f in rep["findings"]:
        if f.get("reproduced") is False and not f.get("deterministic"): continue      # verify-by-replay: drop non-reproducible
        kind = f.get("kind")
        if (f.get("report") and f.get("how") == "absence") or kind in ("pageerror", "blank_page"):
            out.append((f, f.get("report") or f.get("message") or f.get("action") or kind))
        else:
            out.append((f, template_report(f, cache)))
    return out


def write_markdown(run, url):
    rep = json.load(open(run / "findings.json"))
    items = reports_for(rep)
    usd = rep["jev"]["input_tokens"] / 1e6 * 0.042 + rep["jev"].get("claude_usd", 0)
    lines = [f"# jevqa report: {url}", "",
             f"{len(items)} findings · {rep['steps']} steps · {rep['states']} screens · {rep['secs']:.0f}s · ${usd:.2f} (Jev {rep['jev']['calls']} calls, Claude {rep['jev'].get('claude_calls', 0)})", "",
             f"Expectations exercised without violation: {len(rep.get('subgoals_done', []))}/{len(rep.get('expectations', []))}. "
             "Expect roughly 1 in 8 findings to be a confirmed defect; the rest are noise or defects outside the spec. Triage top to bottom.", ""]
    order = {"absence": 0, "init": 1, "probe": 2, "step": 3}
    items.sort(key=lambda t: order.get((t[0].get("how") or "").split("(")[0], 9))
    for i, (f, text) in enumerate(items, 1):
        flags = ", ".join(f.get("flags") or [])
        lines += [f"## {i}. {flags or f.get('kind') or 'finding'}", "", text, ""]
        shot = run / "flagged" / f"{f.get('step', -1):03d}.png"
        if shot.exists(): lines += [f"![step {f.get('step')}](flagged/{shot.name})", ""]
    (run / "report.md").write_text("\n".join(lines))
    return run / "report.md", len(items), usd
