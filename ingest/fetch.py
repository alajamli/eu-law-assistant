"""Download and cache the raw legal texts.

Two rules, both learned the hard way:

1. Ask for `application/xhtml+xml` with an `Accept-Language`. Requesting
   `text/html` from the Cellar endpoint returns 404.
2. Validate the payload before caching it. A firewall challenge page is a valid
   200/202 response with an empty or tiny body; caching it silently produces an
   empty corpus and an eval run that "works" with zero chunks.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ingest.models import Source

USER_AGENT = "eu-law-assistant/0.1 (research project; contact: alajamli61@gmail.com)"
RAW_DIR = Path("data/raw")
MIN_BYTES = 5_000
MIN_ARTICLES = 5


class InvalidPayload(RuntimeError):
    """The server answered, but not with a legal document."""


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def headers_for(source: Source) -> dict[str, str]:
    return {
        "User-Agent": USER_AGENT,
        "Accept": "application/xhtml+xml",
        "Accept-Language": "fra" if source.lang.lower() == "fr" else "eng",
    }


@retry(
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=20),
    reraise=True,
)
def _get(source: Source) -> httpx.Response:
    with httpx.Client(timeout=90.0, follow_redirects=True, headers=headers_for(source)) as client:
        response = client.get(source.url)
        response.raise_for_status()
        return response


def validate(text: str, source: Source) -> None:
    if len(text) < MIN_BYTES:
        raise InvalidPayload(
            f"{source.slug}/{source.lang}: only {len(text)} bytes returned — "
            "likely a firewall challenge page rather than a document"
        )
    if "eli-subdivision" not in text:
        raise InvalidPayload(
            f"{source.slug}/{source.lang}: no ELI markup found — refusing to cache an unusable document"
        )
    if text.count('class="eli-subdivision"') < MIN_ARTICLES:
        raise InvalidPayload(f"{source.slug}/{source.lang}: fewer than {MIN_ARTICLES} subdivisions")


def target_path(source: Source, raw_dir: Path = RAW_DIR) -> Path:
    return raw_dir / f"{source.slug}_{source.lang.lower()}.xhtml"


def fetch(source: Source, raw_dir: Path = RAW_DIR, force: bool = False) -> tuple[Path, str]:
    """Return (cached file path, sha256). Downloads only when needed."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = target_path(source, raw_dir)
    if path.exists() and not force and path.stat().st_size >= MIN_BYTES:
        return path, sha256_of(path)

    response = _get(source)
    text = response.text
    validate(text, source)
    path.write_text(text, encoding="utf-8")
    return path, sha256_of(path)
