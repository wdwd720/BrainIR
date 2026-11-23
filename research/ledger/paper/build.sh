#!/bin/bash
# Build PREPRINT_v1.pdf, PREPRINT_v1.docx and SUPPLEMENT_v1.pdf from the markdown and author.yaml (RUN6_PROMPT section 8).
#   paper/build.sh           final files: refuses while author.yaml has an empty field or a marked line is unfilled
#   paper/build.sh --draft   builds anyway, with DRAFT printed on every page
# Tools: pandoc (Homebrew) for HTML and .docx; headless Google Chrome prints the HTML to PDF (no LaTeX needed).
set -euo pipefail
cd "$(dirname "$0")"
DRAFT=0
if [[ "${1:-}" == "--draft" ]]; then DRAFT=1; fi
CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
command -v pandoc >/dev/null || { echo "pandoc not found (brew install pandoc)"; exit 1; }
[[ -x "$CHROME" ]] || { echo "Google Chrome not found at $CHROME (set CHROME=...)"; exit 1; }

python3 build_tools.py check "$DRAFT"
python3 build_tools.py prepare "$DRAFT"
REF=build/reference.docx
if [[ "$DRAFT" == "1" ]]; then REF=build/reference_draft.docx; fi

for DOC in PREPRINT_v1 SUPPLEMENT_v1; do
  pandoc "build/$DOC.md" -s --embed-resources --resource-path=. --css build/style.css -f markdown+pipe_tables+implicit_figures \
    --metadata lang=en -o "build/$DOC.html"
  "$CHROME" --headless=new --disable-gpu --no-pdf-header-footer --run-all-compositor-stages-before-draw --virtual-time-budget=10000 \
    --print-to-pdf="$DOC.pdf" "file://$PWD/build/$DOC.html" >/dev/null 2>&1
  echo "built $DOC.pdf"
done
pandoc build/PREPRINT_v1_docx.md -f markdown+pipe_tables+implicit_figures --resource-path=. --reference-doc "$REF" -o PREPRINT_v1.docx
echo "built PREPRINT_v1.docx"
if [[ "$DRAFT" == "1" ]]; then echo "DRAFT build: DRAFT printed on every page"; fi
