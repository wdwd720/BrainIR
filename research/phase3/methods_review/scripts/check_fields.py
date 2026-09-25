import re

t = open('METHODS_REVIEW.md', encoding='utf-8').read()
p1 = t.split('# Part I. Method entries')[1].split('# Part II. Synthesis')[0]
fields = ['Core idea', 'Assumptions', 'Identifiab', 'Intervention support', 'Nonlinear capacity', 'Interpretab',
          'Scaling', 'Failure modes', 'Relevance', 'Open-source', 'From-scratch', 'References']
bad = n = 0
for e in re.split(r'\n(?=### )', p1):
    if not e.startswith('### ') or re.match(r'### (Unifying view|Quick map)', e):
        continue
    n += 1
    miss = [f for f in fields if not re.search(r'\*\*' + f, e)]
    if miss:
        bad += 1
        print(e.split('\n')[0][:80], miss)
print('entries:', n, 'with missing fields:', bad)
