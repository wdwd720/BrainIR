"""Count the printed pages of research/ledger/BRIEF.md (run 4; RUN4_PROMPT section 8: "Two pages").

The page is fixed here and was fixed before the two-page rewrite of the brief (LOG L156): US Letter, 1-inch margins, 11 pt
serif body (line height 1.25), 10 pt table and caption, the figure at the full text width (6.5 in). The Markdown is converted to
HTML by the small converter below (headings, paragraphs, bullet lists, tables, one image with its caption, bold, italics and code
spans: the syntax the brief uses) and printed to PDF by headless Chrome, whose path is taken from the CHROME environment variable.
The page count is read from the PDF's page tree.

    CHROME=<path to the Chrome binary> uv run --project ledger --no-sync python ledger/scripts/posthoc/brief_pages_v4.py \
        research/ledger/BRIEF.md <out.pdf>
"""
from __future__ import annotations

import html
import os
import re
import subprocess
import sys
from pathlib import Path

CSS = """
@page { size: Letter; margin: 1in; }
body { font-family: 'Times New Roman', Times, serif; font-size: 11pt; line-height: 1.25; margin: 0; color: #000; }
h1 { font-size: 14pt; margin: 0 0 6pt 0; line-height: 1.2; }
h2 { font-size: 12pt; margin: 10pt 0 4pt 0; }
p { margin: 0 0 6pt 0; text-align: left; }
ul { margin: 0 0 6pt 0; padding-left: 16pt; }
li { margin: 0 0 3pt 0; }
code { font-family: Menlo, monospace; font-size: 9.5pt; }
table { border-collapse: collapse; font-size: 10pt; line-height: 1.15; margin: 4pt 0 8pt 0; width: 100%; }
th, td { border-bottom: 0.5pt solid #999; padding: 1.5pt 4pt; text-align: left; vertical-align: top; }
th { border-bottom: 1pt solid #000; }
figure { margin: 6pt 0 0 0; }
img { width: 100%; display: block; }
figcaption { font-size: 10pt; line-height: 1.2; margin-top: 3pt; }
"""


def inline(s: str) -> str:
    s = html.escape(s, quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    return re.sub(r"(?<![*\w])\*([^*]+)\*(?![*\w])", r"<em>\1</em>", s)


def to_html(md: str, base: Path) -> str:
    out = []
    for blk in re.split(r"\n\s*\n", md.strip()):
        ls = blk.split("\n")
        if ls[0].startswith("# "):
            out.append(f"<h1>{inline(ls[0][2:])}</h1>")
        elif ls[0].startswith("## "):
            out.append(f"<h2>{inline(ls[0][3:])}</h2>")
        elif ls[0].startswith("|"):
            rows = [[c.strip() for c in l.strip().strip("|").split("|")] for l in ls if not re.match(r"^\|[-| ]+\|$", l)]
            t = ["<table><tr>" + "".join(f"<th>{inline(c)}</th>" for c in rows[0]) + "</tr>"]
            t += ["<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in rows[1:]]
            out.append("".join(t) + "</table>")
        elif ls[0].startswith("!["):
            m = re.match(r"!\[([^\]]*)\]\(([^)]+)\)", ls[0])
            src = (base / m.group(2)).resolve().as_uri()
            cap = " ".join(l.strip() for l in ls[1:])
            out.append(f'<figure><img src="{src}" alt="{html.escape(m.group(1))}"><figcaption>{inline(cap)}</figcaption></figure>')
        elif ls[0].startswith("- "):
            items: list[str] = []
            cur: list[str] = []
            for l in ls:
                if l.startswith("- "):
                    if cur:
                        items.append(" ".join(cur))
                    cur = [l[2:].strip()]
                else:
                    cur.append(l.strip())
            items.append(" ".join(cur))
            out.append("<ul>" + "".join(f"<li>{inline(i)}</li>" for i in items) + "</ul>")
        else:
            out.append(f"<p>{inline(' '.join(l.strip() for l in ls))}</p>")
    return f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{''.join(out)}</body></html>"


def main() -> None:
    chrome = os.environ.get("CHROME")
    if not chrome:
        raise SystemExit("set CHROME to the path of the Chrome binary")
    md_path, pdf_path = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    html_path = pdf_path.with_suffix(".html")
    html_path.write_text(to_html(md_path.read_text(), md_path.parent))
    subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--print-to-pdf-no-header",
                    "--allow-file-access-from-files", f"--print-to-pdf={pdf_path}", html_path.as_uri()],
                   check=True, capture_output=True, timeout=120)
    data = pdf_path.read_bytes()
    counts = [int(c) for c in re.findall(rb"/Type\s*/Pages\b[^>]*?/Count\s+(\d+)", data)]
    counts += [int(c) for c in re.findall(rb"/Count\s+(\d+)[^>]*?/Type\s*/Pages\b", data)]
    images = len(re.findall(rb"/Subtype\s*/Image", data))
    prose = " ".join(l for l in md_path.read_text().splitlines() if not l.startswith("|"))
    print(f"pages: {max(counts) if counts else '?'}; embedded images: {images}; prose words: {len(prose.split())}")


if __name__ == "__main__":
    main()
