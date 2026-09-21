"""HTTP cancellation/send failures close only the response's pinned handles."""

import asyncio
import os
from types import SimpleNamespace

import pytest
from ktem.index.file.download_http import _byte_range, _DownloadResponse

from kotaemon.artifact_transfers import DownloadTransfer


@pytest.mark.parametrize("failure", ["start", "body", "disconnect", None])
def test_http_response_releases_transfer_on_every_exit(tmp_path, failure):
    path = tmp_path / "payload"
    path.write_bytes(b"owned transport")
    descriptor = os.open(path, os.O_RDONLY)
    marker = os.open(tmp_path / "ready", os.O_CREAT | os.O_RDWR, 0o600)
    borrowed = os.open(tmp_path / "borrowed", os.O_CREAT | os.O_RDWR, 0o600)
    transfer = DownloadTransfer(
        descriptor, marker, path.stat().st_size, "download.html"
    )
    response = _DownloadResponse(transfer, SimpleNamespace(method="GET", headers={}))
    sent = []

    async def receive():
        if failure == "disconnect":
            return {"type": "http.disconnect"}
        await asyncio.Event().wait()

    async def send(message):
        sent.append(message)
        if (failure == "start" and message["type"] == "http.response.start") or (
            failure == "body" and message["type"] == "http.response.body"
        ):
            raise OSError("controlled send failure")

    try:
        if failure in {"start", "body"}:
            with pytest.raises(BaseException):
                asyncio.run(response({"type": "http"}, receive, send))
        else:
            asyncio.run(response({"type": "http"}, receive, send))
        for fd in (descriptor, marker):
            with pytest.raises(OSError):
                os.fstat(fd)
        transfer.close()
        assert os.fstat(borrowed)
        if failure is None:
            assert (
                b"".join(item.get("body", b"") for item in sent) == b"owned transport"
            )
    finally:
        os.close(borrowed)
        transfer.close()


@pytest.mark.parametrize(
    "value",
    ["bytes=", "bytes=3-2", "bytes=-0", "bytes=0-1,2-3", "bytes=99-", "text=0-1"],
)
def test_invalid_ranges_do_not_start_streaming(value):
    with pytest.raises(ValueError):
        _byte_range(value, 5)


@pytest.mark.parametrize(
    "value,expected",
    [
        ("bytes=-2", (3, 4, True)),
        ("bytes=3-", (3, 4, True)),
        ("bytes=1-90", (1, 4, True)),
        (None, (0, 4, False)),
    ],
)
def test_supported_single_ranges(value, expected):
    assert _byte_range(value, 5) == expected
