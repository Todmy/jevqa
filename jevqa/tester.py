"""Jev-guided monkey tester, v8.

Layers: code (abstract state graph, cheap oracles, recording, replay) -> Jev (action choice, sub-goal check, oracles)
        -> Claude, sparse (Sonnet checklist of expectations once per app, Haiku payload pair once per form) -> Claude report (bench/run.py)
Run: uv run python monkey.py --steps 50 --base http://localhost:6100 --goal "<spec>"
"""
import argparse, hashlib, json, os, random, re, time
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright

JEV_URL = "https://api.typesafe.ai/v1/systemone"
KEY = os.environ.get("TYPESAFE_API_KEY", "")
SAUCE = "https://www.saucedemo.com"
BASE = SAUCE           # overridden by --base
MAX_CANDIDATES = 40
EPSILON = 0.15         # share of random side-steps
FLAG_THRESHOLD = 0.7   # noul above this = suspicious state
MAX_RULES = 8          # ponytail: boundary submits per form; raise if forms with >8 typed fields matter
URL_CAP = 8            # consecutive steps on one path before forcing an exit to an unvisited path
SEL = ('a[href], button, input, select, textarea, [role=button], [role=option], [role=menuitem], [role=tab], '
       '[role=checkbox], [role=switch], [role=slider], [onclick]')
USAGE = {"input_tokens": 0, "calls": 0}
ORACLES = json.load(open(Path(__file__).parent / "oracles.json"))
from . import absence
FORM_CACHE = {}


# ---------------- models ----------------
def jev(state, questions):
    for attempt in range(3):
        try:
            r = requests.post(JEV_URL, headers={"Authorization": f"Bearer {KEY}"},
                              json={"model": "jev-latest", "state": state, "questions": questions}, timeout=30)
            r.raise_for_status(); break
        except requests.RequestException:
            if attempt == 2: raise
            time.sleep(2 * (attempt + 1))
    d = r.json(); USAGE["input_tokens"] += d.get("usage", {}).get("input_tokens", 0); USAGE["calls"] += 1
    return d["answers"]


from .llm import claude_json, USAGE as CLAUDE_USAGE


# ---------------- page model ----------------
def snapshot(page):
    text = page.inner_text("body")[:6000]
    fields = page.evaluate("""() => [...document.querySelectorAll('input:not([type=hidden]), select, textarea')]
        .map(e => `[field ${e.placeholder || e.name || e.id || e.type}='${e.value}']`).join(' ')""")
    text += "\n" + fields
    data = page.evaluate("""(sel) => {
      const fieldTag = t => ['input', 'textarea', 'select'].includes(t);
      const DATE = /select (a )?date|pick a date|choose (a )?date|dd[/]mm|mm[/]dd|yyyy|calendar/i;
      const widget = e => e.getAttribute('role') === 'combobox' ? 'combobox' : e.getAttribute('role') === 'slider' ? 'slider'
        : ['checkbox', 'switch'].includes(e.getAttribute('role')) ? 'checkbox'
        : (e.tagName === 'BUTTON' && (DATE.test(e.innerText) || e.querySelector('svg.lucide-calendar, svg.lucide-calendar-days'))) ? 'date' : null;
      const SUBMIT = /save|creat|submit|add|updat|sign|log ?in|regist|confirm|apply|send|book|place|pay/i;
      const nFields = el => el.querySelectorAll('input:not([type=hidden]):not([type=checkbox]):not([type=radio]), select, textarea, [role=combobox], [role=slider]').length;
      const hasSubmit = el => [...el.querySelectorAll('button')].some(b => b.type === 'submit' || SUBMIT.test(b.innerText));
      // smallest ancestor holding >=2 fields and a submit-like button = the form, whatever markup the app used
      const formOf = e => { let c = e.parentElement; while (c && c !== document.body && !(nFields(c) >= 2 && hasSubmit(c))) c = c.parentElement; return c && c !== document.body ? c : null; };
      const containers = new Map();
      const els = [...document.querySelectorAll(sel)].map((e, i) => [e, i]).filter(([e]) => {
        const r = e.getBoundingClientRect();
        if (!(r.width > 0 && r.height > 0) || e.disabled) return false;
        const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
        if (cy < 0 || cy > innerHeight) return true;   // off-screen centre: Playwright scrolls to it; overlay check impossible
        const hit = document.elementFromPoint(cx, cy);
        return hit && (hit === e || e.contains(hit));
      }).map(([e, i]) => {
        const tag = e.tagName.toLowerCase();
        const box = e.closest('[class*=item], li, tr, form, section, article');
        const name = box && box !== e ? box.querySelector('[class*=name], [class*=title], h1, h2, h3, h4') : null;
        const near = e.closest('div, li, td');
        const label = (e.labels && e.labels[0] ? e.labels[0].innerText : '') || (near && near.querySelector('label') ? near.querySelector('label').innerText : '');
        const w = widget(e);
        const cont = fieldTag(tag) || tag === 'button' || w ? formOf(e) : null;
        let cid = null;
        if (cont) { if (!containers.has(cont)) containers.set(cont, containers.size); cid = containers.get(cont); }
        const svg = e.querySelector('svg');
        return {
          i, tag, type: w || e.type || '', widget: w || undefined, cid, href: tag === 'a' ? e.getAttribute('href') : null,
          text: (fieldTag(tag) || w ? (label || e.placeholder || e.getAttribute('aria-label') || e.name || e.id || e.value)
                               : (e.innerText || e.value || e.getAttribute('aria-label') || e.title || e.name || e.id
                                  || (svg ? svg.getAttribute('class') : '') || '')).trim().slice(0, 60),
          ctx: name ? name.innerText.trim().slice(0, 40) : '',
          attrs: fieldTag(tag) ? {required: e.required || undefined, min: e.min || undefined, max: e.max || undefined,
                                  placeholder: e.placeholder || undefined,
                                  options: tag === 'select' ? [...e.options].map(o => o.text).slice(0, 12) : undefined} : undefined
        };
      });
      const forms = {};
      for (const [cont, cid] of containers) {
        const f = els.filter(x => x.cid === cid && (fieldTag(x.tag) || x.widget) && !['checkbox', 'radio', 'submit', 'button', 'file'].includes(x.type));
        const btns = els.filter(x => x.cid === cid && x.tag === 'button' && !x.widget);
        const btn = btns.find(x => x.type === 'submit' && !/cancel|close/i.test(x.text)) || btns.find(x => SUBMIT.test(x.text));
        if (f.length >= 2) {
          const h = cont.querySelector('h1, h2, h3, h4, [class*=title]');
          forms[cid] = {cid, name: (h ? h.innerText : (btn ? btn.text : 'form')).trim().slice(0, 50), fields: f.map(x => x.i), submit: btn ? btn.i : null};
        }
      }
      return {els, forms};
    }""", SEL)
    return {"url": page.url.replace(BASE, ""), "title": page.title(), "text": text, "elements": data["els"], "forms": data["forms"]}


def norm(s): return re.sub(r"\d+", "#", s or "")


def counters(text): return set(re.findall(r"[A-Za-z][A-Za-z ]{2,30}[:#]?\s*\(?\d+\)?", text))   # "Total Events 3", "Upcoming (0)"


def counter_map(text): return dict(re.findall(r"([A-Za-z][A-Za-z ]{2,30}?)\s*[:#]?\s*\(?\$?(-?[\d,]+(?:\.\d+)?)k?\)?(?=\s|$)", text))


def diff(before, after):
    """Code-computed change between two snapshots: what the oracle points at instead of two text blobs (v9)."""
    b, a = before["text"].splitlines(), after["text"].splitlines()
    bs, as_ = set(b), set(a); cb, ca = counter_map(before["text"]), counter_map(after["text"])
    d = {"url_changed": before["url"] != after["url"],
         "added_lines": [x for x in a if x.strip() and x not in bs][:30], "removed_lines": [x for x in b if x.strip() and x not in as_][:30],
         "counters_changed": {k: [cb[k], ca[k]] for k in cb if k in ca and cb[k] != ca[k]}}
    d["changed"] = d["url_changed"] or bool(d["added_lines"]) or bool(d["removed_lines"]) or bool(d["counters_changed"])
    return d


def state_sig(snap):
    """Abstract state: normalized path + set of interactive elements; free text ignored."""
    path = norm(snap["url"].split("?")[0])
    els = sorted({f'{e["tag"]}:{e["type"]}:{norm(e["text"])[:30]}' for e in snap["elements"]})[:80]
    return hashlib.md5((path + "|" + "|".join(els)).encode()).hexdigest()[:10]


def locator(page, idx): return page.locator(SEL).nth(idx)


def describe(el):
    ctx = f' ({el["ctx"]})' if el["ctx"] and el["ctx"] not in el["text"] else ""
    return f'{el["tag"]}{"[" + el["type"] + "]" if el["type"] else ""} "{el["text"]}"{ctx}'


def login(page, user):
    page.goto(BASE); page.fill("#user-name", user); page.fill("#password", "secret_sauce"); page.click("#login-button")
    page.wait_for_load_state("networkidle")


# ---------------- actions ----------------
def drive(page, loc, kind, value=None, past=False):
    """Radix/shadcn widgets: combobox -> option (by text, else first enabled); date trigger -> enabled day after today (before, when past);
    slider -> ArrowRight x3; role checkbox/switch -> click. Returns the option/day text picked."""
    if kind == "combobox":
        loc.click(timeout=3000); page.wait_for_timeout(300)
        opts = page.locator("[role=option]:not([aria-disabled=true]):not([data-disabled])")
        pick = opts.filter(has_text=str(value)) if value else opts
        pick = pick.first if pick.count() else opts.first
        text = pick.inner_text(timeout=1500); pick.click(timeout=1500); return text
    if kind == "date":
        loc.click(timeout=3000); page.wait_for_timeout(300)
        if past:
            page.locator("button[name=previous-month]").first.click(timeout=1500); page.wait_for_timeout(200)
        days = page.locator("[role=grid] [role=gridcell]:not([disabled]):not([aria-disabled=true])")
        n = days.count(); text = None
        if n:
            day = days.nth(0 if past else min(n - 1, 3))    # earliest enabled day when past is wanted; a few days after the first enabled otherwise
            text = day.inner_text(timeout=1500); day.click(timeout=1500); page.wait_for_timeout(200)
        if page.locator("[role=grid]").count(): loc.click(timeout=1500)   # popover still open: toggle it shut
        return text
    if kind == "slider":
        loc.focus(timeout=3000)
        for _ in range(3): page.keyboard.press("ArrowRight")
        return "+3"
    loc.click(timeout=3000); return "toggled"       # role checkbox / switch


def act(page, el, value=None):
    """One primitive action; returns the value typed (for replay)."""
    loc = locator(page, el["i"])
    if el.get("widget"): value = drive(page, loc, el["widget"], value)
    elif el["tag"] == "textarea" or (el["tag"] == "input" and el["type"] in ("text", "email", "password", "search", "url", "tel", "number", "date", "")):
        if value is None:
            value = {"number": "12", "date": "2026-10-01", "email": "qa@example.com"}.get(el["type"]) or random.choice(["Test", "", "12345", "<script>x</script>", "Іван"])
        if el["type"] == "number": value = re.sub(r"[^\d.-]", "", value) or "1"
        loc.fill(value, timeout=3000)
    elif el["tag"] == "select":
        loc.select_option(index=1)
    else:
        loc.click(timeout=3000)
    page.wait_for_timeout(600)
    return value


def form_payloads(snap, form, spec):
    fields = [e for e in snap["elements"] if e["i"] in form["fields"]]
    key = hashlib.md5((norm(snap["url"]) + form["name"] + "|".join(f["text"] for f in fields)).encode()).hexdigest()[:10]
    if key not in FORM_CACHE:
        meta = [{"label": f["text"], "type": f["type"] or f["tag"], **{k: v for k, v in (f["attrs"] or {}).items() if v}} for f in fields]
        FORM_CACHE[key] = claude_json(f"""A web app was built from this spec:
{spec}

Today is {time.strftime("%Y-%m-%d")}. A tester is on page {snap["url"]} at the form "{form["name"]}" with these fields:
{json.dumps(meta, ensure_ascii=False)}

Produce test payloads. Values must be strings; for select fields use one of the listed options verbatim; dates as YYYY-MM-DD; numbers as plain digits.
Return ONLY JSON: {{"valid": {{"<label>": "<realistic valid value>", ...all fields...}},
 "invalid": {{"field": "<label>", "value": "<value violating a business rule or boundary implied by the spec/field (e.g. 0 or -1 for a price/quantity/count/budget, rating 7 on a 0-5 scale, a past date where the future is required or a far-future date where the past is required, a range whose start is after its end, malformed email, 300-char name)>", "rule": "<the rule it violates, one sentence>"}}}}""") or {}
    if not isinstance(FORM_CACHE[key], dict) or not isinstance(FORM_CACHE[key].get("valid"), dict): FORM_CACHE[key] = {}
    return fields, FORM_CACHE[key]


def boundary_rules(fields, valid):
    """Rule-based boundary matrix per field type, no LLM: [(label, value, rule, past)]."""
    def kind(f):
        typ, lab = (f["type"] or "").lower(), f["text"].lower()
        if typ == "number" or re.search(r"budget|guest|price|quantity|qty|amount|count|salary|capacity|party|size|rating|age", lab): return "number"
        if typ == "date" or f.get("widget") == "date" or "date" in lab: return "date"
        if typ == "email" or "email" in lab: return "email"
        if typ == "tel" or "phone" in lab: return "phone"
        return None
    today = time.time(); rules = []
    for f in fields:
        lab, k = f["text"], kind(f)
        if k == "number": rules += [(lab, "0", f"{lab} must be a positive number, 0 is not allowed", False), (lab, "-1", f"{lab} cannot be negative", False)]
        elif k == "date":
            rules.append((lab, time.strftime("%Y-%m-%d", time.localtime(today - 86400)), f"{lab} cannot be in the past (yesterday)", True))
            if not f.get("widget"): rules.append((lab, time.strftime("%Y-%m-%d", time.localtime(today + 50 * 365 * 86400)), f"{lab} must be realistic, 50 years ahead is invalid", False))
        elif k == "email": rules.append((lab, "notanemail", f"{lab} must be a valid email address", False))
        elif k == "phone": rules.append((lab, "abc", f"{lab} must be a valid phone number", False))
    labs = [f["text"] for f in fields]
    for s in labs:                                               # range: start > end, first matching partner
        e = next((x for x in labs if x != s and re.search(r"end|\bto\b|max", x, re.I)), None) if re.search(r"start|from|min", s, re.I) else None
        if e: rules.append(((s, e), ("2099-12-31", "2000-01-01") if "date" in s.lower() else ("999999", "1"), f"{s} must not be greater than {e}", False)); break
    return rules[:MAX_RULES]


def run_form(page, snap, form, spec, opener=None):
    """Fill the form once per boundary rule (a validated form stays open), then all-valid, then the same valid payload again (duplicate). Returns [(phase, values, rule, after)]."""
    fields, pay = form_payloads(snap, form, spec)
    if not pay.get("valid"): return []
    by_label = {f["text"]: f for f in fields}

    def fill(values, past=False):
        for label, v in values.items():
            f = by_label.get(label)
            if not f: continue
            try:
                loc = locator(page, f["i"])
                if f.get("widget"): drive(page, loc, f["widget"], v, past=past and f["widget"] == "date")
                elif f["tag"] == "select":
                    try: loc.select_option(label=str(v), timeout=1500)
                    except Exception: loc.select_option(index=1, timeout=1500)
                else: loc.fill(str(v), timeout=1500)
            except Exception: pass
        for cb in [e for e in snap["elements"] if e["cid"] == form.get("cid") and e["type"] == "checkbox"]:
            try: locator(page, cb["i"]).check(timeout=1000)
            except Exception: pass

    def complete_required():
        """Native validation blocks submit silently: fill every EMPTY :invalid field (the deliberately invalid one has a value and is left alone)."""
        inv = page.locator(":invalid"); n = 0
        for k in range(min(inv.count(), 12)):
            e = inv.nth(k)
            try:
                tag, typ, val = e.evaluate("e => [e.tagName.toLowerCase(), e.type || '', e.value]")
                if val: continue
                if tag == "select": e.select_option(index=1, timeout=1000)
                elif typ == "checkbox": e.check(timeout=1000)
                else: e.fill({"number": "1", "date": time.strftime("%Y-%m-%d", time.localtime(time.time() + 30 * 86400)), "email": "qa@example.com", "tel": "+14155550123", "url": "https://example.com"}.get(typ, "Test value"), timeout=1000)
                n += 1
            except Exception: pass
        return n

    def submit():
        for _ in range(2):
            pre = snapshot(page)
            try:
                if form["submit"] is not None: locator(page, form["submit"]).click(timeout=3000)
                else: page.keyboard.press("Enter")
            except Exception: pass
            page.wait_for_timeout(900)
            if page.url.replace(BASE, "") != snap["url"] or not complete_required(): break   # navigated, or nothing left to complete
        after = snapshot(page)
        after["blocked"] = after["url"] == pre["url"] and after["text"] == pre["text"] and counters(after["text"]) == counters(pre["text"])
        return after

    phases = []
    def closed(): return len({f["text"] for f in fields} & {e["text"] for e in phases[-1][3]["elements"]}) < 2   # form gone (dialog closed / navigated)
    def reopen():
        """Click the element that made the form appear (dialog forms close on accept); rebind to the fresh snapshot."""
        nonlocal snap, form, fields, by_label
        cur = snapshot(page)
        names = ([opener["text"]] if opener and opener.get("text") else []) + \
                [e["text"] for e in cur["elements"] if e["tag"] == "button" and re.search(r"edit|update|modify|details|add|new|create|start", e["text"], re.I)][:3]
        for name in names:
            try: page.get_by_text(name, exact=True).first.click(timeout=2000); page.wait_for_timeout(700)
            except Exception: continue
            s2 = snapshot(page); f2 = next((f for f in s2["forms"].values() if f["name"] == form["name"]), None)
            if f2:
                snap, form = s2, f2; fields = [e for e in s2["elements"] if e["i"] in f2["fields"]]; by_label = {f["text"]: f for f in fields}
                return True
        return False
    for label, value, rule, past in boundary_rules(fields, pay["valid"]):
        values = {**pay["valid"], **(dict(zip(label, value)) if isinstance(label, tuple) else {label: value})}
        fill(values, past=past); phases.append(("invalid", values, rule, submit()))
        if closed() and not reopen(): return phases
    fill(pay["valid"]); phases.append(("valid", pay["valid"], "", submit()))
    if not phases[-1][3]["blocked"] and (not closed() or reopen()):
        fill(pay["valid"]); phases.append(("invalid", pay["valid"], "duplicate: an identical record was just created, a second identical submit must be rejected", submit()))
    return phases


# ---------------- oracles ----------------
def cheap_oracles(el, before, after, http_err, js_err):
    hits = {}
    if http_err: hits["http_error"] = 1.0
    if js_err: hits["js_exception"] = 1.0
    if len(after["text"].strip()) < 20: hits["blank_page"] = 1.0
    href = el.get("href") or ""
    if el["tag"] == "a" and href.startswith("/") and href.split("?")[0] != before["url"].split("?")[0] \
            and after["url"] == before["url"] and after["text"] == before["text"]:
        hits["dead_link"] = 1.0
    return hits


def jev_oracles(oracle_state, extra=None):
    qs = {k: {"type": "noul", "instructions": v} for k, v in ORACLES.items()} | (extra or {})
    return {k: round(v["noul"], 2) for k, v in jev(oracle_state, qs).items()}


# ---------------- expectations (checklist generated once per app; drives both the chooser and the oracle) ----------------
TUNED = Path(__file__).parent / "checklist_prompt.json"   # DSPy/MIPROv2-optimized instruction (+demo), see bench/dspy_checklist.py


def checklist(spec):
    """Once per app: expectations + concrete UI steps to exercise each (Sonnet). Steps are matched to real elements by Jev at run time."""
    head = ("Write the test checklist a meticulous manual QA engineer would verify: 15-30 items. Cover every feature end to end (create -> appears "
            "in the right place with the right data -> edit -> delete), business rules/boundaries implied by the spec, navigation, and feedback. Do not invent features.")
    if TUNED.exists():
        t = json.load(open(TUNED)); head = t["instructions"]
        if t["demos"]: head += "\n\nExample of the expected quality for another spec:\nSpec: " + t["demos"][0]["spec"] + "\nChecklist: " + json.dumps(t["demos"][0]["expectations"], ensure_ascii=False)
    res = claude_json(f"""{head}

Now the spec under test:
{spec}

Each item = ONE observable expected behaviour plus the concrete UI steps to exercise it, starting from the app's home page.
Cover EVERY user role or mode the spec names (the customer/visitor side AND the admin/owner/organizer side); when the app switches roles via a toggle or link, include that switch in the steps.
For every feature the spec names, include one item whose expectation is that the control for it EXISTS on the relevant page (delete/edit buttons, filters, history views), so missing features are caught.
Steps are short imperative UI actions with concrete values, e.g. "click 'Add Product'", "fill 'Price' with '-5'", "select 'Fitness' in 'Category'",
"fill the form and submit", "open the first product". 2-6 steps each; the LAST step is the action whose result proves or breaks the expectation.
Return ONLY JSON: [{{"expect": "<what must be visible after the last step>", "steps": ["...", "..."]}}, ...]""", model="sonnet")
    if isinstance(res, dict): res = next((v for v in res.values() if isinstance(v, list)), [])
    out = []
    for x in res or []:
        if isinstance(x, dict) and isinstance(x.get("expect"), str):
            out.append({"expect": x["expect"], "steps": [t for t in (x.get("steps") or []) if isinstance(t, str)][:6]})
        elif isinstance(x, str): out.append({"expect": x, "steps": []})
    return out[:30]


def step_value(step):
    m = re.search(r"""(?:with|to|=|:)\s*['"“]([^'"”]+)['"”]""", step)
    return m.group(1) if m else None


# ---------------- main ----------------
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", type=int, default=30)
    ap.add_argument("--user", default="problem_user")  # saucedemo: standard_user | problem_user | error_user
    ap.add_argument("--headed", action="store_true")
    ap.add_argument("--base", default=SAUCE)
    ap.add_argument("--goal", default="Explore this e-commerce app like a manual tester hunting for bugs: prefer actions that progress a purchase flow, touch untested features, or submit forms. Avoid logout.")
    ap.add_argument("--out", default="runs")
    a = ap.parse_args(argv)
    global BASE; BASE = a.base.rstrip("/")
    random.seed(hashlib.md5(a.goal.encode()).hexdigest())   # same app -> same random side-steps; re-runs differ only where the app or Jev does
    home = BASE + ("/inventory.html" if BASE == SAUCE else "/")

    t0 = time.time()
    run = Path(a.out) / time.strftime("%Y%m%d-%H%M%S")
    (run / "flagged").mkdir(parents=True)
    log = open(run / "steps.jsonl", "w")
    G = {}                                            # abstract state -> action -> {"n", "ineff"}
    visited, flagged_pairs, findings_raw = {}, set(), []
    scen = checklist(a.goal)                      # [{expect, steps}]
    if scen:                                      # triage: exercise the expectations most likely to be broken first (Jev score, one call)
        risk = jev({"spec": a.goal, "expectations": {f"E{i}": x["expect"] for i, x in enumerate(scen)}},
                   {f"E{i}": {"type": "score", "instructions": f"How likely is expectation `expectations.E{i}` to be VIOLATED in an AI-generated (vibe-coded) implementation of `spec`? Multi-step flows, edits/deletes propagating to lists and totals, business-rule validation and cross-page consistency break most often; static display and simple navigation rarely do.",
                               "criteria": ["almost certainly works", "probably works", "coin flip", "probably broken", "almost certainly broken"]} for i in range(len(scen))})
        scen = [x for _, x in sorted(zip([-risk[f"E{i}"]["score"] for i in range(len(scen))], scen), key=lambda t: t[0])]
    subgoals, done, checked = [x["expect"] for x in scen], [], set()   # done = exercised w/o violation; checked = judged either way
    steps_of = {x["expect"]: x["steps"] for x in scen}
    NEG = [t for t in subgoals if re.search(r"not (be )?(shown|visible|available|usable|displayed|offered|allowed|permitted)|cannot|must not|hidden|is refused|or is refused|only the (poster|author|owner|creator|admin)|only (an? )?(admin|owner|author)", t, re.I) and not re.search(r"\bexists?\b", t, re.I)]   # negative items: absence there is a pass (v14 strict regex; \bno\b matched "No Longer Relevant")
    seen_lines = set()                                  # every screen line seen in the run: a control named by a stalled scenario that never appeared anywhere = missing feature (v14 absence path)
    print(f"    checklist: {len(subgoals)} expectations, {sum(len(x['steps']) for x in scen)} steps")
    E = {f"E{i}": t for i, t in enumerate(subgoals)}
    sg_steps = sg_step_i = sg_budget = streak = 0; streak_path = None; seen_paths = set(); stalled = []; done_tuples = set(); opener = None
    console, failed, http_err, js_err = [], [], [], []

    def record(step, how, action, before, after, probs, hits, extra, page):
        key = (state_sig(before), action)
        if hits and key in flagged_pairs: hits = {}
        if hits: flagged_pairs.add(key)
        rec = {"step": step, "state": key[0], "how": how, "action": action, "from": before["url"], "to": after["url"],
               "oracles": probs, "flags": list(hits), **extra}
        log.write(json.dumps(rec, ensure_ascii=False) + "\n"); log.flush()
        mark = " <-- FLAG " + ",".join(hits) if hits else ""
        print(f'{step:03d} {how:11s} {action[:45]:45s} {before["url"][-22:]:>22s} -> {after["url"][-22:]:<22s}{mark}')
        if hits:
            page.screenshot(path=run / "flagged" / f"{step:03d}.png")
            findings_raw.append({**rec, "evidence": {"action": action, "before": {"url": before["url"], "text": before["text"][:2000]},
                                                     "after": {"url": after["url"], "text": after["text"][:3000]},
                                                     "console_errors": console[:5], "failed_requests": failed[:5], "http_errors": http_err[:5],
                                                     "js_exceptions": js_err[:3], **extra}})

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not a.headed)
        page = browser.new_page()
        page.on("console", lambda m: console.append(m.text[:200]) if m.type == "error" else None)
        page.on("pageerror", lambda e: js_err.append(str(e)[:200]))
        page.on("requestfailed", lambda r: failed.append(r.url[:200]))
        page.on("response", lambda r: http_err.append(f"{r.status} {r.url[:150]}")
                if r.status >= 400 and r.request.resource_type in ("xhr", "fetch", "document") else None)
        if BASE == SAUCE: login(page, a.user)
        else: page.goto(home); page.wait_for_load_state("networkidle")

        step, absent = 0, []
        if absence and BASE != SAUCE:                     # crawl nav/detail/role states once, one step charged per page; absences become deterministic findings
            try:
                pages = absence.crawl(page, home); absent = absence.probe(a.goal + "\n" + "\n".join(subgoals), pages)   # checklist expectations are a second quote source (spec rarely names delete/edit)
                for pg in pages:
                    log.write(json.dumps({"step": step, "state": "", "how": "crawl", "action": f'crawl {pg["url"].replace(BASE, "")}', "from": pg["url"].replace(BASE, ""), "to": pg["url"].replace(BASE, ""), "oracles": {}, "flags": []}) + "\n"); step += 1
                print(f'    absence: {len(pages)} pages crawled ({step} steps charged), {len(absent)} absent: {[x["expected_control"] for x in absent]}')
            except Exception as e: print(f"    absence failed: {str(e)[:120]}")
            page.goto(home); page.wait_for_load_state("networkidle")
        init = snapshot(page); blank = {"url": "", "text": "", "elements": []}
        probs = jev_oracles({"action": "open the app's initial page (fresh load, no interaction yet)", "before": blank, "after": {"url": init["url"], "text": init["text"][:3000]}, "spec": a.goal},
                            {"initial_broken": {"type": "noul", "instructions": "Judging `after.text` (the first page of an app described by `spec`): does it show clearly wrong seed data or rendering, e.g. a chart/summary whose values are all 0 or $0 while lists on the same page hold items, NaN/undefined/null, or totals contradicting listed rows? Answer no for a merely empty app with no data anywhere."}})
        hits = {k: v for k, v in probs.items() if k in ("initial_broken", "broken_content", "inconsistent_state") and v >= FLAG_THRESHOLD}
        record(step, "init", "initial page", blank | {"url": init["url"]}, init, probs, hits, {"value": None, "expectation": None}, page); step += 1
        while step < a.steps:
            if not page.url.startswith(BASE): page.goto(home)
            if BASE == SAUCE and "user-name" in page.content() and page.url.rstrip("/") == BASE: login(page, a.user)
            before = snapshot(page); seen_lines.update(before["text"].splitlines())
            sig = state_sig(before)
            visited[sig] = visited.get(sig, 0) + 1
            mem = G.setdefault(sig, {})

            # --- current target: next expectation not yet exercised, round-robin with patience ---
            pending = [t for t in subgoals if t not in checked]
            if pending and sg_steps >= sg_budget:                       # overran its share: stalled, never retried
                if sg_steps: stalled.append(pending[0]); checked.add(pending[0]); pending.pop(0)
                sg_steps = sg_step_i = 0
                if pending: sg_budget = max(len(steps_of.get(pending[0], [])), (a.steps - step) // len(pending))   # ponytail: floor(remaining/pending) alone is 1 step for 30 items at budget 50; an item at least gets its own scenario length
            subgoal = pending[0] if pending else None
            steps = steps_of.get(subgoal, []) if subgoal else []
            scen_step = steps[sg_step_i] if sg_step_i < len(steps) else None
            final_step = scen_step is not None and sg_step_i == len(steps) - 1

            # --- candidates: primitives + whole-form macros, ranked by graph memory (fresh > useful > any) ---
            cands = [(describe(e), ("el", e)) for e in before["elements"][:MAX_CANDIDATES]]
            cands += [(f'form "{f["name"]}" (fill all {len(f["fields"])} fields and submit)', ("form", f)) for f in before["forms"].values()]
            if not cands:
                page.keyboard.press("Escape"); page.wait_for_timeout(300)
                if not snapshot(page)["elements"]: page.goto(home)
                continue
            path = norm(before["url"].split("?")[0])
            cands = [c for c in cands if (path, c[0]) not in done_tuples or c[1][1].get("tag") in ("input", "textarea")] or cands   # never redo an identical (route, action) unless typed values differ
            fresh = [c for c in cands if c[0] not in mem]
            useful = [c for c in cands if c[0] in mem and not mem[c[0]]["ineff"]]
            pool = fresh or useful or cands
            picked = None
            seen_paths.add(path)
            streak = streak + 1 if path == streak_path else 1; streak_path = path
            if streak > URL_CAP:                                   # trapped on one page: leave via a link to a path never visited
                exits = [c for c in cands if c[1][0] == "el" and (c[1][1].get("href") or "").startswith("/") and norm(c[1][1]["href"].split("?")[0]) not in seen_paths]
                if exits: picked = random.choice(exits); how = "escape"
                else: page.keyboard.press("Escape"); page.goto(home); streak = 0; continue
            if scen_step and not picked:
                wide = [(describe(e), ("el", e)) for e in before["elements"][:120]] + cands[len(cands) - len(before["forms"]):]
                crit = {f"e{i}": c[0] for i, c in enumerate(wide)} | {"none": "no candidate performs this step"}
                ans = jev({"page": before["url"], "visible_text": before["text"][:2500], "scenario_step": scen_step, "expectation": subgoal},
                          {"el": {"type": "choice", "criteria": crit, "instructions": "Which candidate element performs `scenario_step` on this page? Choose none if no candidate does."}})["el"]
                sg_step_i += 1                                  # advance either way: a missing step is skipped, not retried
                best, p_best = max(((k, v) for k, v in ans["probabilities"].items() if k != "none"), key=lambda kv: kv[1], default=("none", 0))
                if best != "none" and p_best >= 0.25:
                    picked = wide[int(best[1:])]; how = f'step({p_best:.2f})'
                elif os.environ.get("MONKEY_DEBUG"):
                    print(f'    step miss: "{scen_step[:60]}" ({ans["confidence"]:.2f}) on {before["url"]}')
            if picked:
                desc, (kind, obj) = picked
            elif not pending and random.random() < EPSILON:              # side-steps only once the queue is empty
                desc, (kind, obj) = random.choice(pool); how = "random"
            else:
                ans = jev({"page": before["url"], "visible_text": before["text"][:2500], "visits_to_this_state": visited[sig],
                           "goal": a.goal, "current_subgoal": subgoal or "explore untested features"},
                          {"next": {"type": "choice", "criteria": {f"e{i}": c[0] for i, c in enumerate(pool)},
                                    "instructions": "Which element should the tester interact with next to make progress toward `current_subgoal` (and the overall `goal`)? Prefer a whole-form action when a form is the way forward."}})["next"]
                desc, (kind, obj) = pool[int(ans["choice"][1:])]; how = f'jev({ans["confidence"]:.2f})'
            mem.setdefault(desc, {"n": 0, "ineff": False}); mem[desc]["n"] += 1
            console.clear(); failed.clear(); http_err.clear(); js_err.clear()
            def judge(st, extra_q, dead_click=False):
                """Which expectation does this step exercise (Jev choice, or the scenario's own on its final step), is it violated (Jev noul), plus generic + extra oracles."""
                exp = subgoal if (final_step and picked) else None
                if E and not exp:
                    rel = jev({k: v for k, v in st.items() if k != "current_subgoal"},
                              {"rel": {"type": "choice", "criteria": E | {"none": "no listed expectation is exercised or checkable from this action and its result"},
                                       "instructions": "Which expectation does this action and its visible result exercise (make checkable), if any?"}})["rel"]
                    if rel["choice"] != "none" and rel["confidence"] >= 0.4: exp = E[rel["choice"]]
                q = dict(extra_q)
                if exp:
                    st = st | {"expectation": exp}
                    q["expectation_violated"] = {"type": "noul", "instructions": "`expectation` states what must be visible after this kind of action. Judging only `before` -> `after` for `action`, is the expectation clearly VIOLATED (the required result did not appear, or something contradicting it appeared)? Answer no if the action does not fully exercise it yet or the result matches."}
                    q["expectation_verified"] = {"type": "noul", "instructions": "Judging only `before` -> `after` for `action`, did the result required by `expectation` clearly APPEAR, so the expectation is now positively confirmed? Answer no if the action merely navigated, opened a form, or changed nothing relevant."}
                probs = jev_oracles(st, q)
                strong = {k for k in probs if k in extra_q or k == "expectation_violated"} | ({"action_ignored"} if dead_click else set())
                hits = {k: v for k, v in probs.items() if k != "expectation_verified" and v >= FLAG_THRESHOLD and (k in strong or probs.get("expectation_violated", 0) >= FLAG_THRESHOLD)}
                if exp:
                    verified = probs.get("expectation_verified", 0) >= 0.6 and st.get("diff", {}).get("changed", True)
                    if verified or "expectation_violated" in hits: checked.add(exp)      # resolved either way; otherwise it stays pending
                    if verified and "expectation_violated" not in hits and exp not in done: done.append(exp)
                return probs, hits, exp

            if kind == "form":
                phases = run_form(page, before, obj, a.goal, opener)
                mem[desc]["ineff"] = True                       # one-shot: same payloads would be replayed
                if not phases: step += 1; continue
                prev = before
                for phase, values, rule, after in phases:
                    st = {"action": f"submitted form {obj['name']} with {phase} values", "submitted_values": values, "violated_rule": rule or None,
                          "before": {"url": prev["url"], "text": prev["text"][:2000]}, "after": {"url": after["url"], "text": after["text"][:3000]}, "diff": diff(prev, after),
                          "console_errors": console[:5], "http_errors": http_err[:5], "current_subgoal": subgoal}
                    q = {"invalid_accepted": {"type": "noul", "instructions": "The submission deliberately violated `violated_rule`. Did the app ACCEPT it anyway (success message, item created/updated, form closed, new data visible) instead of showing a validation error and keeping the form open?"}} if phase == "invalid" else \
                        {"valid_rejected": {"type": "noul", "instructions": "All `submitted_values` were valid and realistic. Did the app REJECT or ignore the submission (validation error shown, form still open unchanged, no success/confirmation, data not appearing) instead of accepting it?"}}
                    if after.get("blocked"):                         # nothing changed at all: browser/app validation swallowed the submit
                        probs, hits, exp = {}, {}, None; st["form_blocked"] = True
                    else:
                        probs, hits, exp = judge(st, q)
                    hits |= cheap_oracles({"tag": "form"}, prev, after, http_err, js_err)
                    record(step, how, f"{desc} [{phase}]", prev, after, probs, hits, {"values": values, "rule": rule, "expectation": exp, "form_blocked": after.get("blocked", False), "diff": st["diff"]}, page)
                    prev = after; step += 1; sg_steps += 1
                done_tuples.add((path, desc))
                continue

            el = obj
            try:
                value = act(page, el, step_value(scen_step) if picked and scen_step else None)
            except Exception as e:
                log.write(json.dumps({"step": step, "action": desc, "error": str(e)[:200]}) + "\n")
                print(f'{step:03d} {how:11s} {desc[:45]:45s} ERR {str(e).splitlines()[0][:50]}'); mem[desc]["ineff"] = True; step += 1; continue
            after = snapshot(page); seen_lines.update(after["text"].splitlines())
            if {f["name"] for f in after["forms"].values()} - {f["name"] for f in before["forms"].values()}: opener = el   # this click opened a form
            if state_sig(after) == sig and after["text"] == before["text"]: mem[desc]["ineff"] = True
            st = {"action": desc, "before": {"url": before["url"], "text": before["text"][:2000]}, "after": {"url": after["url"], "text": after["text"][:3000]}, "diff": diff(before, after),
                  "console_errors": console[:5], "failed_requests": failed[:5], "http_errors": http_err[:5], "current_subgoal": subgoal}
            dead_click = mem[desc]["ineff"] and el["tag"] in ("button", "a")   # code-observed: click changed nothing at all
            probs, hits, exp = judge(st, {}, dead_click)
            hits |= cheap_oracles(el, before, after, http_err, js_err)
            record(step, how, desc, before, after, probs, hits, {"value": value, "expectation": exp, "diff": st["diff"]}, page)
            done_tuples.add((path, desc, value)); step += 1; sg_steps += 1

        # --- absence (v14): a stalled scenario whose click step names a control that never appeared on any screen = the feature is missing (deterministic, no judge) ---
        seen = "\n".join(seen_lines); last = snapshot(page)
        def present(name): return all(re.search(rf"(?<![A-Za-z]){re.escape(w)}(?![A-Za-z])", seen, re.I) for w in re.findall(r"[A-Za-z][A-Za-z-]+", name)) if re.findall(r"[A-Za-z][A-Za-z-]+", name) else True
        reported = {x["expected_control"].casefold() for x in absent}                          # dedupe: one report per control name, none if v9's probe already reported it
        for item in stalled:
            if item in NEG or any(json.loads(x["evidence"])["requirement"] in item for x in absent): continue   # negative items: absence is a pass; v9 probe already fired for this expectation
            names = [n for st_ in steps_of.get(item, []) if re.match(r"\s*(click|press|tap|open)\b", st_, re.I) for n in re.findall(r"""['"‘“]([^'"’”]{1,40})['"’”]""", st_)]
            missing = [n for n in names if not present(n) and n.casefold() not in reported]
            if missing:
                reported.add(missing[0].casefold())
                record(step, "absence", f"searched every screen for a '{missing[0]}' control", last, last, {}, {"expectation_unreachable": 1.0}, {"value": None, "expectation": item, "deterministic": True, "missing_controls": missing}, page); step += 1

        # --- verify by replay: redo each flagged primitive action from its page; forms are stateful, left as reproduced=None ---
        findings, seen = [], set()
        for f in findings_raw:
            key = (f["action"].split(" (")[0].split(" [")[0], f["from"], ",".join(f["flags"]))
            if key in seen: continue
            seen.add(key)
            f = {**f, "id": len(findings), "page": f["from"], "reproduced": None,
                 "count": sum(1 for g in findings_raw if (g["action"].split(" (")[0].split(" [")[0], g["from"], ",".join(g["flags"])) == key)}
            if not f["action"].startswith("form ") and f.get("how") != "absence" and len(findings) < 12:
                try:
                    page.goto(BASE + f["from"]); page.wait_for_load_state("networkidle"); page.wait_for_timeout(400)
                    snap = snapshot(page)
                    el = next(e for e in snap["elements"] if describe(e) == f["action"])
                    console.clear(); failed.clear(); http_err.clear(); js_err.clear()
                    act(page, el, f.get("value")); after = snapshot(page)
                    st = {"action": f["action"], "before": {"url": snap["url"], "text": snap["text"][:2000]}, "after": {"url": after["url"], "text": after["text"][:3000]},
                          "console_errors": console[:5], "failed_requests": failed[:5], "http_errors": http_err[:5]}
                    if f.get("expectation"):
                        st["expectation"] = f["expectation"]
                        probs = jev_oracles(st, {"expectation_violated": {"type": "noul", "instructions": "`expectation` states what must be visible after this kind of action. Judging only `before` -> `after` for `action`, is the expectation clearly VIOLATED?"}})
                    else: probs = jev_oracles(st)
                    again = {k for k, v in probs.items() if v >= FLAG_THRESHOLD} | set(cheap_oracles(el, snap, after, http_err, js_err))
                    f["reproduced"] = bool(again & set(f["flags"]))
                except Exception as e:
                    f["replay_error"] = str(e)[:120]
            f["action"] = key[0]
            findings.append(f)
        absent = list({x["expected_control"].casefold(): x for x in reversed(absent)}.values())[::-1]   # one feature_missing report per control name across pages (first page wins)
        for x in absent:                                  # deterministic: no replay, no Sonnet needed (`report` is the sentence to pass through)
            ev = json.loads(x["evidence"]); url = x["url"].replace(BASE, "")
            findings.append({"id": len(findings), "step": -1, "state": "", "how": "absence", "action": f'absence probe: {x["verb"]}', "page": url, "from": url, "to": url,
                             "oracles": {"feature_missing": x["confidence"]}, "flags": ["feature_missing"], "reproduced": True, "count": 1, "expectation": ev["requirement"],
                             "report": f'On {url} the spec requires "{ev["requirement"]}" but no {x["expected_control"]} control or content exists (looked for {", ".join(ev["missing_terms"])} among {len(ev["controls"])} controls and {len(ev["fields"])} fields).',
                             "evidence": {"action": x["verb"], "before": {"url": url, "text": ""}, "after": {"url": url, "text": ev["text"][:3000]}, "console_errors": [], "failed_requests": [], "http_errors": [], "js_exceptions": [],
                                          "controls": ev["controls"], "fields": ev["fields"], "missing_terms": ev["missing_terms"]}})
        browser.close()

    print(f"\n{a.steps} steps, {len(visited)} distinct states, {len(findings_raw)} flagged, {len(done)}/{len(subgoals)} expectations exercised -> {run}/flagged/")
    for f in findings:
        print(f'  {f["action"][:40]:40s} @ {f["page"][-24:]:24s} -> {",".join(f["flags"])[:35]:35s} x{f["count"]} reproduced={f["reproduced"]}')
    json.dump({"run": str(run), "steps": a.steps, "user": a.user, "states": len(visited), "flagged_steps": len(findings_raw),
               "subgoals_done": done, "stalled": stalled, "expectations": subgoals, "checked": sorted(checked), "secs": round(time.time() - t0, 1), "jev": USAGE | CLAUDE_USAGE, "findings": findings},
              open(run / "findings.json", "w"), indent=1, ensure_ascii=False)
    return run


if __name__ == "__main__":
    main()
