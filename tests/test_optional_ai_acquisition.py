"""Offline tests for the CI-only canonical wheel trust boundary."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import ssl
import sys
import urllib.error
import urllib.response
import zipfile
from email.message import Message
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/acquire-optional-ai.py"


@pytest.fixture
def acquisition():
    spec = importlib.util.spec_from_file_location("acquire_optional_ai", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def wheel(*, metadata=None, metadata_path=None) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr(
            metadata_path or "giadaware_ai-0.0.2.dist-info/METADATA",
            metadata
            or "Name: giadaware-ai\nVersion: 0.0.2\nRequires-Python: >=3.11\n"
            'Requires-Dist: build>=1.2; extra == "dev"\n',
        )
    return output.getvalue()


def serve(monkeypatch, acquisition, data, *, status=200, url=None):
    response = Mock()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.status = status
    response.geturl.return_value = acquisition.URL if url is None else url
    response.read.return_value = data
    opener = Mock(return_value=response)
    monkeypatch.setattr(
        acquisition.urllib.request,
        "build_opener",
        Mock(return_value=SimpleNamespace(open=opener)),
    )
    return opener, response


def test_reviewed_release_pin_is_exact(acquisition):
    assert acquisition.URL == (
        "https://github.com/gcomneno/giadaware-ai/releases/download/v0.0.2/"
        "giadaware_ai-0.0.2-py3-none-any.whl"
    )
    assert acquisition.SHA256 == (
        "9c0951244f1f43f0b27f6dc4ae3c69150d0c8588f6ac099cbe47ae11e21ed0a2"
    )


def test_download_authenticates_before_publishing(monkeypatch, tmp_path, acquisition):
    data = wheel()
    monkeypatch.setattr(acquisition, "SHA256", hashlib.sha256(data).hexdigest())
    opener, response = serve(monkeypatch, acquisition, data)
    directory = tmp_path / "fresh"
    destination = acquisition.acquire(directory)
    assert destination == directory / acquisition.WHEEL
    assert destination.read_bytes() == data
    opener.assert_called_once_with(acquisition.URL, timeout=60)
    response.read.assert_called_once_with(acquisition.MAX_BYTES + 1)


@pytest.mark.parametrize(
    "url", ["http://example.invalid", "//example.invalid", "ftp://example.invalid"]
)
def test_initial_url_requires_https(monkeypatch, tmp_path, acquisition, url):
    opener, _ = serve(monkeypatch, acquisition, b"unused")
    monkeypatch.setattr(acquisition, "URL", url)
    with pytest.raises(ValueError, match="requires HTTPS"):
        acquisition.acquire(tmp_path)
    opener.assert_not_called()
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("code", [301, 302, 303, 307, 308])
@pytest.mark.parametrize(
    "target,accepted",
    [
        ("https://assets.example.invalid/wheel", True),
        ("//assets.example.invalid/wheel", True),
        ("/wheel", True),
        ("http://assets.example.invalid/wheel", False),
        ("ftp://assets.example.invalid/wheel", False),
        ("file:///wheel", False),
        ("data:application/zip,untrusted", False),
    ],
)
def test_redirect_transport_policy(
    monkeypatch, tmp_path, acquisition, code, target, accepted
):
    data = wheel()
    monkeypatch.setattr(acquisition, "SHA256", hashlib.sha256(data).hexdigest())
    intermediate = "https://redirect.example.invalid/start"
    final = acquisition.urllib.parse.urljoin(intermediate, target)
    visited = []

    class Transport(
        acquisition.urllib.request.HTTPSHandler, acquisition.urllib.request.HTTPHandler
    ):
        def https_open(self, request):
            visited.append(request.full_url)
            headers = Message()
            status = 200
            if request.full_url in (acquisition.URL, intermediate):
                status = code
                headers["Location"] = intermediate if len(visited) == 1 else target
            elif request.type == "http":
                status = code
                headers["Location"] = "https://assets.example.invalid/wheel"
            response = urllib.response.addinfourl(
                io.BytesIO(data), headers, request.full_url, status
            )
            response.msg = "OK" if status == 200 else "Redirect"
            return response

        http_open = https_open

    build_opener = acquisition.urllib.request.build_opener
    monkeypatch.setattr(
        acquisition.urllib.request,
        "build_opener",
        lambda policy: build_opener(policy, Transport()),
    )
    if accepted:
        assert acquisition.acquire(tmp_path).read_bytes() == data
        assert visited == [acquisition.URL, intermediate, final]
    else:
        # Even if the HTTP endpoint would redirect back to HTTPS, never reach it.
        with pytest.raises((ValueError, urllib.error.HTTPError)):
            acquisition.acquire(tmp_path)
        assert visited == [acquisition.URL, intermediate]
        assert list(tmp_path.iterdir()) == []


def test_protocol_relative_redirect_from_http_is_rejected(acquisition):
    request = acquisition.urllib.request.Request("http://example.invalid/start")
    with pytest.raises(ValueError, match="redirects require HTTPS"):
        acquisition.HTTPSOnlyRedirectHandler().redirect_request(
            request, None, 302, "Redirect", Message(), "//assets.example.invalid/wheel"
        )


def test_digest_rejected_before_archive_parse(monkeypatch, tmp_path, acquisition):
    serve(monkeypatch, acquisition, b"corrupt or historical local wheel")
    parser = Mock(side_effect=AssertionError("Unverified archive opened"))
    monkeypatch.setattr(acquisition.zipfile, "ZipFile", parser)
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        acquisition.acquire(tmp_path)
    parser.assert_not_called()
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "error",
    [
        urllib.error.URLError("offline"),
        urllib.error.URLError(ssl.SSLCertVerificationError("untrusted certificate")),
        urllib.error.HTTPError("https://example.invalid", 404, "missing", {}, None),
        TimeoutError("timeout"),
        OSError("read interrupted"),
    ],
)
def test_download_failure_has_no_fallback_or_output(
    monkeypatch, tmp_path, acquisition, error
):
    opener = Mock(side_effect=error)
    monkeypatch.setattr(
        acquisition.urllib.request,
        "build_opener",
        Mock(return_value=SimpleNamespace(open=opener)),
    )
    with pytest.raises(type(error)):
        acquisition.acquire(tmp_path)
    opener.assert_called_once_with(acquisition.URL, timeout=60)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "options,message",
    [
        ({"status": 404}, "download failed"),
        ({"url": "http://example.invalid/wheel"}, "download failed"),
        ({"url": "ftp://example.invalid/wheel"}, "download failed"),
        ({"url": "//example.invalid/wheel"}, "download failed"),
        ({"data": b"x" * (1024 * 1024 + 1)}, "size limit"),
    ],
)
def test_bad_download_response_is_not_published(
    monkeypatch, tmp_path, acquisition, options, message
):
    serve(monkeypatch, acquisition, **{"data": b"untrusted", **options})
    with pytest.raises(ValueError, match=message):
        acquisition.acquire(tmp_path)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "changes,message",
    [
        ({"metadata_path": "other-0.0.2.dist-info/METADATA"}, "identity"),
        ({"metadata": "Name: other\nVersion: 0.0.2\n"}, "Name"),
        ({"metadata": "Name: giadaware-ai\nVersion: 0.0.1\n"}, "Version"),
        ({"metadata": "Name: giadaware-ai\nVersion: 0.0.2\n"}, "Requires-Python"),
        (
            {"metadata": "Name: giadaware-ai\nName: giadaware-ai\nVersion: 0.0.2\n"},
            "Name",
        ),
        (
            {
                "metadata": "Name: giadaware-ai\nVersion: 0.0.2\n"
                "Requires-Python: >=3.11\nRequires-Dist: unapproved\n"
            },
            "dependency resolution",
        ),
    ],
)
def test_authenticated_but_wrong_metadata_fails_closed(
    monkeypatch, tmp_path, acquisition, changes, message
):
    data = wheel(**changes)
    monkeypatch.setattr(acquisition, "SHA256", hashlib.sha256(data).hexdigest())
    serve(monkeypatch, acquisition, data)
    with pytest.raises(ValueError, match=message):
        acquisition.acquire(tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_malformed_archive_fails_closed(monkeypatch, tmp_path, acquisition):
    data = b"not a zip"
    monkeypatch.setattr(acquisition, "SHA256", hashlib.sha256(data).hexdigest())
    serve(monkeypatch, acquisition, data)
    with pytest.raises(zipfile.BadZipFile):
        acquisition.acquire(tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_existing_output_is_never_overwritten(monkeypatch, tmp_path, acquisition):
    target = tmp_path / acquisition.WHEEL
    target.write_bytes(b"protected")
    opener, _ = serve(monkeypatch, acquisition, b"unused")
    with pytest.raises(ValueError, match="overwrite"):
        acquisition.acquire(tmp_path)
    assert target.read_bytes() == b"protected"
    opener.assert_not_called()


@pytest.mark.parametrize("mode", ["canonical", "local", "version", "name", "shadow"])
def test_installed_identity_requires_canonical_archive_provenance(
    monkeypatch, tmp_path, acquisition, mode
):
    metadata = Message()
    metadata["Name"] = "other" if mode == "name" else "giadaware-ai"
    direct_url = (
        {"archive_info": {"hashes": {"sha256": acquisition.SHA256}}}
        if mode != "local"
        else {"dir_info": {"editable": True}}
    )
    distribution = SimpleNamespace(
        metadata=metadata,
        version="0.0.1" if mode == "version" else "0.0.2",
        read_text=lambda name: json.dumps(direct_url),
        locate_file=lambda name: tmp_path / name,
    )
    monkeypatch.setattr(
        acquisition.importlib.metadata, "distribution", lambda name: distribution
    )
    monkeypatch.setattr(
        acquisition.importlib.util,
        "find_spec",
        lambda name: SimpleNamespace(
            origin=str(
                tmp_path
                / ("shadow.py" if mode == "shadow" else "giadaware_ai/__init__.py")
            )
        ),
    )
    if mode == "canonical":
        acquisition.verify_installed()
    else:
        with pytest.raises(ValueError):
            acquisition.verify_installed()


def test_cli_failure_is_nonzero(monkeypatch, acquisition, capsys):
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "verify-installed"])
    monkeypatch.setattr(
        acquisition, "verify_installed", Mock(side_effect=ValueError("invalid"))
    )
    with pytest.raises(SystemExit) as caught:
        acquisition.main()
    assert caught.value.code == 1
    assert "Optional-AI qualification failed: invalid" in capsys.readouterr().err
