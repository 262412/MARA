"""Bounded regressions for AnyIO's process stderr and IDNA advisories."""

import asyncio
import datetime
import json
import os
import socket
import ssl
import subprocess
import sys
import threading

import anyio
import psutil
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

PROCESS_PROBE = """
import json
import os
import sys
from pathlib import Path

import anyio
from anyio import to_process


def fill_stderr(pid_file):
    Path(pid_file).write_text(str(os.getpid()), encoding="utf-8")
    sys.stderr.write("owned stderr " * 180000)
    sys.stderr.flush()
    return "finished"


async def exercise():
    result = {"timed_out": False}
    try:
        with anyio.fail_after(5):
            result["value"] = await to_process.run_sync(
                fill_stderr, sys.argv[1], cancellable=True
            )
    except TimeoutError:
        result["timed_out"] = True
    with anyio.fail_after(5):
        result["followup_pid"] = await to_process.run_sync(
            os.getpid, cancellable=True
        )
    return result


if __name__ == "__main__":
    result = anyio.run(exercise)
    print(json.dumps(result))
    raise SystemExit(1 if result["timed_out"] else 0)
"""


def test_process_worker_stderr_finishes_and_pool_shuts_down(tmp_path):
    """GHSA-5p39-cfhj-2xmp: real pipe pressure, cancellation and a later call."""
    probe = tmp_path / "owned_process_probe.py"
    pid_file = tmp_path / "worker.pid"
    probe.write_text(PROCESS_PROBE, encoding="utf-8")
    command = [sys.executable, "-B", str(probe), str(pid_file)]
    with subprocess.Popen(
        command,
        cwd=tmp_path,
        env=os.environ.copy(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    ) as process:
        try:
            stdout, stderr = process.communicate(timeout=20)
        except subprocess.TimeoutExpired:
            # Only descendants of this owned probe are eligible for termination.
            descendants = psutil.Process(process.pid).children(recursive=True)
            for child in descendants:
                child.kill()
            process.kill()
            process.communicate(timeout=5)
            psutil.wait_procs(descendants, timeout=5)
            pytest.fail("Owned process-pool probe exceeded its outer deadline")
    assert pid_file.exists(), stderr
    assert not psutil.pid_exists(int(pid_file.read_text(encoding="utf-8")))
    result = json.loads(stdout)
    assert not psutil.pid_exists(result["followup_pid"])
    assert process.returncode == 0, result
    assert result["value"] == "finished"


def issue_certificate(key, subject, issuer, issuer_key, *, ca=False, hostname=None):
    now = datetime.datetime.now(datetime.timezone.utc)
    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=ca, path_length=None), critical=True)
    )
    if hostname:
        builder = builder.add_extension(
            x509.SubjectAlternativeName([x509.DNSName(hostname)]), critical=False
        )
    return builder.sign(issuer_key, hashes.SHA256())


def owned_tls_contexts(tmp_path, hostname):
    ca_key = ec.generate_private_key(ec.SECP256R1())
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Owned test CA")])
    ca = issue_certificate(ca_key, ca_name, ca_name, ca_key, ca=True)
    key = ec.generate_private_key(ec.SECP256R1())
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, hostname)])
    cert = issue_certificate(key, subject, ca_name, ca_key, hostname=hostname)
    cert_path, key_path = tmp_path / "server.pem", tmp_path / "server.key"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    server = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server.load_cert_chain(cert_path, key_path)
    client = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    client.load_verify_locations(
        cadata=ca.public_bytes(serialization.Encoding.PEM).decode("ascii")
    )
    assert client.check_hostname and client.verify_mode == ssl.CERT_REQUIRED
    return server, client


@pytest.mark.parametrize(
    ("certificate_hostname", "accepted"),
    [("xn--strae-oqa.test", True), ("strasse.test", False)],
)
def test_unicode_tls_hostname_verifies_idna2008_certificate(
    tmp_path, certificate_hostname, accepted
):
    """GHSA-82r6-8w77-94w6: trust only an ephemeral CA on a loopback socket."""
    server_context, client_context = owned_tls_contexts(tmp_path, certificate_hostname)
    server_events = []
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.settimeout(8)
        port = listener.getsockname()[1]

        def serve():
            try:
                connection, _ = listener.accept()
                with connection:
                    connection.settimeout(8)
                    with server_context.wrap_socket(
                        connection, server_side=True
                    ) as tls:
                        server_events.append("verified")
                        tls.sendall(b"owned")
            except ssl.SSLError:
                server_events.append("rejected")
            except OSError as error:
                server_events.append(type(error).__name__)

        async def connect():
            with anyio.fail_after(8):
                async with await anyio.connect_tcp(
                    "127.0.0.1",
                    port,
                    tls_hostname="straße.test",
                    ssl_context=client_context,
                    tls_standard_compatible=False,
                ) as stream:
                    assert await stream.receive() == b"owned"

        thread = threading.Thread(target=serve, name="owned-anyio-tls-test")
        thread.start()
        try:
            if accepted:
                asyncio.run(connect())
            else:
                with pytest.raises(ssl.SSLCertVerificationError):
                    asyncio.run(connect())
        finally:
            thread.join(timeout=10)
            assert not thread.is_alive()
    assert server_events == (["verified"] if accepted else ["rejected"])
