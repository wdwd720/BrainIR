"""Download machinery tested offline with a fake HTTP session (ranges, resume, corruption)."""

from __future__ import annotations

import json

import pytest

from brainir import acquire
from brainir.acquire import IntegrityError, _download_ranges


class FakeResponse:
    def __init__(self, status, content):
        self.status_code = status
        self.content = content


class FakeSession:
    """Serves byte ranges of an in-memory payload; optionally corrupts or fails some chunks."""

    def __init__(self, payload: bytes, fail_first: set[int] | None = None, short: bool = False):
        self.payload = payload
        self.calls: list[tuple[int, int]] = []
        self.fail_first = set(fail_first or ())
        self.short = short

    def get(self, url, headers=None, timeout=None):
        rng = headers["Range"].split("=")[1]
        start, end = (int(x) for x in rng.split("-"))
        self.calls.append((start, end))
        if start in self.fail_first:
            self.fail_first.discard(start)
            return FakeResponse(503, b"")
        data = self.payload[start:end + 1]
        if self.short:
            data = data[:-1]
        return FakeResponse(206, data)


@pytest.fixture
def small_chunks(monkeypatch):
    monkeypatch.setattr(acquire, "CHUNK_BYTES", 1000)
    monkeypatch.setattr(acquire.time, "sleep", lambda s: None)


def test_parallel_ranged_download_reassembles_exact_bytes(tmp_path, monkeypatch, small_chunks):
    payload = bytes(range(256)) * 37  # 9472 bytes -> 10 chunks
    fake = FakeSession(payload, fail_first={3000})  # one transient failure is retried
    monkeypatch.setattr(acquire, "_session", lambda: fake)
    part = tmp_path / "f.partial"
    _download_ranges("https://example/f", part, len(payload), n_threads=4)
    assert part.read_bytes() == payload
    assert not (tmp_path / "f.partial.parts.json").exists()


def test_resume_skips_completed_chunks(tmp_path, monkeypatch, small_chunks):
    payload = b"x" * 5000
    part = tmp_path / "f.partial"
    part.write_bytes(payload[:2000] + b"\0" * 3000)  # chunks 0,1 already done
    (tmp_path / "f.partial.parts.json").write_text(json.dumps({"size": 5000, "chunk_bytes": 1000, "done": [0, 1]}))
    fake = FakeSession(payload)
    monkeypatch.setattr(acquire, "_session", lambda: fake)
    _download_ranges("https://example/f", part, 5000, n_threads=2)
    assert part.read_bytes() == payload
    assert sorted(s for s, _ in fake.calls) == [2000, 3000, 4000]


def test_short_reads_are_rejected(tmp_path, monkeypatch, small_chunks):
    fake = FakeSession(b"y" * 3000, short=True)
    monkeypatch.setattr(acquire, "_session", lambda: fake)
    with pytest.raises(IntegrityError):
        _download_ranges("https://example/f", tmp_path / "g.partial", 3000, n_threads=1)
