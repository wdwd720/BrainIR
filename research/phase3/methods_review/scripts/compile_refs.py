import re, collections, sys
sys.path.insert(0, 'scripts')
exec(open('scripts/extract_refs.py', encoding='utf-8').read().split("def sortkey")[0])
names = {'A': 'Classical system identification and model reduction', 'B': 'Koopman, DMD and sparse identification',
 'C': 'Predictive states, causal states, bisimulation and abstraction refinement', 'D': 'Neural state-space and continuous-time latent models',
 'E': 'Causal representation learning, identifiability and causal abstraction', 'F': 'Population-dynamics latent models and latent-space comparison',
 'G': 'Experiment design, canonical coordinates and evaluation'}
seen = set(); byarea = collections.OrderedDict((a, []) for a in names)
for r in refs:
    k = key(r)
    if k in seen: continue
    seen.add(k); g = groups[k]
    byarea[r['area']].append(g)
lines = []
for a, lst in byarea.items():
    lines.append(f"### R-{a}. {names[a]}\n")
    for g in lst:
        other = sorted(g['areas'] - {a})
        extra = f" (also cited in area {', '.join(other)})" if other else ''
        t = g['text'] if g['tag'] else g['text'] + ' [tag missing in notes; treat as unverified]'
        lines.append(f"- {t}{extra}")
    lines.append('')
open('notes/_refs_compiled.md', 'w', encoding='utf-8').write('\n'.join(lines))
print({a: len(v) for a, v in byarea.items()})
