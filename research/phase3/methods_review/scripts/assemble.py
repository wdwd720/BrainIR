import re, glob
names = {'A': 'Classical system identification, minimal realisation and model reduction', 'B': 'Koopman operator learning, DMD and sparse identification',
 'C': 'Predictive states, causal states, bisimulation and abstraction refinement', 'D': 'Neural state-space and continuous-time latent models',
 'E': 'Causal representation learning, identifiability, invariance and causal abstraction', 'F': 'Population-dynamics latent models and comparing latent spaces',
 'G': 'Experiment design, canonical dynamical coordinates and evaluation of learned dynamics'}
part1, appx = [], []; nentries = 0
for f in sorted(glob.glob('notes/area_*.md')):
    a = f.split('area_')[1][0]
    txt = open(f, encoding='utf-8').read().replace('\r\n', '\n')
    lines = txt.split('\n')
    if lines[0].startswith('# '): lines = lines[1:]
    idx = next(i for i, l in enumerate(lines) if l.startswith('## Area synthesis hints'))
    body, hints = lines[:idx], lines[idx+1:]
    while body and body[-1].strip() in ('', '---'): body.pop()
    body = [('### ' + l[3:]) if l.startswith('## ') else l for l in body]
    nentries += sum(1 for l in body if l.startswith('### ') and not re.match(r'### (Unifying view|Quick map)', l))
    part1.append(f'## {a}. {names[a]}\n\n_Source notes: `{f}`._\n\n' + '\n'.join(body).strip() + '\n')
    hints = [('#### ' + l[4:]) if l.startswith('### ') else l for l in hints]
    appx.append(f'## Appendix {a}. Area synthesis notes: {names[a]}\n\n' + '\n'.join(hints).strip() + '\n')
hdr = open('notes/_header.md', encoding='utf-8').read()
hdr = hdr.replace('Part I has about 110 method entries', f'Part I has {nentries} method entries')
syn = open('notes/_synthesis.md', encoding='utf-8').read()
refs = open('notes/_refs_compiled.md', encoding='utf-8').read()
doc = (hdr.rstrip() + '\n\n---\n\n# Part I. Method entries\n\n' + '\n---\n\n'.join(part1) +
       '\n---\n\n' + syn.rstrip() + '\n\n---\n\n# Part III. References\n\n' +
       'Deduplicated across areas (by arXiv id or URL). Each item keeps the strongest verification tag found. '
       'Items are listed under the area where they first appear; per-entry reference lists in Part I show which method each supports.\n\n'
       + refs.rstrip() + '\n\n---\n\n# Appendix. Detailed per-area synthesis notes\n\n'
       'Condensed in Part II; kept here for the detailed recipes, hyperparameters and area-specific pitfalls.\n\n' + '\n---\n\n'.join(appx))
open('METHODS_REVIEW.md', 'w', encoding='utf-8').write(doc)
print('entries', nentries, 'bytes', len(doc.encode()), 'lines', doc.count('\n'))
