#!/usr/bin/env python3
"""Acquire the qualified GitHub wheel for CI; never resolve an AI package index.

This is explicit build/test tooling, not an application runtime download path.
The reviewed digest is the trust anchor, including for mutable release assets.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import io
import json
import sys
import urllib.parse
import urllib.request
import zipfile
from email.parser import BytesParser
from pathlib import Path

VERSION = "0.0.2"
WHEEL = "giadaware_ai-0.0.2-py3-none-any.whl"
SHA256 = "9c0951244f1f43f0b27f6dc4ae3c69150d0c8588f6ac099cbe47ae11e21ed0a2"
URL = f"https://github.com/gcomneno/giadaware-ai/releases/download/v{VERSION}/{WHEEL}"
MAX_BYTES = 1024 * 1024


def validate_wheel(data: bytes) -> None:
    # Authenticate bytes BEFORE opening the archive or trusting its metadata.
    if hashlib.sha256(data).hexdigest() != SHA256:
        raise ValueError("Canonical GiadaWare AI wheel SHA-256 mismatch")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        metadata_path = f"giadaware_ai-{VERSION}.dist-info/METADATA"
        names = archive.namelist()
        if [name for name in names if name.endswith(".dist-info/METADATA")] != [
            metadata_path
        ]:
            raise ValueError("Unexpected wheel distribution identity")
        metadata = BytesParser().parsebytes(archive.read(metadata_path))
    for field, expected in (
        ("Name", "giadaware-ai"),
        ("Version", VERSION),
        ("Requires-Python", ">=3.11"),
    ):
        if metadata.get_all(field) != [expected]:
            raise ValueError(f"Unexpected wheel {field}")
    # The qualified wheel declares build tooling only for its unused dev extra.
    if metadata.get_all("Requires-Dist") != ['build>=1.2; extra == "dev"']:
        raise ValueError(
            "Unexpected wheel dependencies; no dependency resolution allowed"
        )


class HTTPSOnlyRedirectHandler(urllib.request.HTTPRedirectHandler):
    # Python 3.10 does not register a handler for permanent 308 redirects.
    http_error_308 = urllib.request.HTTPRedirectHandler.http_error_302

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urllib.parse.urljoin(req.full_url, newurl)
        if urllib.parse.urlsplit(target).scheme != "https":
            raise ValueError("Canonical wheel redirects require HTTPS")
        # 308 has the same method policy as 307, supported by Python 3.10.
        if code == 308:
            code = 307
        return super().redirect_request(req, fp, code, msg, headers, target)


def acquire(directory: Path) -> Path:
    # No glob/asset enumeration: historical local-superseded-* files cannot win.
    destination = directory / WHEEL
    if destination.exists() or destination.is_symlink():
        raise ValueError("Refusing to overwrite an existing wheel")
    if urllib.parse.urlsplit(URL).scheme != "https":
        raise ValueError("Canonical wheel URL requires HTTPS")
    opener = urllib.request.build_opener(HTTPSOnlyRedirectHandler())
    with opener.open(URL, timeout=60) as response:
        if (
            response.status != 200
            or urllib.parse.urlsplit(response.geturl()).scheme != "https"
        ):
            raise ValueError("Canonical wheel download failed")
        data = response.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("Canonical wheel download exceeds size limit")
    validate_wheel(data)
    directory.mkdir(parents=True, exist_ok=True)
    # Publish only completely downloaded, authenticated bytes. Never reuse caches.
    with destination.open("xb") as stream:
        stream.write(data)
    return destination


def verify_installed() -> None:
    distribution = importlib.metadata.distribution("giadaware-ai")
    if (
        distribution.metadata.get_all("Name") != ["giadaware-ai"]
        or distribution.version != VERSION
    ):
        raise ValueError("Installed GiadaWare AI identity/version mismatch")
    # Version alone cannot distinguish the historical local 0.0.2 wheel.
    direct_url = json.loads(distribution.read_text("direct_url.json") or "null")
    if (
        not isinstance(direct_url, dict)
        or direct_url.get("archive_info", {}).get("hashes", {}).get("sha256") != SHA256
    ):
        raise ValueError("Installed GiadaWare AI lacks canonical wheel provenance")
    spec = importlib.util.find_spec("giadaware_ai")
    expected = Path(distribution.locate_file("giadaware_ai/__init__.py")).resolve()
    if spec is None or spec.origin is None or Path(spec.origin).resolve() != expected:
        raise ValueError("GiadaWare AI import is shadowed or missing")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    download = commands.add_parser("download")
    download.add_argument("directory", type=Path)
    commands.add_parser("verify-installed")
    arguments = parser.parse_args()
    try:
        if arguments.command == "download":
            print(acquire(arguments.directory))
        else:
            verify_installed()
            print(f"Verified installed giadaware-ai=={VERSION} from {SHA256}")
    except Exception as exc:
        print(f"Optional-AI qualification failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
