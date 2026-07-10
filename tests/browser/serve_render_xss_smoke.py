"""Serve a browser smoke page built through MARA's real HTML renderers."""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from ktem.pages.chat.answer_rendering import format_chat_message_html
from ktem.utils.render import Render

HOSTILE_HTML = (
    '<img src="x" onerror="window.__maraRenderXss += 1">'
    "<script>window.__maraRenderXss += 10</script>"
    '<a href="javascript:window.__maraRenderXss += 100">script URL</a>'
    '<a href="data:text/html,<script>window.__maraRenderXss += 1000</script>">'
    "data URL</a></summary></details>"
)


def build_page() -> str:
    evidence = Render.collapsible(
        f"Evidence {HOSTILE_HTML}",
        Render.table(f"# Source\n\n{HOSTILE_HTML}"),
        open=True,
    )
    highlighted = Render.highlight(HOSTILE_HTML, "browser-smoke")
    image = Render.image("javascript:window.__maraRenderXss=9999", HOSTILE_HTML)
    answer = format_chat_message_html(HOSTILE_HTML, "assistant")
    rendered = evidence + highlighted + image + answer
    return f"""<!doctype html>
<html lang="en">
  <head><meta charset="utf-8"><title>MARA rendered XSS smoke</title></head>
  <body data-test-status="running">
    <script data-test-harness>window.__maraRenderXss = 0;</script>
    <main id="render-output">{rendered}</main>
    <script data-test-harness>
      window.addEventListener("load", () => {{
        setTimeout(() => {{
          const output = document.getElementById("render-output");
          const activeNodes = output.querySelectorAll(
            "script, [onerror], [onload], [onclick], [href^='javascript:'], [href^='data:text/html']"
          );
          if (window.__maraRenderXss !== 0 || activeNodes.length !== 0) {{
            document.body.dataset.testStatus = "failed";
            document.body.dataset.testError =
              `marker=${{window.__maraRenderXss}} activeNodes=${{activeNodes.length}}`;
            return;
          }}
          document.body.dataset.testStatus = "passed";
        }}, 50);
      }});
    </script>
  </body>
</html>"""


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        body = build_page().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    ThreadingHTTPServer(("127.0.0.1", args.port), _Handler).serve_forever()


if __name__ == "__main__":
    main()
