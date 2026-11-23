"""Helpers of `paper/build.sh` (standard library only).

    python3 build_tools.py check DRAFT      # exit 1 if a final build is asked for while author.yaml or a marked line is incomplete
    python3 build_tools.py prepare DRAFT    # build/: the markdown with the author block, style.css, reference.docx (DRAFT header)
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = HERE / "build"
DOCS = ("PREPRINT_v1.md", "SUPPLEMENT_v1.md")
MARK = re.compile(r"\[\[AUTHOR TO COMPLETE[^\]]*\]\]")
FIELDS = ("name", "affiliation", "email")


def author() -> dict[str, str]:
    out = {}
    for line in (HERE / "author.yaml").read_text(encoding="utf-8").splitlines():
        m = re.match(r'^\s*([a-z_]+)\s*:\s*"?(.*?)"?\s*$', line)
        if m and not line.lstrip().startswith("#"):
            out[m.group(1)] = m.group(2).strip()
    return out


def check(draft: bool) -> int:
    a = author()
    empty = [f for f in FIELDS if not a.get(f)]
    marked = [d for d in DOCS if (HERE / d).exists() and MARK.search((HERE / d).read_text(encoding="utf-8"))]
    if (empty or marked) and not draft:
        print(f"refused: author.yaml empty fields {empty}; unfilled marked lines in {marked}. Fill them, or build with --draft.")
        return 1
    if empty or marked:
        print(f"draft build: empty fields {empty}, marked lines in {marked}")
    return 0


CSS = """
@page { size: A4; margin: 18mm 16mm 18mm 16mm; }
body { font-family: "Helvetica Neue", Arial, sans-serif; font-size: 10.5pt; line-height: 1.42; color: #111; max-width: none; margin: 0; }
h1 { font-size: 17pt; line-height: 1.25; margin: 0 0 6pt 0; }
h2 { font-size: 13pt; margin: 14pt 0 4pt 0; break-after: avoid; }
h3 { font-size: 11pt; margin: 10pt 0 3pt 0; break-after: avoid; }
p { margin: 0 0 6pt 0; text-align: left; }
.authors { margin: 4pt 0 12pt 0; font-size: 10.5pt; }
table { border-collapse: collapse; width: 100%; font-size: 8.6pt; margin: 6pt 0 10pt 0; break-inside: auto; }
tr { break-inside: avoid; }
th, td { border: 0.5pt solid #999; padding: 2pt 4pt; vertical-align: top; text-align: left; }
th { background: #eee; }
figure { margin: 8pt 0 10pt 0; break-inside: avoid; text-align: center; }
figure img { max-width: 100%; max-height: 120mm; }
figcaption { font-size: 9pt; text-align: left; margin-top: 3pt; }
code { font-size: 9pt; }
.draftbar { position: fixed; top: -12mm; left: 0; right: 0; text-align: center; color: #b00; font-weight: bold; font-size: 10pt; letter-spacing: 2pt; }
.draftmark { position: fixed; top: 105mm; left: 10mm; font-size: 96pt; color: rgba(190, 0, 0, 0.10); transform: rotate(-30deg); z-index: -1; }
"""


def _docx_reference(draft: bool) -> Path:
    ref = BUILD / "reference.docx"
    subprocess.run(["pandoc", "-o", str(ref), "--print-default-data-file", "reference.docx"], capture_output=True, check=True)
    if not draft:
        return ref
    tmp = BUILD / "reference_draft.docx"
    with zipfile.ZipFile(ref) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            buf = zin.read(item.filename)
            if item.filename == "word/document.xml":
                s = buf.decode("utf-8")
                hdr = '<w:headerReference w:type="default" r:id="rIdDraftHdr"/>'
                if "<w:sectPr" in s:
                    s = re.sub(r"(<w:sectPr[^>]*>)", r"\1" + hdr, s, count=1)
                else:
                    s = s.replace("</w:body>", f"<w:sectPr>{hdr}</w:sectPr></w:body>")
                if 'xmlns:r=' not in s:
                    s = s.replace("<w:document ", '<w:document xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" ', 1)
                buf = s.encode("utf-8")
            elif item.filename == "word/_rels/document.xml.rels":
                s = buf.decode("utf-8").replace("</Relationships>", '<Relationship Id="rIdDraftHdr" Type="http://schemas.openxmlformats.org/'
                                                "officeDocument/2006/relationships/header\" Target=\"header1.xml\"/></Relationships>")
                buf = s.encode("utf-8")
            elif item.filename == "[Content_Types].xml":
                s = buf.decode("utf-8").replace("</Types>", '<Override PartName="/word/header1.xml" ContentType="application/'
                                                "vnd.openxmlformats-officedocument.wordprocessingml.header+xml\"/></Types>")
                buf = s.encode("utf-8")
            zout.writestr(item, buf)
        zout.writestr("word/header1.xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:hdr xmlns:w="http://schemas.openxmlformats.'
                                          'org/wordprocessingml/2006/main"><w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:rPr><w:b/>'
                                          '<w:color w:val="BB0000"/></w:rPr><w:t>DRAFT - not for distribution</w:t></w:r></w:p></w:hdr>')
    return tmp


def prepare(draft: bool) -> None:
    if BUILD.exists():
        shutil.rmtree(BUILD)
    BUILD.mkdir()
    a = author()
    names = a.get("name") or "[author name]"
    aff = a.get("affiliation") or "[affiliation]"
    em = a.get("email") or "[email]"
    for d in DOCS:
        src = (HERE / d).read_text(encoding="utf-8")
        title = re.search(r"^# (.+)$", src, flags=re.M).group(1).strip()
        body = re.sub(r"^# .+\n", "", src, count=1, flags=re.M)
        head = f'---\ntitle: "{title.replace(chr(34), chr(39))}"\n---\n\n'
        block = f'<div class="authors">{names}<br/>{aff}<br/>{em}</div>\n\n'
        if draft:
            block = '<div class="draftbar">DRAFT - not for distribution</div><div class="draftmark">DRAFT</div>\n\n' + block
        (BUILD / d).write_text(head + block + body, encoding="utf-8")
        docx_head = f'---\ntitle: "{title.replace(chr(34), chr(39))}"\nauthor: "{names}, {aff}, {em}"\n---\n\n'
        (BUILD / d.replace(".md", "_docx.md")).write_text(docx_head + (("**DRAFT - not for distribution**\n\n") if draft else "") + body,
                                                          encoding="utf-8")
    (BUILD / "style.css").write_text(CSS, encoding="utf-8")
    _docx_reference(draft)


if __name__ == "__main__":
    cmd, draft = sys.argv[1], sys.argv[2] == "1"
    if cmd == "check":
        raise SystemExit(check(draft))
    prepare(draft)
