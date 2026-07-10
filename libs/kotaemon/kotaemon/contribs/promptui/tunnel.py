class Tunnel:
    """Compatibility facade for the retired internal PromptUI tunnel."""

    def __init__(self, appname, username, local_port):
        self.proc = None
        self.url = None
        self.appname = appname
        self.username = username
        self.local_port = local_port

    def run(self) -> str:
        raise RuntimeError(
            "The internal PromptUI tunnel is retired because its remote binary and "
            "credentials cannot be verified. Deploy behind an authenticated, "
            "operator-managed reverse proxy instead."
        )

    def kill(self):
        if self.proc is not None:
            print(f"Killing tunnel 127.0.0.1:{self.local_port} <> {self.url}")
            self.proc.terminate()
            self.proc = None
