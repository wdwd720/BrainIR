import re, glob, collections
files = sorted(glob.glob('notes/area_*.md'))
refs = []
for f in files:
    area = f.split('area_')[1][0]
    lines = open(f, encoding='utf-8').read().split('\n')
    inref = False; cur = None; method = None
    for ln in lines:
        if ln.startswith('### '): method = ln[4:].strip()
        if ln.startswith('## Area synthesis'): break
        if re.match(r'^- \*\*References:?\*\*', ln):
            inref = True; continue
        if inref:
            if ln.startswith('### ') or ln.startswith('---') or ln.startswith('## ') or re.match(r'^- \*\*', ln):
                inref = False
                if cur: refs.append(cur); cur = None
                continue
            m = re.match(r'^\s{0,4}[-*] (.*)', ln)
            if m and (len(ln) - len(ln.lstrip())) <= 4:
                if cur: refs.append(cur)
                cur = {'area': area, 'text': m.group(1).strip(), 'method': method}
            elif cur and ln.strip():
                cur['text'] += ' ' + ln.strip()
    if cur: refs.append(cur)
def key(r):
    t = r['text']
    m = re.search(r'arxiv\.org/(?:abs|pdf|html)/(\d{4}\.\d{4,5})', t)
    if m: return 'arxiv:' + m.group(1)
    m = re.search(r'arXiv[: ](\d{4}\.\d{4,5})', t)
    if m: return 'arxiv:' + m.group(1)
    m = re.search(r'https?://\S+', t)
    if m: return m.group(0).rstrip('.,;)').lower().rstrip('/')
    return re.sub(r'\W+', '', t.lower())[:60]
rank = {'[read-full]': 4, '[repo/docs]': 3, '[read-abstract]': 2, '[unverified]': 1}
def tagof(t):
    best = None
    for m in re.finditer(r'\[(read-full|read-abstract|repo/docs|unverified)', t):
        k = '[' + m.group(1) + ']'
        if best is None or rank[k] > rank[best]: best = k
    return best
groups = collections.OrderedDict()
for r in refs:
    k = key(r)
    if k not in groups: groups[k] = {'text': r['text'], 'areas': set(), 'tag': tagof(r['text'])}
    g = groups[k]; g['areas'].add(r['area'])
    t = tagof(r['text'])
    if t and (g['tag'] is None or rank[t] > rank[g['tag']]):
        g['text'] = r['text']; g['tag'] = t
def sortkey(g):
    return re.sub(r'[^a-z]', '', g['text'].lower().lstrip('*_"\'[')[:30])
out = sorted(groups.values(), key=sortkey)
cnt = collections.Counter(g['tag'] for g in out)
with open('notes/_refs_compiled.md', 'w', encoding='utf-8') as fh:
    for i, g in enumerate(out, 1):
        fh.write(f"{i}. {g['text']} (areas: {', '.join(sorted(g['areas']))})\n")
print(len(refs), 'raw;', len(out), 'unique;', dict(cnt))
