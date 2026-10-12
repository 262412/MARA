"""Wheel smoke sitecustomize: permit only the explicitly owned vector service."""

import os
import socket
from urllib.parse import urlsplit

service = urlsplit(os.environ.get("MARA_TEST_QDRANT_URL", ""))
allowed = None
if service.hostname in {"127.0.0.1", "::1"} and service.port:
    allowed = (service.hostname, service.port)


class OfflineSocket(socket.socket):
    def connect(self, address):
        if allowed is None or address[:2] != allowed:
            raise RuntimeError("network access is forbidden during wheel smoke")
        return super().connect(address)

    def connect_ex(self, address):
        if allowed is None or address[:2] != allowed:
            raise RuntimeError("network access is forbidden during wheel smoke")
        return super().connect_ex(address)


setattr(socket, "socket", OfflineSocket)
