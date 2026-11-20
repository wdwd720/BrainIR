"""Mechanical source downloader for labels v2 (ledger run 2): RUN2_PROMPT.md section 7 "Sources", PREREG_v2.md L7.

No language model is in the loop. For every DOI of a registry the script fetches what open-access services offer and converts
it into plain files that a blind labeler session can read from its room:

    uv run --project ledger --no-sync --with pymupdf==1.25.5 --with openpyxl==3.1.5 --with xlrd==2.0.1 \
        python ledger/scripts/labels2_download.py --registry REGISTRY.csv --out OUT_DIR --manifest MANIFEST.json \
        [--only DOI ...] [--log LOG] [--force]

REGISTRY.csv has a `doi` column and optional `slug` and `title` columns. The default slug is the DOI in lower case with every
run of characters other than [a-z0-9-] replaced by `_` (10.7554/eLife.34275 -> 10_7554_elife_34275). Unsafe slugs, and two
DOIs with the same slug, stop the run before anything is downloaded.

OUT_DIR/<slug>/ receives
    text.txt      the full text as plain text: title, abstracts, sections, figure captions (with the image file name), table
                  text (tab-separated rows), supplementary-file captions (with the local file names), references. Its first
                  line is `ABSTRACT ONLY` when only an abstract was found, `UNREACHABLE` when not even that. It ends with an
                  index of the folder's files.
    meta.json     doi, slug, title, year, status (full_text | abstract_only | unreachable), routes_tried, errors, files
                  (relative path, bytes, sha256), skipped files (videos, oversized files), the numbers behind the status
                  (`fulltext`), and per-PDF, per-sheet and per-archive details.
    article.pdf   the article PDF, when one was obtained; fulltext.xml: the JATS XML that text.txt was made from.
    figures/      figure images (.jpg / .png; GIF / TIFF converted to PNG with PyMuPDF). When an article has no separate
                  figure files, the raster images embedded in article.pdf.
    supp/         supplementary files. Spreadsheets are kept and also written as one CSV per sheet (<file>__<sheet>.csv);
                  Word files and PDFs are kept and also written as .txt; archives are expanded into supp/<archive name>/
                  (the archive itself is recorded in meta.json, not kept); other binary files are kept up to --max-keep-mb.
                  supp/article.txt is the text of article.pdf when text.txt was made from XML.
    pages/        page images <pdfname>_p<NNN>.png of every PDF (article.pdf -> article_p001.png, ...).
OUT_DIR/.raw/ is the download cache: a re-run reuses every file already fetched, so an interrupted or throttled DOI resumes
where it stopped. OUT_DIR/.partial/ holds a DOI while it is processed. Neither belongs in a room.

Routes, in order. Each attempt is recorded in meta.json `routes_tried`, each failure in `errors` and in the log.
  1 europepmc_search    Europe PMC REST search by DOI: title, year, abstract, PMCID, open-access flags, preprint (PPR) records.
  2 europepmc_fulltext  Europe PMC full-text XML of the PMCID (JATS), converted to text.
    pmc_cloud           The PMC open-access article package. The PMC OA Web Service (oa.fcgi) and its .tar.gz packages were
                        retired in August 2026 (NLM Technical Bulletin, Jan-Feb 2026). Its replacement, the PMC Cloud Service
                        bucket `pmc-oa-opendata`, is read anonymously over HTTPS: the same package files one by one, with
                        MD5s (verified). Figures, supplementary files and the PDF, plus its XML when Europe PMC's failed.
  3 biorxiv             bioRxiv / medRxiv (DOI prefixes 10.1101/ and 10.64898/): api.biorxiv.org details -> latest version ->
                        JATS XML, figure images (<Fn>.large.jpg), supplementary files (DCn/embed/media-n.ext) and the PDF.
  4 europepmc_preprint  Europe PMC full text of a preprint record (PPR...) when Europe PMC holds one and nothing gave text.
  5 elife               eLife (10.7554/eLife.*) when the routes above gave no text, or neither a PDF nor figures: the eLife
                        API -> article XML, PDF, figure images (IIIF) and supplementary files from cdn.elifesciences.org.
  6 crossref            Crossref metadata (title, year, abstract, licences) when still missing, and, when there is still no
                        text, open full-text PDF links from Crossref and Europe PMC (publisher open-access copies).
Never contacted: GitHub, Zenodo and other code hosts, doi.org (the resolver can land anywhere), any shadow library. Every
request and every redirect hop is checked against that denylist, and a DOI of a banned host (Zenodo, 10.5281/) is marked
unreachable without a single request.

Status rule (its numbers are recorded in meta.json `fulltext`): full_text if the XML body has >= 3 paragraphs and >= 1500
characters, or article.pdf yields >= 6000 characters of text over >= 2 pages; else abstract_only if an abstract was found;
else unreachable. A preprint and its journal version are different DOIs: a route never fetches another version.

Politeness: one request at a time, at most --max-rps requests per second overall, at least 3 s between requests to
www.biorxiv.org / www.medrxiv.org, exponential back-off on HTTP 429 / 5xx and network errors that honours Retry-After (up to
--max-wait), --retries retries, connect and read timeouts. Videos and audio files are never downloaded.

Re-runs are incremental: a DOI whose meta.json is present, from the same major script version, with every listed file intact
and no transient (retryable) error, is skipped unless --force. MANIFEST.json maps every registry DOI that has an output folder
to {slug, status, n_files, files: {relpath: sha256}} (meta.json included), records the UTC time and the script version, and
is rewritten atomically after each DOI.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import email.utils
import gzip
import hashlib
import html
import html.entities
import json
import logging
import math
import os
import random
import re
import shutil
import sys
import tarfile
import time
import unicodedata
import warnings
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import quote, unquote, urljoin, urlsplit

import requests

try:
    import pymupdf
except ImportError:  # older PyMuPDF releases only expose the `fitz` name
    try:
        import fitz as pymupdf
    except ImportError:
        pymupdf = None
try:
    import openpyxl
except ImportError:
    openpyxl = None
try:
    import xlrd  # optional: legacy .xls workbooks
except ImportError:
    xlrd = None

SCRIPT_VERSION = "1.0.0"
USER_AGENT = "brainir-ledger-downloader/1.0"
TIMEOUT = (20, 120)  # connect, read (seconds)
ROUTES = ("europepmc_search", "europepmc_fulltext", "pmc_cloud", "biorxiv", "europepmc_preprint", "elife", "crossref")

EPMC_REST = "https://www.ebi.ac.uk/europepmc/webservices/rest"
PMC_BUCKET = "https://pmc-oa-opendata.s3.amazonaws.com"
BIORXIV_API = "https://api.biorxiv.org/details"
ELIFE_API = "https://api.elifesciences.org/articles"
ELIFE_CDN = "https://cdn.elifesciences.org/articles"
ELIFE_IIIF = "https://iiif.elifesciences.org/lax"
CROSSREF_API = "https://api.crossref.org/works"

BANNED_HOSTS = (
    "github.com", "githubusercontent.com", "github.io", "githubassets.com", "githubapp.com", "ghcr.io", "git.io",
    "zenodo.org", "jsdelivr.net", "jsdelivr.com", "nbviewer.org", "nbviewer.jupyter.org", "githack.com", "statically.io",
    "gitee.com", "gitee.io", "gitlab.com", "gitlab.io", "bitbucket.org", "codeberg.org", "sourceforge.net",
    "doi.org",
)
SHADOW_RE = re.compile(r"sci-?hub|libgen|library\.lol|z-?lib|annas-archive|booksc\.|b-ok\.", re.IGNORECASE)
KEY_REQUIRED_HOSTS = ("api.elsevier.com", "api.wiley.com")  # Crossref text-mining links that need an API key
BANNED_DOI_PREFIXES = ("10.5281/",)  # Zenodo
RXIV_PREFIXES = ("10.1101/", "10.64898/")
HOST_GAPS = {"www.biorxiv.org": 3.0, "www.medrxiv.org": 3.0, "api.biorxiv.org": 1.0}  # seconds between requests to a host

VIDEO_EXT = {".mp4", ".m4v", ".mov", ".avi", ".wmv", ".mkv", ".webm", ".ogv", ".mpg", ".mpeg", ".flv", ".3gp", ".mts",
             ".m2ts", ".vob", ".qt", ".swf"}
AUDIO_EXT = {".wav", ".mp3", ".aac", ".flac", ".m4a", ".aif", ".aiff", ".oga", ".wma"}
MEDIA_EXT = VIDEO_EXT | AUDIO_EXT
IMG_RANK = {".jpg": 0, ".jpeg": 0, ".png": 1, ".tif": 2, ".tiff": 2, ".gif": 3, ".bmp": 4, ".webp": 5}
IMAGE_EXT = set(IMG_RANK)
SHEET_EXT = {".xlsx", ".xlsm", ".xltx", ".xltm"}
TEXT_EXT = {".txt", ".csv", ".tsv", ".tab", ".md", ".json", ".xml", ".html", ".htm", ".py", ".m", ".r", ".ipynb", ".tex",
            ".rtf", ".yaml", ".yml", ".log", ".fasta", ".fa", ".gb", ".gff", ".bed", ".sh", ".c", ".cpp", ".h", ".jl",
            ".java", ".swc", ".ini", ".cfg"}
ARCHIVE_SUFFIXES = (".tar.gz", ".tar.bz2", ".tar.xz", ".tgz", ".tbz2", ".txz", ".tar", ".zip")

XL_HREF = "{http://www.w3.org/1999/xlink}href"
HW_ID = "{http://schema.highwire.org/Journal}id"
MIN_XML_PARAGRAPHS, MIN_XML_CHARS = 3, 1500
MIN_PDF_CHARS, MIN_PDF_PAGES = 6000, 2
STATUS_RULE = (f"full_text if the XML body has >= {MIN_XML_PARAGRAPHS} paragraphs and >= {MIN_XML_CHARS} characters, or "
               f"article.pdf yields >= {MIN_PDF_CHARS} characters of text over >= {MIN_PDF_PAGES} pages; else abstract_only "
               "if an abstract was found; else unreachable")

log = logging.getLogger("labels2_download")


# ----------------------------------------------------------------------------------------------------------------- helpers
def utc_now() -> str:
    return dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def norm_ws(s) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def strip_tags(s) -> str:
    """HTML / JATS fragment (Europe PMC abstractText, Crossref abstract) -> plain text, one line per block."""
    s = re.sub(r"<\s*/?\s*(?:h\d|p|br|div|li|jats:p|jats:title|jats:sec|title|sec)\b[^>]*>", "\n", s or "", flags=re.IGNORECASE)
    s = html.unescape(re.sub(r"<[^>]+>", "", s))
    return "\n".join(x for x in (norm_ws(line) for line in s.splitlines()) if x)


def safe_name(name: str, maxlen: int = 150) -> str:
    name = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode()
    s = re.sub(r"_+", "_", re.sub(r"[^A-Za-z0-9._-]+", "_", name)).strip("._ ") or "file"
    if len(s) > maxlen:
        stem, dot, ext = s.rpartition(".")
        s = stem[: maxlen - len(ext) - 1] + "." + ext if dot and 0 < len(ext) <= 8 else s[:maxlen]
    return s


def ext_of(name: str) -> str:
    return PurePosixPath(name or "").suffix.lower()


def stem_of(name: str) -> str:
    n = PurePosixPath(name or "").name
    s = PurePosixPath(n).suffix
    return n[: -len(s)] if s else n


def base_of(href: str) -> str:
    return PurePosixPath((href or "").replace("\\", "/")).name


def href_key(href: str) -> str:
    """Lookup key of a figure: lower-case file name without an image extension (XML hrefs often have none)."""
    n = base_of(href).lower()
    return n[: -len(ext_of(n))] if ext_of(n) in IMAGE_EXT else n


def is_archive(name: str) -> bool:
    return name.lower().endswith(ARCHIVE_SUFFIXES)


def archive_stem(name: str) -> str:
    low = name.lower()
    for suf in ARCHIVE_SUFFIXES:
        if low.endswith(suf):
            return name[: -len(suf)] or "archive"
    return name


def safe_parts(member: str) -> list[str]:
    parts = [p for p in member.replace("\\", "/").split("/") if p not in ("", ".", "..")]
    return [safe_name(p, 100) for p in parts][-8:]


def human(n) -> str:
    if n is None:
        return "size unknown"
    return f"{n / 1e6:.1f} MB" if n >= 1e5 else f"{max(n, 1) / 1e3:.0f} kB"


def image_kind(head: bytes) -> str | None:
    if head[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if head[:4] in (b"II*\x00", b"MM\x00*"):
        return "tiff"
    if head[:2] == b"BM":
        return "bmp"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    return None


HTML_RE = re.compile(rb"^\s*(?:<!--.*?-->\s*)*(?:<!doctype\s+html|<html|<head|<body)", re.IGNORECASE | re.DOTALL)


def sniff(path: Path, expect: str) -> tuple[bool, str]:
    """Check the bytes, not the HTTP status: paywalls and bot walls answer 200 with an HTML page."""
    with open(path, "rb") as f:
        head = f.read(4096)
    is_html = bool(HTML_RE.match(head.lstrip(b"\xef\xbb\xbf")))
    what = "HTML page" if is_html else repr(head[:24])
    if expect == "pdf":
        return b"%PDF" in head[:1024], what
    if expect == "image":
        return image_kind(head) is not None, what
    if expect == "xml":
        return head.lstrip(b"\xef\xbb\xbf \t\r\n").startswith(b"<") and not is_html, what
    if expect == "nothtml":
        return not is_html or ext_of(path.name) in (".html", ".htm"), what
    return True, what


def looks_like_text(path: Path) -> bool:
    with open(path, "rb") as f:
        head = f.read(8192)
    if not head or b"\x00" in head:
        return False
    try:
        head.decode("utf-8")
    except UnicodeDecodeError as e:
        return e.start > len(head) - 4  # a multi-byte character cut at the end of the sample
    return True


class TooLarge(Exception):
    pass


def copy_capped(fi, fo, cap: int) -> int:
    n = 0
    for chunk in iter(lambda: fi.read(1 << 20), b""):
        n += len(chunk)
        if n > cap:
            raise TooLarge(f"more than {cap} bytes")
        fo.write(chunk)
    return n


def cell_str(v) -> str:
    if isinstance(v, (dt.datetime, dt.date, dt.time)):
        return v.isoformat()
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    return str(v)


def norm_doi(raw: str) -> str:
    s = (raw or "").strip()
    s = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", s, flags=re.IGNORECASE).strip()
    return unquote(s) if "%2f" in s.lower() else s


def slug_from_doi(doi: str) -> str:
    s = re.sub(r"[^a-z0-9-]+", "_", doi.lower()).strip("_")
    return s if len(s) <= 120 else s[:100] + "_" + hashlib.sha1(doi.lower().encode()).hexdigest()[:10]


# ------------------------------------------------------------------------------------------------------------------- HTTP
class FetchError(Exception):
    def __init__(self, url: str | None, msg: str, status: int | None = None, transient: bool = False):
        super().__init__(f"{msg} ({url})")
        self.url, self.msg, self.status, self.transient = url, msg, status, transient


def banned_reason(url: str) -> str | None:
    p = urlsplit(url)
    if p.scheme not in ("http", "https"):
        return f"scheme {p.scheme!r} not allowed"
    host = (p.hostname or "").lower().rstrip(".")
    for b in BANNED_HOSTS:
        if host == b or host.endswith("." + b):
            return f"banned host {b}"
    if SHADOW_RE.search(host):
        return "shadow library"
    return None


class Http:
    """One request at a time; global and per-host spacing; manual redirects (every hop is checked); retries with back-off."""

    RETRY_STATUS = frozenset({429, 502, 503, 504})

    def __init__(self, max_rps: float, attempts: int, max_wait: float):
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": USER_AGENT})
        self.gap = 1.0 / max_rps
        self.attempts = max(1, attempts)
        self.max_wait = max_wait
        self.t_last = -1e9
        self.t_host: dict[str, float] = {}
        self.n = 0  # requests sent, redirect hops included

    def _throttle(self, host: str) -> None:
        now = time.monotonic()
        wait = max(self.t_last + self.gap, self.t_host.get(host, -1e9) + HOST_GAPS.get(host, 0.0)) - now
        if wait > 0:
            time.sleep(wait)
        self.t_last = self.t_host[host] = time.monotonic()

    @staticmethod
    def _backoff(attempt: int) -> float:
        return min(60.0, 2.0 * 2 ** (attempt - 1)) + random.uniform(0, 1)

    @staticmethod
    def _retry_after(r: requests.Response) -> float | None:
        v = (r.headers.get("retry-after") or "").strip()
        if not v:
            return None
        try:
            return max(0.0, float(v)) + 1.0
        except ValueError:
            pass
        try:
            when = email.utils.parsedate_to_datetime(v)
            return max(0.0, (when - dt.datetime.now(dt.UTC)).total_seconds()) + 1.0
        except (TypeError, ValueError):
            return None

    def _send(self, url: str, headers: dict | None) -> requests.Response:
        for _hop in range(10):
            why = banned_reason(url)
            if why:
                raise FetchError(url, f"not fetched: {why}")
            self._throttle((urlsplit(url).hostname or "").lower())
            t0 = time.monotonic()
            r = self.s.get(url, headers=headers, stream=True, timeout=TIMEOUT, allow_redirects=False)
            self.n += 1
            log.debug("GET %s -> %d (%.1f s)", url, r.status_code, time.monotonic() - t0)
            if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("location"):
                nxt = urljoin(url, r.headers["location"])
                r.close()
                url = nxt
                continue
            r.final_url = url
            return r
        raise FetchError(url, "too many redirects")

    def get(self, url: str, headers: dict | None = None) -> requests.Response:
        """Open a streamed GET whose status is < 400, retrying 429 / 5xx / network errors."""
        for attempt in range(1, self.attempts + 1):
            try:
                r = self._send(url, headers)
            except FetchError:
                raise
            except requests.RequestException as e:
                if attempt < self.attempts:
                    d = self._backoff(attempt)
                    log.warning("%s on %s; retry %d/%d in %.0f s", type(e).__name__, url, attempt, self.attempts - 1, d)
                    time.sleep(d)
                    continue
                raise FetchError(url, f"{type(e).__name__}: {e}", transient=True) from e
            code = r.status_code
            if code in self.RETRY_STATUS or (code == 500 and attempt == 1):
                delay = self._retry_after(r)
                delay = self._backoff(attempt) if delay is None else delay
                r.close()
                if delay > self.max_wait:
                    raise FetchError(url, f"HTTP {code}; Retry-After {delay:.0f} s exceeds --max-wait", code, transient=True)
                if attempt < self.attempts:
                    log.warning("HTTP %d on %s; retry %d/%d in %.0f s", code, url, attempt, self.attempts - 1, delay)
                    time.sleep(delay)
                    continue
                raise FetchError(url, f"HTTP {code} after {attempt} attempts", code, transient=True)
            if code >= 400:
                r.close()
                raise FetchError(url, f"HTTP {code}", code, transient=code in (408, 500))
            return r
        raise FetchError(url, "no attempt made", transient=True)

    def fetch_bytes(self, url: str, params: dict | None = None, headers: dict | None = None, cap: int = 64 << 20) -> bytes:
        if params:
            url = requests.Request("GET", url, params=params).prepare().url
        for attempt in range(1, self.attempts + 1):
            r = self.get(url, headers)
            try:
                buf = bytearray()
                for chunk in r.iter_content(1 << 16):
                    buf += chunk
                    if len(buf) > cap:
                        raise FetchError(url, f"response larger than {cap} bytes")
                return bytes(buf)
            except requests.RequestException as e:
                if attempt < self.attempts:
                    time.sleep(self._backoff(attempt))
                    continue
                raise FetchError(url, f"stream error: {e}", transient=True) from e
            finally:
                r.close()
        raise FetchError(url, "no attempt made", transient=True)

    def fetch_json(self, url: str, params: dict | None = None, headers: dict | None = None):
        data = self.fetch_bytes(url, params, headers)
        try:
            return json.loads(data.decode("utf-8"))
        except ValueError as e:
            raise FetchError(url, f"invalid JSON: {e}") from e

    def download(self, url: str, dest: Path, cap: int) -> dict:
        for attempt in range(1, self.attempts + 1):
            r = self.get(url)
            cl = r.headers.get("content-length", "")
            if cl.isdigit() and int(cl) > cap:
                r.close()
                raise FetchError(url, f"too large ({int(cl)} B > {cap} B cap)")
            tmp = dest.with_name(dest.name + ".part")
            h256, hmd5, n = hashlib.sha256(), hashlib.md5(), 0
            try:
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(1 << 20):
                        n += len(chunk)
                        if n > cap:
                            raise FetchError(url, f"too large (> {cap} B cap)")
                        f.write(chunk)
                        h256.update(chunk)
                        hmd5.update(chunk)
            except requests.RequestException as e:
                tmp.unlink(missing_ok=True)
                if attempt < self.attempts:
                    d = self._backoff(attempt)
                    log.warning("stream error on %s (%s); retry %d/%d in %.0f s", url, e, attempt, self.attempts - 1, d)
                    time.sleep(d)
                    continue
                raise FetchError(url, f"stream error: {e}", transient=True) from e
            except BaseException:
                tmp.unlink(missing_ok=True)
                raise
            finally:
                r.close()
            os.replace(tmp, dest)
            log.debug("saved %d B from %s", n, url)
            return {"url": url, "final_url": r.final_url, "bytes": n, "sha256": h256.hexdigest(), "md5": hmd5.hexdigest(),
                    "content_type": r.headers.get("content-type", "")}
        raise FetchError(url, "no attempt made", transient=True)


@dataclass
class Got:
    path: Path
    info: dict


class RawCache:
    """Downloads land in <out>/.raw/<slug>/ with a sidecar JSON; a later run reuses them instead of fetching again."""

    def __init__(self, root: Path, http: Http, refetch: bool):
        self.root, self.http, self.refetch = root, http, refetch
        self.hits = 0

    def fetch(self, slug: str, url: str, *, name: str | None, expect: str | None, md5: str | None, cap: int) -> Got:
        d = self.root / slug
        d.mkdir(parents=True, exist_ok=True)
        base = safe_name(name or base_of(urlsplit(url).path) or "download", 100)
        p = d / f"{hashlib.sha1(url.encode()).hexdigest()[:10]}_{base}"
        side = p.with_name(p.name + ".src.json")
        if not self.refetch and p.is_file() and side.is_file():
            try:
                info = json.loads(side.read_text(encoding="utf-8"))
            except ValueError:
                info = {}
            if info.get("url") == url and info.get("bytes") == p.stat().st_size and (md5 is None or info.get("md5") == md5):
                self.hits += 1
                log.debug("cache hit %s", url)
                return Got(p, info)
        info = self.http.download(url, p, cap)
        if md5 and info["md5"] != md5:
            p.unlink(missing_ok=True)
            raise FetchError(url, f"MD5 mismatch ({info['md5']} != {md5})", transient=True)
        if expect:
            ok, what = sniff(p, expect)
            if not ok:
                p.unlink(missing_ok=True)
                raise FetchError(url, f"content is not {expect} (got {what}; Content-Type {info['content_type'] or '?'})")
        info["utc"] = utc_now()
        side.write_text(json.dumps(info, indent=1) + "\n", encoding="utf-8")
        return Got(p, info)


# ------------------------------------------------------------------------------------------------------------------- JATS
def lname(tag) -> str:
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def href_of(el) -> str:
    return (el.get(XL_HREF) or el.get("href") or "").strip()


def child(el, name):
    if el is None:
        return None
    return next((c for c in el if lname(c.tag) == name), None)


def article_of(root):
    if lname(root.tag) == "article":
        return root
    return next((e for e in root.iter() if lname(e.tag) == "article"), root)


def iter_main(el):
    """Document-order walk that leaves out peer-review sub-articles."""
    yield el
    for c in el:
        if lname(c.tag) not in ("sub-article", "response"):
            yield from iter_main(c)


def parse_xml(data: bytes):
    try:
        return ET.fromstring(data)
    except ET.ParseError as first:
        # The DTD is not loaded, so HTML entity names it would declare fail: replace them by their characters and retry.
        text = data.decode("utf-8", errors="replace")

        def repl(m):
            name = m.group(1)
            if name in ("amp", "lt", "gt", "quot", "apos"):
                return m.group(0)
            return html.entities.html5.get(name + ";", m.group(0))

        fixed = re.sub(r"^\s*<\?xml[^>]*\?>", "", re.sub(r"&([A-Za-z][A-Za-z0-9]*);", repl, text))
        try:
            return ET.fromstring(fixed)
        except ET.ParseError:
            raise first from None


def own_iter(el, stop=("fig", "fig-group", "table-wrap", "supplementary-material", "boxed-text")):
    """Descendants of `el` without descending into nested floats (their files belong to them)."""
    for c in el:
        yield c
        if lname(c.tag) not in stop:
            yield from own_iter(c, stop)


def body_stats(root) -> tuple[int, int]:
    body = child(article_of(root), "body")
    if body is None:
        return 0, 0
    ps = [p for p in body.iter() if lname(p.tag) == "p"]
    return len(ps), sum(len(norm_ws("".join(p.itertext()))) for p in ps)


FORMULA_ANC = {"disp-formula", "inline-formula", "chem-struct", "chem-struct-wrap"}


def jats_files(root) -> list[tuple[str, str]]:
    """Files the XML points to, in document order: (href, role), role in figure | formula | supp | video | subarticle."""
    out, seen = [], set()

    def put(href, role):
        if href and href.lower() not in seen:
            seen.add(href.lower())
            out.append((href, role))

    def walk(el, anc: frozenset):
        n = lname(el.tag)
        if n in ("sub-article", "response"):
            for g in el.iter():
                if lname(g.tag) in ("graphic", "inline-graphic", "media", "supplementary-material"):
                    put(href_of(g), "subarticle")
            return
        href = href_of(el) if n in ("graphic", "inline-graphic", "media", "supplementary-material") else ""
        if href:
            mimetype = (el.get("mimetype") or "").lower()
            if n == "inline-graphic" or anc & FORMULA_ANC:
                put(href, "formula")
            elif n == "media" and (mimetype in ("video", "audio") or ext_of(href) in MEDIA_EXT):
                put(href, "video")
            elif n == "graphic" and "supplementary-material" not in anc:
                put(href, "figure")
            else:
                put(href, "supp")
        for c in el:
            walk(c, anc | {n})

    walk(article_of(root), frozenset())
    return out


def jats_roles(root) -> dict[str, str]:
    roles: dict[str, str] = {}
    for href, role in jats_files(root):
        name = base_of(href).lower()
        roles.setdefault(name, role)
        roles.setdefault(name[: -len(ext_of(name))] if ext_of(name) else name, role)
    return roles


FLOATS = {"fig", "fig-group", "table-wrap", "table-wrap-group", "supplementary-material", "media", "boxed-text", "list",
          "def-list", "disp-quote", "statement", "preformat", "code", "chem-struct-wrap", "graphic", "table"}
NO_DESCEND = {"inline-formula", "disp-formula", "alternatives", "inline-graphic", "math", "tex-math"}
SKIP = {"title", "label", "object-id", "permissions", "alt-text", "attrib", "sec-meta", "kwd-group", "related-article",
        "counts", "funding-group", "custom-meta-group", "self-uri"}
BLOCKISH = FLOATS | {"p", "sec", "disp-formula", "ref-list", "app", "app-group", "ack", "fn-group", "fn", "glossary", "notes",
                     "title", "label", "abstract", "sub-article", "response", "def-item", "list-item", "caption"}


class JatsText:
    """JATS article -> plain text. Floats (figures, tables, supplementary files) are written where they occur, with the
    local file names that the lookups return."""

    def __init__(self, root, fig_lookup, supp_lookup):
        self.art = article_of(root)
        self.fig_lookup, self.supp_lookup = fig_lookup, supp_lookup
        self.lines: list[str] = []
        self.stats: Counter = Counter()
        self.in_body = False

    def emit(self, text: str) -> None:
        if text:
            self.lines += [text, ""]

    def heading(self, text: str, depth: int) -> None:
        if text:
            self.lines += ["", "#" * max(2, min(depth + 1, 6)) + " " + text, ""]

    def inline(self, el, skip=FLOATS) -> str:
        if el is None:
            return ""
        parts = [el.text or ""]
        for c in el:
            n = lname(c.tag)
            if n and n not in skip:
                if n in ("inline-formula", "disp-formula"):
                    parts.append(" " + self.formula(c) + " ")
                elif n == "alternatives":
                    parts.append(self.alternatives(c))
                elif n == "break":
                    parts.append(" ")
                elif n != "inline-graphic":
                    parts.append(self.inline(c, skip))
            parts.append(c.tail or "")
        return "".join(parts)

    def formula(self, el) -> str:
        for c in el.iter():
            n = lname(c.tag)
            if n == "alternatives":
                return self.alternatives(c)
            if n in ("math", "tex-math"):
                return norm_ws("".join(c.itertext()))
        if any(lname(c.tag) in ("graphic", "inline-graphic") for c in el.iter()):
            return "[formula image]"
        return norm_ws("".join(el.itertext()))

    def alternatives(self, el) -> str:
        for want in ("math", "tex-math"):
            for c in el:
                if lname(c.tag) == want:
                    return norm_ws("".join(c.itertext()))
        return "[formula image]"

    def title_of(self, el) -> str:
        lab, tit = child(el, "label"), child(el, "title")
        bits = [norm_ws(self.inline(lab)) if lab is not None else "", norm_ws(self.inline(tit)) if tit is not None else ""]
        return " ".join(b for b in bits if b)

    def floats_in(self, el):
        for c in el:
            n = lname(c.tag)
            if n in FLOATS:
                yield c
            elif n not in NO_DESCEND:
                yield from self.floats_in(c)

    def para(self, el, depth: int, count: bool = True) -> None:
        t = norm_ws(self.inline(el))
        if t:
            self.emit(t)
            if count and self.in_body:
                self.stats["body_paragraphs"] += 1
                self.stats["body_chars"] += len(t)
        for f in self.floats_in(el):
            self.block(f, depth)

    def caption(self, el, depth: int) -> None:
        cap = child(el, "caption")
        if cap is None:
            self.lines.append("")
            return
        for c in cap:
            n = lname(c.tag)
            if n == "title":
                t = norm_ws(self.inline(c))
                if t:
                    self.lines.append(t)
            elif n == "p":
                self.para(c, depth, count=False)
            else:
                self.block(c, depth)
        self.lines.append("")

    def block(self, el, depth: int) -> None:
        n = lname(el.tag)
        if not n or n in SKIP:
            return
        if n in ("sub-article", "response"):
            return
        handler = getattr(self, "b_" + n.replace("-", "_"), None)
        if handler:
            handler(el, depth)
            return
        title = self.title_of(el)
        if title:
            self.heading(title, depth)
        if any(lname(c.tag) in BLOCKISH for c in el):
            for c in el:
                self.block(c, depth + 1)
        else:
            t = norm_ws(self.inline(el, FLOATS | {"title", "label"}))
            if t:
                self.emit(t)
                if self.in_body:
                    self.stats["body_chars"] += len(t)

    def b_p(self, el, depth):
        self.para(el, depth)

    def b_fig(self, el, depth):
        label = norm_ws(self.inline(child(el, "label")))
        own = list(own_iter(el))  # not the graphics of nested figures (eLife: fig > p > fig for figure supplements)
        hrefs = [href_of(g) for g in own if lname(g.tag) == "graphic" and href_of(g)]
        media = [href_of(m) for m in own if lname(m.tag) == "media" and href_of(m)]
        files = [f for f in (self.fig_lookup(h) for h in hrefs) if f]
        bits = ["image file: " + ", ".join(files)] if files else (["image file: not available"] if hrefs else [])
        bits += [self.supp_lookup(m) for m in dict.fromkeys(media)]  # a video given as a figure
        self.lines += ["", "[FIGURE" + (" " + label if label else "") + "]" + (" (" + "; ".join(bits) + ")" if bits else "")]
        self.caption(el, depth)
        for c in el:
            n = lname(c.tag)
            if n in ("supplementary-material", "fig", "fig-group", "table-wrap"):
                self.block(c, depth)
            elif n == "p":  # holds the figure supplements in eLife XML
                self.para(c, depth, count=False)
        self.stats["figures"] += 1

    def b_fig_group(self, el, depth):
        if child(el, "caption") is not None or child(el, "label") is not None:
            label = norm_ws(self.inline(child(el, "label")))
            self.lines += ["", "[FIGURE GROUP" + (" " + label if label else "") + "]"]
            self.caption(el, depth)
        for c in el:
            if lname(c.tag) in ("fig", "fig-group", "supplementary-material", "media", "graphic"):
                self.block(c, depth)

    def b_table_wrap(self, el, depth):
        label = norm_ws(self.inline(child(el, "label")))
        own = list(own_iter(el))
        tables = [t for t in own if lname(t.tag) == "table"]
        hrefs = [href_of(g) for g in own if lname(g.tag) == "graphic" and href_of(g)]
        files = [f for f in (self.fig_lookup(h) for h in hrefs) if f]
        head = "[TABLE" + (" " + label if label else "") + "]"
        if files:
            head += " (image file: " + ", ".join(files) + ")"
        elif hrefs and not tables:
            head += " (table image: not available; see the page images)"
        self.lines += ["", head]
        self.caption(el, depth)
        for t in tables:
            self.b_table(t, depth)
        for foot in (c for c in el if lname(c.tag) == "table-wrap-foot"):
            for x in foot.iter():
                if lname(x.tag) in ("p", "attrib"):
                    t = norm_ws(self.inline(x))
                    if t:
                        self.lines.append(t)
        self.lines.append("")
        self.stats["tables"] += 1

    def b_table(self, el, depth):
        for tr in el.iter():
            if lname(tr.tag) == "tr":
                cells = [norm_ws(self.inline(td, skip=set())) for td in tr if lname(td.tag) in ("td", "th")]
                self.lines.append("\t".join(cells))
        self.lines.append("")

    def _file_float(self, el, depth, kind: str, stat: str):
        label = norm_ws(self.inline(child(el, "label")))
        hrefs = [href_of(el)] if href_of(el) else []
        hrefs += [href_of(m) for m in el.iter() if m is not el and lname(m.tag) in ("media", "graphic") and href_of(m)]
        descs = [self.supp_lookup(h) for h in dict.fromkeys(hrefs)]
        self.lines += ["", f"[{kind}" + (" " + label if label else "") + "]" + (" (" + "; ".join(descs) + ")" if descs else "")]
        self.caption(el, depth)
        self.stats[stat] += 1

    def b_supplementary_material(self, el, depth):
        self._file_float(el, depth, "SUPPLEMENTARY FILE", "supplementary")

    def b_media(self, el, depth):
        self._file_float(el, depth, "MEDIA FILE", "media")

    def b_graphic(self, el, depth):
        f = self.fig_lookup(href_of(el)) if href_of(el) else None
        self.emit(f"[IMAGE] (image file: {f or 'not available'})")

    def b_list(self, el, depth, indent: int = 0):
        for item in el:
            if lname(item.tag) != "list-item":
                continue
            lab = child(item, "label")
            prefix = "  " * indent + (norm_ws(self.inline(lab)) + " " if lab is not None else "- ")
            texts = [norm_ws(item.text)]
            nested = []
            for c in item:
                cn = lname(c.tag)
                if cn == "list":
                    nested.append(c)
                elif cn != "label":
                    texts.append(norm_ws(self.inline(c)))
            t = " ".join(x for x in texts if x)
            if t:
                self.lines.append(prefix + t)
                if self.in_body:
                    self.stats["body_chars"] += len(t)
            for c in nested:
                self.b_list(c, depth, indent + 1)
        if indent == 0:
            self.lines.append("")

    def b_def_list(self, el, depth):
        for item in el.iter():
            if lname(item.tag) == "def-item":
                term = norm_ws(self.inline(child(item, "term")))
                dfn = norm_ws(self.inline(child(item, "def"), skip=set()))
                self.lines.append(f"{term}: {dfn}" if term else dfn)
        self.lines.append("")

    def b_disp_formula(self, el, depth):
        self.emit("[formula] " + self.formula(el))

    def b_preformat(self, el, depth):
        self.emit("".join(el.itertext()).strip("\n"))

    b_code = b_preformat

    def b_ref_list(self, el, depth):
        self.heading(self.title_of(el) or "References", depth)
        for r in el.iter():
            if lname(r.tag) != "ref":
                continue
            lab = child(r, "label")
            txt = " ".join(t.strip() for c in r if lname(c.tag) != "label" for t in c.itertext() if t.strip())
            self.lines.append((norm_ws(self.inline(lab)) + " " if lab is not None else "") + norm_ws(txt))
            self.stats["references"] += 1
        self.lines.append("")

    def render(self) -> str:
        art = self.art
        meta = child(child(art, "front"), "article-meta")
        if meta is not None:
            for ab in (c for c in meta if lname(c.tag) in ("abstract", "trans-abstract")):
                kind = ab.get("abstract-type") or ""
                self.heading(self.title_of(ab) or ("Abstract" + (f" ({kind})" if kind else "")), 1)
                for c in ab:
                    self.block(c, 2)
                self.stats["abstracts"] += 1
        body = child(art, "body")
        if body is not None:
            self.in_body = True
            for c in body:
                self.block(c, 1)
            self.in_body = False
        back = child(art, "back")
        if back is not None:
            for c in back:
                self.block(c, 1)
        floats = child(art, "floats-group")
        if floats is not None:
            self.heading("Figures and tables", 1)
            for c in floats:
                self.block(c, 2)
        n_sub = sum(1 for c in art if lname(c.tag) in ("sub-article", "response"))
        if n_sub:
            self.lines += ["", (f"[{n_sub} sub-article(s) of the XML (peer review: decision letter, reviews or author "
                                "response) are not included in this text]")]
            self.stats["sub_articles_omitted"] = n_sub
        return re.sub(r"\n{3,}", "\n\n", "\n".join(self.lines)).strip() + "\n"


def xml_counts(root) -> dict:
    c = Counter(lname(e.tag) for e in iter_main(article_of(root)))
    return {k: c[k] for k in ("sec", "p", "fig", "table-wrap", "supplementary-material", "media", "ref")}


# ---------------------------------------------------------------------------------------------------- file converters
def iter_archive(path: Path, name: str):
    """(member name, declared size, opener) for the regular files of a zip or tar archive."""
    if name.lower().endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            for info in z.infolist():
                if not info.is_dir():
                    yield info.filename, info.file_size, (lambda info=info: z.open(info))
    else:
        with tarfile.open(path, "r:*") as tf:
            for m in tf:
                if m.isfile():
                    yield m.name, m.size, (lambda m=m: tf.extractfile(m))


def docx_text(path: Path) -> str:
    w = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    with zipfile.ZipFile(path) as z:
        info = z.getinfo("word/document.xml")
        if info.file_size > 200 << 20:
            raise TooLarge("word/document.xml larger than 200 MB")
        root = ET.fromstring(z.read(info))

    def ptext(p) -> str:
        out = []
        for e in p.iter():
            if e.tag == w + "t":
                out.append(e.text or "")
            elif e.tag == w + "tab":
                out.append("\t")
            elif e.tag in (w + "br", w + "cr"):
                out.append("\n")
        return "".join(out)

    lines: list[str] = []

    def walk(container) -> None:
        for e in container:
            if e.tag == w + "p":
                lines.append(ptext(e))
            elif e.tag == w + "tbl":
                for tr in e.iter(w + "tr"):
                    lines.append("\t".join(" ".join(ptext(p) for p in tc.iter(w + "p")).strip() for tc in tr.findall(w + "tc")))
                lines.append("")
            elif e.tag == w + "sdt":
                content = e.find(w + "sdtContent")
                if content is not None:
                    walk(content)

    body = root.find(w + "body")
    if body is not None:
        walk(body)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip() + "\n"


# --------------------------------------------------------------------------------------------------------------- registry
@dataclass
class Entry:
    doi: str
    slug: str
    title: str


SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,150}$")


def load_registry(path: Path) -> list[Entry]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        rdr = csv.DictReader(f)
        cols = {(h or "").strip().lower(): h for h in (rdr.fieldnames or [])}
        if "doi" not in cols:
            raise SystemExit(f"{path}: no `doi` column (columns: {list(cols)})")
        entries, seen, problems = [], {}, []
        for line, row in enumerate(rdr, start=2):
            doi = norm_doi(row.get(cols["doi"]) or "")
            if not doi:
                continue
            if doi.lower() in seen:
                log.warning("registry line %d: %s repeats line %d; ignored", line, doi, seen[doi.lower()])
                continue
            seen[doi.lower()] = line
            slug = (row.get(cols["slug"]) or "").strip() if "slug" in cols else ""
            if slug and not SLUG_RE.match(slug):
                problems.append(f"line {line}: unsafe slug {slug!r}")
                continue
            title = (row.get(cols["title"]) or "").strip() if "title" in cols else ""
            entries.append(Entry(doi, slug or slug_from_doi(doi), title))
    by_slug: dict[str, list[str]] = {}
    for e in entries:
        by_slug.setdefault(e.slug.lower(), []).append(e.doi)
    problems += [f"slug {s!r} is shared by {d}" for s, d in by_slug.items() if len(d) > 1]
    if problems:
        raise SystemExit(f"{path}: fix the registry first:\n  " + "\n  ".join(problems))
    return entries


# ------------------------------------------------------------------------------------------------------------------ paper
@dataclass
class Run:
    args: argparse.Namespace
    out: Path
    http: Http
    cache: RawCache


class Paper:
    def __init__(self, entry: Entry, run: Run):
        self.e, self.run, self.http, self.args = entry, run, run.http, run.args
        self.dir = run.out / ".partial" / entry.slug
        self.tmp = self.dir / ".tmp"
        self.used: set[str] = set()
        self.pdfnames: set[str] = set()
        self.n_tmp = 0
        self.route_name = "start"
        self.meta: dict = {
            "doi": entry.doi, "slug": entry.slug, "title": None, "year": None, "status": None, "routes_tried": [],
            "errors": [], "files": [], "skipped": [], "fulltext": {}, "pdfs": [], "spreadsheets": [], "archives": [],
            "ids": {}, "journal": None, "license": None, "registry_title": entry.title or None, "notes": [],
            "script_version": SCRIPT_VERSION,
        }
        self.title = self.year = self.journal = self.authors = None
        self.abstract = self.abstract_src = None
        self.rec: dict | None = None
        self.pmcid: str | None = None
        self.root = self.root_label = self.root_path = self.root_origin = None
        self.pdf_rel = self.pdf_label = None
        self.fig_files: dict[str, str] = {}
        self.supp: dict[str, dict] = {}

    # -- bookkeeping
    def err(self, msg: str, url: str | None = None, transient: bool = False) -> None:
        self.meta["errors"].append({"route": self.route_name, "url": url, "error": msg, "transient": bool(transient)})
        log.warning("%s [%s] %s%s", self.e.doi, self.route_name, msg, f" <{url}>" if url else "")

    def ferr(self, e: FetchError) -> None:
        self.err(e.msg, e.url, e.transient)

    def skip(self, name: str, size, reason: str, url: str | None = None, register: bool = False) -> None:
        self.meta["skipped"].append({"name": name, "bytes": size, "reason": reason, "url": url})
        if register:
            self.register_supp({"name": name, "path": None, "derived": [], "note": f"not downloaded: {reason} ({human(size)})"})

    def route(self, name: str, fn) -> None:
        if name in self.args.skip_route:
            self.meta["routes_tried"].append({"route": name, "result": "skipped (--skip-route)"})
            return
        self.route_name, n0, t0 = name, self.http.n, time.monotonic()
        try:
            result = fn() or "ok"
        except FetchError as e:
            self.ferr(e)
            result = f"failed: {e.msg}"
        except Exception as e:  # a converter bug must not lose the other routes or the DOI
            log.exception("%s [%s] unexpected error", self.e.doi, name)
            self.err(f"{type(e).__name__}: {e}")
            result = f"error: {type(e).__name__}"
        self.meta["routes_tried"].append({"route": name, "result": result, "requests": self.http.n - n0,
                                          "seconds": round(time.monotonic() - t0, 1)})
        log.info("%s [%s] %s", self.e.doi, name, result)
        self.route_name = "finish"

    def fetch(self, url: str, *, name: str | None = None, expect: str | None = None, md5: str | None = None) -> Got:
        return self.run.cache.fetch(self.e.slug, url, name=name, expect=expect, md5=md5, cap=self.args.max_file_bytes)

    # -- output files
    def unique_rel(self, rel: str) -> str:
        p, cand, k = PurePosixPath(rel), rel, 2
        while cand.lower() in self.used or (self.dir / cand).exists():
            cand = str(p.with_name(f"{p.stem}_{k}{p.suffix}"))
            k += 1
        self.used.add(cand.lower())
        return cand

    def place(self, src: Path, rel: str) -> str:
        rel = self.unique_rel(rel)
        dst = self.dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.link(src, dst)
        except OSError:
            shutil.copy2(src, dst)
        return rel

    def write_text_file(self, rel: str, text: str) -> str:
        rel = self.unique_rel(rel)
        p = self.dir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")
        return rel

    def tmpfile(self) -> Path:
        self.n_tmp += 1
        self.tmp.mkdir(parents=True, exist_ok=True)
        return self.tmp / f"t{self.n_tmp}"

    def register_supp(self, entry: dict) -> dict:
        name = entry["name"].lower()
        self.supp.setdefault(name, entry)
        self.supp.setdefault(stem_of(name), entry)
        return entry

    def fig_lookup(self, href: str) -> str | None:
        return self.fig_files.get(href_key(href))

    def supp_lookup(self, href: str) -> str:
        name = base_of(href).lower()
        e = self.supp.get(name) or self.supp.get(stem_of(name))
        if e is None:
            f = self.fig_files.get(href_key(href))
            return f"image file: {f}" if f else "file not downloaded"
        parts = []
        if e.get("path"):
            parts.append("file: " + e["path"])
        derived = e.get("derived") or []
        if derived:
            parts.append("as text: " + ", ".join(derived[:12]) + (f" and {len(derived) - 12} more" if len(derived) > 12 else ""))
        if e.get("note"):
            parts.append(e["note"])
        return "; ".join(parts) or "file not downloaded"

    def set_main_pdf(self, src: Path, label: str) -> None:
        if self.pdf_rel is None:
            self.pdf_rel, self.pdf_label = self.place(src, "article.pdf"), label

    def try_root(self, path: Path, label: str, origin: str) -> str:
        try:
            root = parse_xml(path.read_bytes())
        except ET.ParseError as e:
            self.err(f"XML does not parse ({label}): {e}")
            return "XML does not parse"
        n_p, n_c = body_stats(root)
        if n_p < MIN_XML_PARAGRAPHS or n_c < MIN_XML_CHARS:
            self.err(f"XML without article body ({label}): {n_p} paragraphs, {n_c} characters")
            return f"XML without article body ({n_p} paragraphs, {n_c} characters)"
        self.root, self.root_label, self.root_path, self.root_origin = root, label, path, origin
        return f"ok: XML body {n_p} paragraphs, {n_c} characters"

    # -- conversions
    def place_image(self, src: Path, rel_dir: str, stem: str) -> str:
        with open(src, "rb") as f:
            kind = image_kind(f.read(16))
        stem = safe_name(stem)
        if kind == "jpeg":
            return self.place(src, f"{rel_dir}/{stem}.jpg")
        if kind == "png":
            return self.place(src, f"{rel_dir}/{stem}.png")
        try:
            pix = pymupdf.Pixmap(str(src))
            if pix.colorspace is not None and pix.colorspace.n > 3:
                pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
            if pix.alpha:
                pix = pymupdf.Pixmap(pix, 0)
            while max(pix.width, pix.height) > 8000:
                pix.shrink(1)
            rel = self.unique_rel(f"{rel_dir}/{stem}.png")
            (self.dir / rel).parent.mkdir(parents=True, exist_ok=True)
            pix.save(self.dir / rel)
            return rel
        except Exception as e:
            self.err(f"image {src.name} ({kind}) not converted to PNG: {e}; kept as it is")
            return self.place(src, f"{rel_dir}/{stem}{'.' + kind if kind else ext_of(src.name)}")

    def unique_pdfname(self, base: str) -> str:
        base, cand, k = safe_name(base, 100), safe_name(base, 100), 2
        while cand.lower() in self.pdfnames:
            cand = f"{base}_{k}"
            k += 1
        self.pdfnames.add(cand.lower())
        return cand

    def process_pdf(self, rel: str, pdfname: str) -> tuple[dict, str]:
        info = {"file": rel, "pages": 0, "rendered": 0, "dpi": self.args.dpi, "text_chars": 0, "text_file": None,
                "page_images": f"pages/{pdfname}_pNNN.png"}
        self.meta["pdfs"].append(info)
        try:
            doc = pymupdf.open(self.dir / rel)
        except Exception as e:
            self.err(f"PDF does not open ({rel}): {e}")
            return info, ""
        parts = []
        try:
            if doc.needs_pass and not doc.authenticate(""):
                self.err(f"PDF is password-protected ({rel})")
                return info, ""
            info["pages"] = doc.page_count
            (self.dir / "pages").mkdir(exist_ok=True)
            for i in range(doc.page_count):
                page = doc.load_page(i)
                try:
                    t = page.get_text("text")
                except Exception as e:
                    t = ""
                    self.err(f"no text from page {i + 1} of {rel}: {e}")
                parts.append(f"[page {i + 1}]\n{t.strip()}\n")
                if i >= self.args.max_pages:
                    continue
                try:
                    dpi = self.args.dpi
                    area = max(page.rect.width / 72 * page.rect.height / 72, 1e-6)
                    if area * dpi * dpi > 30e6:  # posters and other huge pages
                        dpi = max(36, int(math.sqrt(30e6 / area)))
                    page.get_pixmap(dpi=dpi, alpha=False).save(self.dir / "pages" / f"{pdfname}_p{i + 1:03d}.png")
                    info["rendered"] += 1
                except Exception as e:
                    self.err(f"no image of page {i + 1} of {rel}: {e}")
        finally:
            doc.close()
        if info["pages"] > self.args.max_pages:
            self.meta["notes"].append(f"{rel}: only the first {self.args.max_pages} of {info['pages']} pages have page images")
        text = "\n".join(parts)
        info["text_chars"] = len(re.sub(r"\s+", "", re.sub(r"\[page \d+\]", "", text)))
        return info, text

    def extract_pdf_images(self, limit: int = 80, min_side: int = 300) -> int:
        """Fallback when there are no figure files: the raster images embedded in article.pdf."""
        n = 0
        try:
            doc = pymupdf.open(self.dir / self.pdf_rel)
        except Exception as e:
            self.err(f"PDF does not open for image extraction: {e}")
            return 0
        with doc:
            seen: set[int] = set()
            for pno in range(doc.page_count):
                for img in doc.get_page_images(pno, full=True):
                    xref, w, h = img[0], img[2], img[3]
                    if xref in seen or min(w, h) < min_side:
                        continue
                    seen.add(xref)
                    name = f"figures/article_p{pno + 1:03d}_img{len(seen)}"
                    try:
                        d = doc.extract_image(xref)
                        if d.get("ext") in ("jpeg", "jpg") and d.get("colorspace") in (1, 3):
                            rel = self.unique_rel(name + ".jpg")
                            (self.dir / rel).write_bytes(d["image"])
                        else:
                            pix = pymupdf.Pixmap(doc, xref)
                            if pix.colorspace is None:
                                continue
                            if pix.colorspace.n > 3:
                                pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
                            if pix.alpha:
                                pix = pymupdf.Pixmap(pix, 0)
                            pix.save(self.dir / self.unique_rel(name + ".png"))
                        n += 1
                    except Exception as e:
                        self.err(f"embedded image {xref} on page {pno + 1} not extracted: {e}")
                    if n >= limit:
                        return n
        return n

    def write_csv(self, rel: str, rows) -> tuple[int, int, bool]:
        p = self.dir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        n_rows = n_cols = blank = 0
        trunc = False
        with open(p, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, lineterminator="\n")
            for row in rows:
                vals = ["" if v is None else cell_str(v) for v in row]
                while vals and vals[-1] == "":
                    vals.pop()
                if not vals:
                    blank += 1
                    continue
                for _ in range(blank):
                    w.writerow([])
                blank = 0
                w.writerow(vals)
                n_rows += 1
                n_cols = max(n_cols, len(vals))
                if n_rows % 2000 == 0 and f.tell() > self.args.max_csv_bytes:
                    trunc = True
                    break
        return n_rows, n_cols, trunc

    def sheets(self, rel: str, rel_dir: str, stem: str) -> list[str]:
        """One CSV per sheet. openpyxl for .xlsx-type files, xlrd (if installed) for legacy .xls."""
        path, out = self.dir / rel, []
        legacy = ext_of(rel) == ".xls"
        if (xlrd if legacy else openpyxl) is None:
            self.meta["notes"].append(f"{rel}: kept unconverted ({'xlrd' if legacy else 'openpyxl'} not installed)")
            return out
        try:
            if legacy:
                book = xlrd.open_workbook(str(path), on_demand=True)
                sheets = [(book.sheet_by_index(i).name, self._xls_rows(book, i)) for i in range(book.nsheets)]
            else:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    book = openpyxl.load_workbook(path, read_only=True, data_only=True)
                sheets = []
                for ws in book.worksheets:
                    if hasattr(ws, "reset_dimensions"):  # read-only mode trusts the declared dimensions otherwise
                        ws.reset_dimensions()
                    sheets.append((ws.title, ws.iter_rows(values_only=True)))
        except Exception as e:
            self.err(f"spreadsheet {rel} does not open: {e}")
            return out
        try:
            for title, rows in sheets:
                csv_rel = self.unique_rel(f"{rel_dir}/{stem}__{safe_name(title, 60)}.csv")
                n_rows, n_cols, trunc = self.write_csv(csv_rel, rows)
                self.meta["spreadsheets"].append({"file": rel, "sheet": title, "csv": csv_rel, "rows": n_rows,
                                                  "cols": n_cols, "truncated": trunc})
                if trunc:
                    self.meta["notes"].append(f"{csv_rel}: truncated at about {self.args.max_csv_mb} MB")
                out.append(csv_rel)
        except Exception as e:
            self.err(f"spreadsheet {rel}: conversion stopped: {e}")
        finally:
            (book.release_resources if legacy else book.close)()
        return out

    @staticmethod
    def _xls_rows(book, i):
        sh = book.sheet_by_index(i)
        for r in range(sh.nrows):
            row = []
            for c in range(sh.ncols):
                cell = sh.cell(r, c)
                v = cell.value
                if cell.ctype == xlrd.XL_CELL_DATE:
                    try:
                        v = xlrd.xldate.xldate_as_datetime(v, book.datemode)
                    except Exception:
                        pass
                elif cell.ctype in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK):
                    v = None
                elif cell.ctype == xlrd.XL_CELL_NUMBER and float(v).is_integer() and abs(v) < 1e15:
                    v = int(v)
                row.append(v)
            yield row

    def add_supp(self, src: Path, name: str, rel_dir: str = "supp", depth: int = 0, url: str | None = None) -> dict:
        """Keep one supplementary file and write its text forms; returns its entry for text.txt."""
        name = safe_name(name)
        ext, size = ext_of(name), src.stat().st_size
        entry = {"name": name, "path": None, "derived": [], "note": ""}
        if ext in MEDIA_EXT:
            self.skip(name, size, "video or audio", url)
            entry["note"] = f"video or audio, not kept ({human(size)})"
            return self.register_supp(entry)
        if is_archive(name) and depth < 2:
            return self.register_supp(self.expand_archive(src, name, rel_dir, depth, url))
        if ext == ".gz" and depth < 2:
            tmp = self.tmpfile()
            try:
                with gzip.open(src, "rb") as fi, open(tmp, "wb") as fo:
                    copy_capped(fi, fo, self.args.max_file_bytes)
            except (OSError, EOFError, TooLarge) as e:
                self.err(f"{name}: not decompressed ({e}); kept as it is", url)
            else:
                inner = self.add_supp(tmp, name[:-3] or "file", rel_dir, depth + 1, url)
                tmp.unlink(missing_ok=True)
                inner["note"] = "; ".join(x for x in (inner["note"], f"decompressed from {name}") if x)
                return inner
        if ext in IMAGE_EXT:
            entry["path"] = self.place_image(src, rel_dir, stem_of(name))
            return self.register_supp(entry)
        convertible = ext in SHEET_EXT or ext in (".xls", ".pdf", ".docx")
        if size > self.args.max_file_bytes:
            self.skip(name, size, "larger than --max-file-mb", url)
            entry["note"] = f"not kept ({human(size)}, larger than the size cap)"
            return self.register_supp(entry)
        if not (convertible or ext in TEXT_EXT or size <= self.args.max_keep_bytes or looks_like_text(src)):
            self.skip(name, size, "binary file larger than --max-keep-mb", url)
            entry["note"] = f"not kept (binary, {human(size)})"
            return self.register_supp(entry)
        rel = self.place(src, f"{rel_dir}/{name}")
        entry["path"] = rel
        stem = stem_of(PurePosixPath(rel).name)
        if ext in SHEET_EXT or ext == ".xls":
            entry["derived"] = self.sheets(rel, rel_dir, stem)
        elif ext == ".pdf":
            sub = rel_dir.split("/", 1)[1] if "/" in rel_dir else ""
            pdfname = self.unique_pdfname("__".join(x for x in (sub.replace("/", "__"), stem) if x))
            info, text = self.process_pdf(rel, pdfname)
            if text:
                info["text_file"] = self.write_text_file(f"{rel_dir}/{stem}.txt", f"Text extracted mechanically from {rel}, page by page.\n\n{text}")
                entry["derived"].append(info["text_file"])
            if info["rendered"]:
                entry["derived"].append(f"page images pages/{pdfname}_p001.png ... ({info['rendered']} pages)")
        elif ext == ".docx":
            try:
                entry["derived"].append(self.write_text_file(f"{rel_dir}/{stem}.txt", docx_text(self.dir / rel)))
            except Exception as e:
                self.err(f"{rel}: no text extracted ({e})")
        return self.register_supp(entry)

    def expand_archive(self, src: Path, name: str, rel_dir: str, depth: int, url: str | None) -> dict:
        size = src.stat().st_size
        target = self.unique_rel(f"{rel_dir}/{safe_name(archive_stem(name))}")
        arc = {"name": name, "bytes": size, "sha256": sha256_file(src), "url": url, "expanded_to": target, "members": 0,
               "kept": 0}
        self.meta["archives"].append(arc)
        entry = {"name": name, "path": None, "derived": [], "note": ""}
        total = 0
        try:
            for member, msize, opener in iter_archive(src, name):
                arc["members"] += 1
                raw = [p for p in member.replace("\\", "/").split("/") if p]
                if not raw or any(p.lower() == "__macosx" for p in raw) or raw[-1] in (".DS_Store", "Thumbs.db", "desktop.ini") \
                        or raw[-1].startswith("._"):  # macOS resource forks and folder metadata, not data
                    continue
                parts = safe_parts(member)
                if not parts:
                    continue
                label = f"{name}:{member}"
                if ext_of(parts[-1]) in MEDIA_EXT:
                    self.skip(label, msize, "video or audio inside an archive", url)
                    continue
                if msize > self.args.max_file_bytes or total + msize > self.args.max_archive_bytes:
                    self.skip(label, msize, "archive member over the size caps", url)
                    continue
                total += msize
                tmp = self.tmpfile()
                try:
                    with opener() as fi, open(tmp, "wb") as fo:
                        copy_capped(fi, fo, self.args.max_file_bytes)
                except TooLarge:
                    tmp.unlink(missing_ok=True)
                    self.skip(label, msize, "archive member over the size caps", url)
                    continue
                e = self.add_supp(tmp, parts[-1], "/".join([target] + parts[:-1]), depth + 1, None)
                tmp.unlink(missing_ok=True)
                if e.get("path"):
                    arc["kept"] += 1
                    entry["derived"].append(e["path"])
                entry["derived"] += [d for d in e.get("derived", []) if not d.startswith("page images")]
        except (zipfile.BadZipFile, tarfile.TarError, OSError, RuntimeError, EOFError, ValueError) as e:
            self.err(f"archive {name} not read completely: {e}", url)
        entry["note"] = f"archive ({human(size)}) expanded into {target}/: {arc['kept']} files kept"
        return entry

    # -- routes
    def r_europepmc_search(self) -> str:
        params = {"query": f'DOI:"{self.e.doi}"', "format": "json", "resultType": "core", "pageSize": "25"}
        j = self.http.fetch_json(f"{EPMC_REST}/search", params)
        res = [r for r in (j.get("resultList") or {}).get("result") or [] if (r.get("doi") or "").lower() == self.e.doi.lower()]
        if not res:
            return f"no record with this DOI ({j.get('hitCount', 0)} hits)"
        rec = min(res, key=lambda r: (not r.get("pmcid"), r.get("source") == "PPR"))
        self.rec, self.pmcid = rec, rec.get("pmcid")
        self.authors = norm_ws(rec.get("authorString")) or None
        self.title = strip_tags(rec.get("title") or "").replace("\n", " ") or None
        self.year = rec.get("pubYear") or None
        self.journal = ((rec.get("journalInfo") or {}).get("journal") or {}).get("title") or \
            (rec.get("bookOrReportDetails") or {}).get("publisher")
        self.meta["license"] = rec.get("license")
        if rec.get("abstractText"):
            self.abstract, self.abstract_src = strip_tags(rec["abstractText"]), "Europe PMC"
        self.meta["ids"].update({"europepmc": f"{rec.get('source')}:{rec.get('id')}", "pmid": rec.get("pmid"),
                                 "pmcid": self.pmcid, "isOpenAccess": rec.get("isOpenAccess"), "inEPMC": rec.get("inEPMC")})
        return (f"ok: {rec.get('source')}:{rec.get('id')}, pmcid {self.pmcid}, isOpenAccess {rec.get('isOpenAccess')}, "
                f"inEPMC {rec.get('inEPMC')}, abstract {'yes' if self.abstract else 'no'}")

    def r_europepmc_fulltext(self) -> str:
        g = self.fetch(f"{EPMC_REST}/{self.pmcid}/fullTextXML", name=f"{self.pmcid}_europepmc.xml", expect="xml")
        return self.try_root(g.path, f"Europe PMC full-text XML ({self.pmcid})", "pmc")

    def s3_list(self, prefix: str) -> list[tuple[str, int]]:
        ns = {"s": "http://s3.amazonaws.com/doc/2006-03-01/"}
        out, token = [], None
        while True:
            params = {"list-type": "2", "prefix": prefix, "max-keys": "1000"}
            if token:
                params["continuation-token"] = token
            root = ET.fromstring(self.http.fetch_bytes(PMC_BUCKET + "/", params))
            for c in root.findall("s:Contents", ns):
                out.append((c.findtext("s:Key", "", ns), int(c.findtext("s:Size", "0", ns) or 0)))
            token = root.findtext("s:NextContinuationToken", None, ns)
            if root.findtext("s:IsTruncated", "false", ns) != "true" or not token:
                return out

    @staticmethod
    def s3_key(u: str | None) -> tuple[str | None, str | None]:
        m = re.match(r"s3://pmc-oa-opendata/([^?]+)(?:\?md5=([0-9a-fA-F]{32}))?", u or "")
        return (m.group(1), (m.group(2) or "").lower() or None) if m else (None, None)

    def r_pmc_cloud(self) -> str:
        versions: dict[int, dict[str, int]] = {}
        for key, size in self.s3_list(f"{self.pmcid}."):
            m = re.match(rf"^{re.escape(self.pmcid)}\.(\d+)/", key)
            if m:
                versions.setdefault(int(m.group(1)), {})[key] = size
        if not versions:
            self.err("article not in the PMC Cloud bucket (it holds the open-access and author-manuscript datasets)")
            return "not in the bucket"
        v = max(versions)
        sizes, folder = versions[v], f"{self.pmcid}.{v}"
        j = self.http.fetch_json(f"{PMC_BUCKET}/{folder}/{folder}.json")
        self.meta["ids"]["pmc_cloud"] = {k: j.get(k) for k in ("license_code", "is_manuscript", "is_retracted", "citation")}
        self.meta["ids"]["pmc_cloud"]["folder"] = folder
        if j.get("is_retracted"):
            self.meta["notes"].append("PMC marks this article as retracted")
        url_of = lambda key: f"{PMC_BUCKET}/{quote(key, safe='/')}"
        got = []
        if self.root is None:
            key, md5 = self.s3_key(j.get("xml_url"))
            if key:
                try:
                    g = self.fetch(url_of(key), name=base_of(key), expect="xml", md5=md5)
                    got.append("xml " + self.try_root(g.path, f"PMC Cloud XML ({folder})", "pmc"))
                except FetchError as e:
                    self.ferr(e)
        roles = jats_roles(self.root) if self.root is not None and self.root_origin == "pmc" else {}
        key, md5 = self.s3_key(j.get("pdf_url"))
        if key and self.pdf_rel is None:
            try:
                g = self.fetch(url_of(key), name=base_of(key), expect="pdf", md5=md5)
                self.set_main_pdf(g.path, f"PMC Cloud PDF ({folder})")
                got.append("pdf")
            except FetchError as e:
                self.ferr(e)
        figs: dict[str, tuple] = {}
        supps = []
        n_media = 0
        for u in j.get("media_urls") or []:
            key, md5 = self.s3_key(u)
            if not key:
                continue
            fname = base_of(key)
            ext, stem, size, url = ext_of(fname), stem_of(fname).lower(), sizes.get(key), url_of(key)
            role = roles.get(fname.lower()) or roles.get(stem)
            if ext in MEDIA_EXT or role == "video":
                n_media += 1
                self.skip(fname, size, "video or audio", url, register=True)
            elif role == "subarticle":
                self.skip(fname, size, "belongs to a peer-review sub-article (not in text.txt)", url)
            elif ext in IMAGE_EXT and role == "formula":
                self.skip(fname, size, "formula or inline image", url)
            elif ext in IMAGE_EXT and role in (None, "figure"):
                cur = figs.get(stem)
                if cur is None or IMG_RANK[ext] < IMG_RANK[ext_of(cur[2])]:
                    if cur:
                        self.skip(cur[2], cur[3], "same figure in another format", cur[0])
                    figs[stem] = (url, md5, fname, size)
                else:
                    self.skip(fname, size, "same figure in another format", url)
            else:
                supps.append((url, md5, fname, size))
        for stem, (url, md5, fname, size) in sorted(figs.items()):
            try:
                g = self.fetch(url, name=fname, expect="image", md5=md5)
            except FetchError as e:
                self.ferr(e)
                continue
            self.fig_files[stem] = self.place_image(g.path, "figures", stem_of(fname))
        n_supp = 0
        for url, md5, fname, size in supps:
            if size and size > self.args.max_file_bytes:
                self.skip(fname, size, "larger than --max-file-mb", url, register=True)
                continue
            try:
                g = self.fetch(url, name=fname, expect="nothtml", md5=md5)
            except FetchError as e:
                self.ferr(e)
                continue
            self.add_supp(g.path, fname, "supp", 0, url)
            n_supp += 1
        got += [f"{len([s for s in figs if s in self.fig_files])}/{len(figs)} figures", f"{n_supp}/{len(supps)} supplementary files",
                f"{n_media} videos not downloaded"]
        return f"ok: {folder}: " + ", ".join(got)

    def r_biorxiv(self) -> str:
        doi, latest, server = self.e.doi, None, None
        for srv in ("biorxiv", "medrxiv"):
            j = self.http.fetch_json(f"{BIORXIV_API}/{srv}/{doi}")
            coll = [c for c in j.get("collection") or [] if (c.get("doi") or "").lower() == doi.lower()]
            if coll:
                latest, server = max(coll, key=lambda c: int(c.get("version") or 0)), srv
                break
        if latest is None:
            return "no record at api.biorxiv.org (bioRxiv, medRxiv)"
        v = latest.get("version")
        self.meta["ids"]["rxiv"] = {"server": server, "version": v, "date": latest.get("date"),
                                    "published_doi_not_fetched": latest.get("published")}
        self.title = self.title or norm_ws(latest.get("title")) or None
        self.year = self.year or (latest.get("date") or "")[:4] or None
        self.journal = self.journal or latest.get("server")
        self.authors = self.authors or norm_ws(latest.get("authors")) or None
        if not self.abstract and latest.get("abstract"):
            self.abstract, self.abstract_src = norm_ws(latest["abstract"]), f"{server} API"
        got = []
        if self.root is None and latest.get("jatsxml"):
            g = self.fetch(latest["jatsxml"], name=f"{server}_v{v}.source.xml", expect="xml")
            res = self.try_root(g.path, f"{server} JATS XML, version {v}", "rxiv")
            got.append("xml" if self.root_origin == "rxiv" else f"xml: {res}")
            final = g.info.get("final_url") or latest["jatsxml"]
            if self.root_origin == "rxiv":
                if final.endswith(".source.xml"):
                    got.append(self.rxiv_assets(final[: -len(".source.xml")]))
                else:
                    self.err(f"no asset base URL derivable from {final}")
        if self.pdf_rel is None:
            url = f"https://www.{server}.org/content/{doi}v{v}.full.pdf"
            try:
                g = self.fetch(url, name=f"{server}_v{v}.full.pdf", expect="pdf")
                self.set_main_pdf(g.path, f"{server} PDF, version {v}")
                got.append("pdf")
            except FetchError as e:
                self.ferr(e)
        return f"ok: {server} version {v}: " + ", ".join(got)

    def rxiv_assets(self, base: str) -> str:
        n_fig = n_fig_ok = n_supp = n_supp_ok = 0
        main = list(iter_main(article_of(self.root)))
        for fig in (e for e in main if lname(e.tag) == "fig"):
            hw = fig.get(HW_ID)
            g = next((x for x in fig.iter() if lname(x.tag) == "graphic" and href_of(x)), None)
            if not hw or g is None:
                continue
            n_fig += 1
            stem = href_key(href_of(g))
            try:
                got = self.fetch(f"{base}/{hw}.large.jpg", name=f"{stem}.jpg", expect="image")
            except FetchError as e:
                self.ferr(e)
                continue
            self.fig_files[stem] = self.place_image(got.path, "figures", stem)
            n_fig_ok += 1
        for sm in (e for e in main if lname(e.tag) == "supplementary-material"):
            hw = sm.get(HW_ID)
            for media in (x for x in sm.iter() if lname(x.tag) == "media" and href_of(x)):
                name = base_of(href_of(media))
                if ext_of(name) in MEDIA_EXT:
                    self.skip(name, None, "video or audio", None, register=True)
                    continue
                n_supp += 1
                mid = media.get(HW_ID) or media.get("id")  # HighWire ids: DCn on the element, media-n on the media
                if not hw or not mid:
                    self.err(f"no download address for supplementary file {name}")
                    continue
                url = f"{base}/{hw}/embed/{mid}{ext_of(name)}?download=true"
                try:
                    got = self.fetch(url, name=name, expect="nothtml")
                except FetchError as e:
                    self.ferr(e)
                    continue
                self.add_supp(got.path, name, "supp", 0, url)
                n_supp_ok += 1
        return f"{n_fig_ok}/{n_fig} figures, {n_supp_ok}/{n_supp} supplementary files"

    def r_europepmc_preprint(self) -> str:
        pid = self.rec.get("id")
        g = self.fetch(f"{EPMC_REST}/{pid}/fullTextXML", name=f"{pid}_europepmc.xml", expect="xml")
        return self.try_root(g.path, f"Europe PMC preprint full-text XML ({pid})", "epmc_preprint")

    def r_elife(self) -> str:
        m = re.match(r"10\.7554/elife\.(\d+)", self.e.doi, re.IGNORECASE)
        if not m:
            return "no eLife article number in the DOI"
        art = m.group(1)
        j = self.http.fetch_json(f"{ELIFE_API}/{art}")
        self.title = self.title or strip_tags(j.get("title") or "").replace("\n", " ") or None
        self.year = self.year or (j.get("published") or "")[:4] or None
        self.journal = self.journal or "eLife"
        got = []
        if self.root is None and j.get("xml"):
            g = self.fetch(j["xml"], expect="xml")
            res = self.try_root(g.path, f"eLife article XML ({j['xml']})", "elife")
            got.append("xml" if self.root_origin == "elife" else f"xml: {res}")
        if self.root_origin == "elife":
            iiif: dict[str, str] = {}  # figure key -> IIIF image URI, as the API gives them (the XML hrefs lack the .tif)

            def collect(o) -> None:
                if isinstance(o, dict):
                    u = o.get("uri")
                    if isinstance(u, str) and u.startswith(ELIFE_IIIF + "/") and "/full/" not in u:
                        iiif.setdefault(href_key(unquote(u.rsplit("/", 1)[-1])), u)
                    for v in o.values():
                        collect(v)
                elif isinstance(o, list):
                    for v in o:
                        collect(v)

            collect(j)
            n_fig = n_supp = 0
            for href, role in jats_files(self.root):
                name = base_of(href)
                if role == "figure":
                    stem = href_key(href)
                    tif = name if ext_of(name) in IMAGE_EXT else name + ".tif"
                    uri = iiif.get(stem) or f"{ELIFE_IIIF}/{art}%2F{quote(tif, safe='')}"
                    try:
                        g = self.fetch(f"{uri}/full/full/0/default.jpg", name=f"{stem}.jpg", expect="image")
                    except FetchError as e:
                        self.ferr(e)
                        continue
                    self.fig_files[stem] = self.place_image(g.path, "figures", stem)
                    n_fig += 1
                elif role == "video":
                    self.skip(name, None, "video or audio", None, register=True)
                elif role == "supp":
                    url = f"{ELIFE_CDN}/{art}/{quote(name, safe='')}"
                    try:
                        g = self.fetch(url, name=name, expect="nothtml")
                    except FetchError as e:
                        self.ferr(e)
                        continue
                    self.add_supp(g.path, name, "supp", 0, url)
                    n_supp += 1
            got.append(f"{n_fig} figures, {n_supp} supplementary files")
        if self.pdf_rel is None and j.get("pdf"):
            try:
                g = self.fetch(j["pdf"], expect="pdf")
                self.set_main_pdf(g.path, f"eLife PDF ({j['pdf']})")
                got.append("pdf")
            except FetchError as e:
                self.ferr(e)
        return "ok: " + (", ".join(got) or "nothing new")

    def r_crossref(self) -> str:
        j = self.http.fetch_json(f"{CROSSREF_API}/{quote(self.e.doi, safe='/')}")
        m = j.get("message") or {}
        got = []
        if not self.title and m.get("title"):
            self.title = strip_tags(m["title"][0]).replace("\n", " ")
            got.append("title")
        if not self.year:
            for k in ("issued", "published", "published-print", "published-online", "created"):
                parts = (m.get(k) or {}).get("date-parts") or [[None]]
                if parts and parts[0] and parts[0][0]:
                    self.year = str(parts[0][0])
                    got.append("year")
                    break
        self.journal = self.journal or ((m.get("container-title") or [None])[0])
        if not self.authors and m.get("author"):
            names = [" ".join(x for x in (a.get("family"), a.get("given")) if x) or a.get("name") or "" for a in m["author"]]
            self.authors = ", ".join(n for n in names if n) or None
        if not self.abstract and m.get("abstract"):
            self.abstract, self.abstract_src = strip_tags(m["abstract"]), "Crossref"
            got.append("abstract")
        licences = [x.get("URL") for x in m.get("license") or [] if x.get("URL")]
        if licences:
            self.meta["license_crossref"] = licences
        if self.root is None and self.pdf_rel is None:
            cands = []
            for x in m.get("link") or []:
                u, ct = x.get("URL") or "", (x.get("content-type") or "").lower()
                if u and ("pdf" in ct or u.lower().split("?")[0].endswith(".pdf")):
                    cands.append(("Crossref full-text link", u))
            for f in ((self.rec or {}).get("fullTextUrlList") or {}).get("fullTextUrl") or []:
                if f.get("documentStyle") == "pdf" and f.get("site") != "Europe_PMC" and f.get("url") and \
                        (f.get("availabilityCode") in ("OA", "F") or f.get("availability") in ("Open access", "Free")):
                    cands.append((f"Europe PMC full-text link ({f.get('site')})", f["url"]))
            for label, u in cands:
                host = (urlsplit(u).hostname or "").lower()
                if any(host == h or host.endswith("." + h) for h in KEY_REQUIRED_HOSTS):
                    self.meta.setdefault("links_not_tried_need_api_key", []).append(u)
                    continue
                try:
                    g = self.fetch(u, name="publisher.pdf", expect="pdf")
                except FetchError as e:
                    self.ferr(e)
                    continue
                self.set_main_pdf(g.path, f"{label}: {u}")
                got.append("pdf")
                break
            else:
                got.append(f"no open PDF among {len(cands)} full-text links")
        return "ok: " + (", ".join(got) or "nothing new")

    # -- the whole DOI
    def process(self) -> dict:
        t0, n0 = time.monotonic(), self.http.n
        shutil.rmtree(self.dir, ignore_errors=True)
        for d in ("figures", "supp", "pages"):
            (self.dir / d).mkdir(parents=True, exist_ok=True)
        doi, low = self.e.doi, self.e.doi.lower()
        self.route_name = "registry"
        if not re.match(r"^10\.\d{4,9}/\S+$", doi):
            self.err("not a DOI; nothing fetched")
        elif low.startswith(BANNED_DOI_PREFIXES):
            self.err("DOI of a banned host (Zenodo); nothing fetched")
            self.meta["banned_host"] = True
            self.meta["notes"].append("this DOI belongs to a banned host (Zenodo): do not fetch it, not even live")
        else:
            self.route("europepmc_search", self.r_europepmc_search)
            if self.pmcid:
                self.route("europepmc_fulltext", self.r_europepmc_fulltext)
                self.meta["routes_tried"].append({"route": "pmc_oa_fcgi", "result": "not tried: the PMC OA Web Service "
                                                  "was retired in August 2026; pmc_cloud is its replacement"})
                self.route("pmc_cloud", self.r_pmc_cloud)
            if low.startswith(RXIV_PREFIXES) and (self.root is None or self.pdf_rel is None):
                self.route("biorxiv", self.r_biorxiv)
            if self.root is None and self.rec and self.rec.get("source") == "PPR" and self.rec.get("inEPMC") == "Y":
                self.route("europepmc_preprint", self.r_europepmc_preprint)
            if low.startswith("10.7554/elife.") and (self.root is None or (self.pdf_rel is None and not self.fig_files)):
                self.route("elife", self.r_elife)
            if not self.title or not self.year or (self.root is None and self.pdf_rel is None):
                self.route("crossref", self.r_crossref)
        self.finish()
        self.meta.update({"n_requests": self.http.n - n0, "elapsed_s": round(time.monotonic() - t0, 1), "utc": utc_now()})
        self.finalize()
        return self.meta

    def finish(self) -> None:
        self.route_name = "finish"
        pdf_info, pdf_text = None, ""
        if self.pdf_rel:
            pdf_info, pdf_text = self.process_pdf(self.pdf_rel, self.unique_pdfname("article"))
        xml_text, stats = "", Counter()
        if self.root is not None:
            jt = JatsText(self.root, self.fig_lookup, self.supp_lookup)
            xml_text, stats = jt.render(), jt.stats
        n_p, n_c = stats["body_paragraphs"], stats["body_chars"]
        pages, pchars = (pdf_info["pages"], pdf_info["text_chars"]) if pdf_info else (0, 0)
        if self.root is not None and n_p >= MIN_XML_PARAGRAPHS and n_c >= MIN_XML_CHARS:
            status, mode, source = "full_text", "xml", self.root_label
        elif pchars >= MIN_PDF_CHARS and pages >= MIN_PDF_PAGES:
            status, mode, source = "full_text", "pdf", f"text extracted from article.pdf ({self.pdf_label})"
        elif self.abstract:
            status, mode, source = "abstract_only", "abstract", f"abstract only ({self.abstract_src})"
        else:
            status, mode, source = "unreachable", "none", None
        if pdf_info and pages and pchars < MIN_PDF_CHARS and mode != "xml":
            self.meta["notes"].append(f"article.pdf has {pages} pages but only {pchars} characters of text (scanned?): read its page images")
        if pdf_text and mode != "pdf":
            pdf_info["text_file"] = self.write_text_file(
                "supp/article.txt", f"Text extracted mechanically from article.pdf (the article PDF), page by page.\n\n{pdf_text}")
        elif mode == "pdf":
            pdf_info["text_file"] = "text.txt"
        if self.pdf_rel and not self.fig_files and status == "full_text":
            n = self.extract_pdf_images()
            if n:
                self.meta["notes"].append(f"figures/ holds {n} raster images extracted from article.pdf (no separate figure "
                                          "files were available); vector graphics appear only in the page images")
        if mode == "xml":
            self.place(self.root_path, "fulltext.xml")
        authors = self.authors if not self.authors or len(self.authors) <= 600 else self.authors[:600].rsplit(",", 1)[0] + ", et al."
        self.meta.update({"status": status, "title": self.title or self.e.title or None, "year": self.year, "authors": authors,
                          "journal": self.journal})
        self.meta["fulltext"] = {
            "rule": STATUS_RULE, "text_source": source, "xml_source": self.root_label, "xml_body_paragraphs": n_p,
            "xml_body_chars": n_c, "xml_counts": xml_counts(self.root) if self.root is not None else None,
            "rendered": dict(stats), "pdf_source": self.pdf_label, "pdf_pages": pages, "pdf_text_chars": pchars,
            "abstract_source": self.abstract_src,
        }
        head = []
        if status == "abstract_only":
            head.append("ABSTRACT ONLY")
        elif status == "unreachable":
            head.append("UNREACHABLE: neither a full text nor an abstract could be downloaded (see meta.json, errors)")
        head.append(f"DOI: {self.e.doi}")
        for k, v in (("TITLE", self.meta["title"]), ("AUTHORS", authors), ("YEAR", self.year), ("JOURNAL", self.journal),
                     ("TEXT SOURCE", source)):
            if v:
                head.append(f"{k}: {v}")
        body = ""
        if mode == "xml":
            body = xml_text
        elif mode == "pdf":
            ab = f"## Abstract ({self.abstract_src})\n\n{self.abstract}\n\n" if self.abstract else ""
            body = f"{ab}## Text of article.pdf ([page N] marks the start of page N)\n\n{pdf_text}"
        elif self.abstract:
            body = f"## Abstract\n\n{self.abstract}\n"
        notes = "".join(f"NOTE: {n}\n" for n in self.meta["notes"])
        text = "\n".join(head) + "\n\n" + (notes + "\n" if notes else "") + body.strip() + "\n\n" + self.files_index(pdf_info)
        self.write_text_file("text.txt", text)

    def files_index(self, pdf_info) -> str:
        files = sorted(p.relative_to(self.dir).as_posix() for p in self.dir.rglob("*") if p.is_file())
        files = [f for f in files if not f.startswith(".tmp/")]
        size = lambda f: human((self.dir / f).stat().st_size)
        lines = ["== FILES IN THIS FOLDER (paths relative to this folder) ==", "text.txt: this file"]
        if "article.pdf" in files and pdf_info:
            lines.append(f"article.pdf ({size('article.pdf')}): the article PDF, {pdf_info['pages']} pages; page images "
                         f"{pdf_info['page_images']} ({pdf_info['rendered']} images); its text: {pdf_info['text_file'] or 'none'}")
        if "fulltext.xml" in files:
            lines.append(f"fulltext.xml ({size('fulltext.xml')}): the XML this text was made from")
        figs = [f for f in files if f.startswith("figures/")]
        lines.append(f"figures/ ({len(figs)} images)" + (": " + ", ".join(f[8:] for f in figs) if figs else ""))
        supp = [f for f in files if f.startswith("supp/")]
        lines.append(f"supp/ ({len(supp)} files)" + (":" if supp else ""))
        lines += [f"  {f} ({size(f)})" for f in supp[:300]]
        if len(supp) > 300:
            lines.append(f"  ... and {len(supp) - 300} more (meta.json lists every file)")
        pages = Counter(m.group(1) for f in files if (m := re.match(r"pages/(.+)_p\d{3,}\.png$", f)))
        lines.append(f"pages/ ({sum(pages.values())} page images)" + (": " + ", ".join(f"{k}_pNNN.png x{v}" for k, v in pages.items()) if pages else ""))
        if self.meta["skipped"]:
            lines.append(f"not downloaded or not kept ({len(self.meta['skipped'])}):")
            lines += [f"  {s['name']} ({human(s['bytes'])}): {s['reason']}" for s in self.meta["skipped"][:200]]
        return "\n".join(lines) + "\n"

    def finalize(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.meta["files"] = [{"path": p.relative_to(self.dir).as_posix(), "bytes": p.stat().st_size, "sha256": sha256_file(p)}
                              for p in sorted(self.dir.rglob("*")) if p.is_file() and p.name != "meta.json"]
        (self.dir / "meta.json").write_text(json.dumps(self.meta, indent=1, ensure_ascii=False) + "\n", encoding="utf-8",
                                            newline="\n")
        final = self.run.out / self.e.slug
        if final.exists():
            trash = self.run.out / ".trash" / f"{self.e.slug}-{os.getpid()}-{time.time_ns()}"
            trash.parent.mkdir(parents=True, exist_ok=True)
            os.replace(final, trash)
            os.replace(self.dir, final)
            shutil.rmtree(trash, ignore_errors=True)
        else:
            os.replace(self.dir, final)


# ------------------------------------------------------------------------------------------------------------------- main
def is_complete(out: Path, e: Entry) -> bool:
    try:
        m = json.loads((out / e.slug / "meta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if (m.get("doi") or "").lower() != e.doi.lower():
        return False
    if str(m.get("script_version", "")).split(".")[0] != SCRIPT_VERSION.split(".")[0]:
        return False
    if any(x.get("transient") for x in m.get("errors", [])):
        return False
    for f in m.get("files", []):
        p = out / e.slug / f["path"]
        if not p.is_file() or p.stat().st_size != f["bytes"]:
            return False
    return True


def write_manifest(path: Path, entries: list[Entry], out: Path, registry: dict) -> dict:
    slugs = {e.doi: e.slug for e in entries}
    try:  # DOIs of an earlier registry stay listed while their folders exist
        prev = json.loads(path.read_text(encoding="utf-8")).get("dois", {})
    except (OSError, ValueError):
        prev = {}
    known = {d.lower() for d in slugs}
    for doi, ent in prev.items():
        if doi.lower() not in known and isinstance(ent, dict) and ent.get("slug"):
            slugs[doi] = ent["slug"]
    dois = {}
    for doi, slug in slugs.items():
        mp = out / slug / "meta.json"
        try:
            m = json.loads(mp.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if (m.get("doi") or "").lower() != doi.lower():
            continue
        files = {f["path"]: f["sha256"] for f in m.get("files", [])}
        files["meta.json"] = sha256_file(mp)
        dois[doi] = {"slug": slug, "status": m.get("status"), "n_files": len(files), "files": files}
    man = {"script": "ledger/scripts/labels2_download.py", "script_version": SCRIPT_VERSION, "utc": utc_now(),
           "registry": registry, "summary": dict(Counter(v["status"] for v in dois.values())),
           "dois": dict(sorted(dois.items(), key=lambda kv: kv[0].lower()))}
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(man, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, path)
    return man


def parse_args(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--registry", required=True, help="CSV with a doi column (optional slug, title)")
    ap.add_argument("--out", required=True, help="output directory; one folder per DOI")
    ap.add_argument("--manifest", required=True, help="MANIFEST.json to write")
    ap.add_argument("--only", nargs="+", metavar="DOI", help="process only these registry DOIs")
    ap.add_argument("--log", help="append a detailed log (every request, every failure) to this file")
    ap.add_argument("--force", action="store_true", help="redo DOIs that are already complete")
    ap.add_argument("--refetch", action="store_true", help="ignore the download cache (.raw) for the DOIs processed")
    ap.add_argument("--skip-route", nargs="+", default=[], choices=ROUTES, metavar="ROUTE",
                    help=f"testing aid: do not use these routes ({', '.join(ROUTES)})")
    ap.add_argument("--dpi", type=int, default=150, help="page-image resolution (default 150: 6-pt figure text stays legible)")
    ap.add_argument("--max-pages", type=int, default=300, help="page images per PDF at most (text: every page)")
    ap.add_argument("--max-file-mb", type=float, default=500, help="largest single download or archive member")
    ap.add_argument("--max-keep-mb", type=float, default=25, help="largest non-convertible binary file kept as it is")
    ap.add_argument("--max-archive-mb", type=float, default=3000, help="most bytes expanded from one archive")
    ap.add_argument("--max-csv-mb", type=float, default=100, help="largest CSV written per sheet")
    ap.add_argument("--max-rps", type=float, default=3.0, help="requests per second overall, at most 3")
    ap.add_argument("--retries", type=int, default=4, help="retries per request on 429 / 5xx / network errors")
    ap.add_argument("--max-wait", type=float, default=300, help="longest Retry-After honoured, seconds")
    ap.add_argument("--version", action="version", version=SCRIPT_VERSION)
    a = ap.parse_args(argv)
    a.max_rps = min(max(a.max_rps, 0.05), 3.0)
    a.retries = min(max(a.retries, 0), 6)
    a.max_file_bytes = int(a.max_file_mb * 1e6)
    a.max_keep_bytes = int(a.max_keep_mb * 1e6)
    a.max_archive_bytes = int(a.max_archive_mb * 1e6)
    a.max_csv_bytes = int(a.max_csv_mb * 1e6)
    return a


def setup_logging(path: str | None) -> None:
    fmt = logging.Formatter("%(asctime)sZ %(levelname)s %(message)s", "%Y-%m-%dT%H:%M:%S")
    fmt.converter = time.gmtime
    log.setLevel(logging.DEBUG)
    log.propagate = False
    sh = logging.StreamHandler(sys.stderr)
    sh.setLevel(logging.INFO)
    sh.setFormatter(fmt)
    log.addHandler(sh)
    if path:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(path, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        log.addHandler(fh)


def main(argv=None) -> int:
    args = parse_args(argv)
    setup_logging(args.log)
    if pymupdf is None or openpyxl is None:
        log.error("PyMuPDF and openpyxl are required: uv run --project ledger --no-sync --with pymupdf==1.25.5 "
                  "--with openpyxl==3.1.5 --with xlrd==2.0.1 python ledger/scripts/labels2_download.py ...")
        return 2
    try:
        pymupdf.TOOLS.mupdf_display_errors(False)
    except Exception:
        pass
    registry = Path(args.registry)
    entries = load_registry(registry)
    selected = entries
    if args.only:
        want = {norm_doi(d).lower() for d in args.only}
        selected = [e for e in entries if e.doi.lower() in want]
        for d in sorted(want - {e.doi.lower() for e in selected}):
            log.warning("--only %s: not in the registry; ignored", d)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / ".lock", "w") as lock:
        try:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except ImportError:  # no fcntl (Windows): no lock
            pass
        except OSError:
            log.error("another run is using %s", out)
            return 2
        return run_all(args, entries, selected, out, registry)


def run_all(args, entries: list[Entry], selected: list[Entry], out: Path, registry: Path) -> int:
    http = Http(args.max_rps, args.retries + 1, args.max_wait)
    run = Run(args, out, http, RawCache(out / ".raw", http, args.refetch))
    reg_info = {"file": registry.name, "sha256": sha256_file(registry), "n_dois": len(entries)}
    log.info("labels2_download %s: %d registry DOIs, %d selected, out %s", SCRIPT_VERSION, len(entries), len(selected), out)
    t0, counts, crashed = time.monotonic(), Counter(), []
    for i, e in enumerate(selected, 1):
        if not args.force and is_complete(out, e):
            counts["already_complete"] += 1
            log.info("[%d/%d] %s: complete, skipped", i, len(selected), e.doi)
            continue
        log.info("[%d/%d] %s -> %s/", i, len(selected), e.doi, e.slug)
        try:
            meta = Paper(e, run).process()
        except KeyboardInterrupt:
            raise
        except Exception:
            log.exception("%s crashed; its output folder is left as it was", e.doi)
            crashed.append(e.doi)
            continue
        counts[meta["status"]] += 1
        log.info("[%d/%d] %s: %s, %d files, %d requests, %.0f s", i, len(selected), e.doi, meta["status"],
                 len(meta["files"]), meta["n_requests"], meta["elapsed_s"])
        write_manifest(Path(args.manifest), entries, out, reg_info)
    man = write_manifest(Path(args.manifest), entries, out, reg_info)
    log.info("done in %.0f s: this run %s; manifest %s; %d requests, %d cache hits%s", time.monotonic() - t0, dict(counts),
             man["summary"], http.n, run.cache.hits, f"; CRASHED: {crashed}" if crashed else "")
    return 1 if crashed else 0


if __name__ == "__main__":
    sys.exit(main())
