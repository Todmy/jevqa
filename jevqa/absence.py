"""Bounded UI crawl and spec-grounded absence probes; --self-test runs offline checks."""
import argparse, json, os, re
from .llm import claude_json
from urllib.parse import urlparse
import requests
from playwright.sync_api import Error, sync_playwright

JEV_URL = "https://api.typesafe.ai/v1/systemone"
CONTROLS = 'a,button,[role=button],[role=tab],[role=switch],[role=combobox],[role=menuitem]'

def _snapshot(page):
    return page.evaluate("""sel => {
      const visible = e => !!(e.getClientRects().length && getComputedStyle(e).visibility !== 'hidden');
      const label = e => ((e.labels?.[0]?.innerText) || e.getAttribute('aria-label') || e.innerText || e.placeholder || e.title || e.name || '').trim();
      return {url:location.href, text:document.body.innerText,
        controls:[...document.querySelectorAll(sel)].filter(visible).map(label).filter(Boolean),
        fields:[...document.querySelectorAll('input:not([type=hidden]),select,textarea')].filter(visible).map(label).filter(Boolean)};
    }""", CONTROLS)

def crawl(page, base, max_pages=8):
    """Visit same-origin nav links, first detail, and role/mode states (including same URL)."""
    origin = urlparse(base)[:2]
    queue, visited, pages = [base], set(), []
    def capture():
        snap = _snapshot(page)
        if snap not in pages and len(pages) < max_pages: pages.append(snap)
        links = page.locator('nav a[href],header a[href],[role=navigation] a[href],main a[href]').evaluate_all('(els) => els.map(e => e.href)')
        for link in links:
            link = link.split('#')[0]
            if urlparse(link)[:2] == origin and link not in visited and link not in queue: queue.append(link)
    while queue and len(pages) < max_pages:
        url = queue.pop(0)
        if url in visited: continue
        visited.add(url)
        page.goto(url, wait_until='domcontentloaded', timeout=15000); page.wait_for_timeout(400)
        capture()
        actions = page.locator(CONTROLS).filter(has_text=re.compile(r'^(switch|view as|.*mode\b)|^(owner|traveler|organizer|visitor|employer|seeker|admin)$', re.I))
        names = actions.all_text_contents() + page.get_by_role('tab').all_text_contents()
        detail = page.locator('article a[href],[class*=card] a[href],a[href]').filter(has_text=re.compile(r'details|view|read more', re.I)).first
        if not detail.count(): detail = page.get_by_role('button', name=re.compile(r'^\d+ comments?$|view details|read more', re.I)).first
        for name in [None] + list(dict.fromkeys(n.strip() for n in names if n.strip())):
            if len(pages) >= max_pages: break
            try:
                target = detail if name is None else page.locator(CONTROLS).filter(has_text=re.compile('^' + re.escape(name) + '$')).first
                if not target.count(): continue
                href = target.get_attribute('href')
                if href and not href.startswith(('/', '#')) and urlparse(href)[:2] != origin: continue
                target.click(timeout=1500); page.wait_for_timeout(300); capture()
            except Error:
                pass  # ponytail: one attempt per target; failed interactions need a deeper crawler.
            finally:
                page.goto(url, wait_until='domcontentloaded', timeout=15000); page.wait_for_timeout(200)
    return pages

def _plan(spec, pages):
    prompt = f'''Derive absence probes from this specification, NOT from controls already present.
SPEC: {spec}
PAGES: {json.dumps(pages, ensure_ascii=False)}
Return ONLY a JSON list of {{page, verb, expected_control, kind, match_terms, source_quote}}.
page is the zero-based PAGES index (states can share URLs). kind is control or content.
source_quote MUST be an exact spec excerpt requiring the feature. No inferred CRUD or extra filters.
Include missing features. Split alternative statuses and filter dimensions into separate probes.
A reopened state does not prove a different status exists. An authenticated page need not show signup.
Control match_terms are literal synonyms, excluding generic words like button or filter.
For concrete content use kind=content and match_terms with a narrowly scoped Python regex proving
that content (e.g. currency plus numeric amount for an actual price, not a dollar tier alone).
Only target relevant states. Skip requirements needing an action result not available in this crawl.'''
    plan = claude_json(prompt, model='sonnet')
    if not isinstance(plan, list): raise ValueError('Sonnet must return a list')
    for p in plan:
        if not isinstance(p, dict) or not all(k in p for k in ('page','verb','expected_control','kind','match_terms','source_quote')): raise ValueError('Invalid probe schema')
        if type(p['page']) is not int or not 0 <= p['page'] < len(pages): raise ValueError('Invalid page index')
        if p['kind'] not in ('control', 'content') or not isinstance(p['match_terms'], list) or not p['match_terms']: raise ValueError('Invalid probe kind/terms')
        if not all(isinstance(x, str) and x.strip() for x in [p['verb'], p['expected_control'], p['source_quote'], *p['match_terms']]): raise ValueError('Empty probe text')
    return [p for p in plan if p['source_quote'] in spec]

def _missing(p, page):
    if p['kind'] == 'content': return not any(re.search(t, page['text'], re.I) for t in p['match_terms'])
    return not any(re.search(r'(?<!\w)' + re.escape(t) + r'(?!\w)', label, re.I)
                   for t in p['match_terms'] for label in page['controls'] + page['fields'])

def probe(spec, pages):
    """One Sonnet plan, deterministic absence checks, one Jev question per candidate."""
    if not pages: raise ValueError('No pages crawled; absence cannot be established')
    plan, findings, seen = _plan(spec, pages), [], set()
    for p in plan:
        page = pages[p['page']]
        key = (p['page'], p['expected_control'].casefold())
        if key in seen or not _missing(p, page): continue
        seen.add(key)
        response = requests.post(JEV_URL, headers={'Authorization': f"Bearer {os.environ['TYPESAFE_API_KEY']}"},
            json={'model': 'jev-latest', 'state': {'requirement': p['source_quote'], 'expected_control': p['expected_control'], **page},
                  'questions': {'feature_missing': {'type':'noul', 'instructions':
                    'Is the required control/content absent in this captured state? Allow equivalent labels. '
                    'Do not infer absence from an unperformed action, unavailable role or closed dialog.'}}}, timeout=30)
        response.raise_for_status()
        score = float(response.json()['answers']['feature_missing']['noul'])
        if not 0 <= score <= 1: raise ValueError('Invalid Jev confidence')
        if score >= .6:   # ponytail: 0.61 = gold 07-16 (No Longer Relevant); recalibrate if fp rises
            findings.append({'url':page['url'], 'verb':p['verb'], 'expected_control':p['expected_control'],
                'evidence':json.dumps({'page':p['page'], 'requirement':p['source_quote'], 'missing_terms':p['match_terms'],
                                       'controls':page['controls'], 'fields':page['fields'], 'text':page['text']}, ensure_ascii=False),
                'confidence':round(score, 2)})
    return findings

def _self_test():
    page = {'text':'Price $$$', 'controls':['Reopen', 'Credit'], 'fields':['Search posts...']}
    p = {'kind':'control', 'match_terms':['Edit']}
    assert _missing(p, page)  # Credit must not match Edit.
    assert not _missing({**p, 'match_terms':['Search']}, page)
    assert _missing({**p, 'match_terms':['No Longer Relevant']}, page)
    p = {'kind':'content', 'match_terms':[r'\$\s*\d+']}
    assert _missing(p, page)
    assert not _missing(p, {**page, 'text':'Price $120'})
    print('absence self-test: PASS')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base'); parser.add_argument('--goal'); parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test: return _self_test()
    if not args.base or not args.goal: parser.error('--base and --goal are required')
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try: findings = probe(args.goal, crawl(browser.new_page(), args.base))
        finally: browser.close()
    print(json.dumps(findings, ensure_ascii=False))


