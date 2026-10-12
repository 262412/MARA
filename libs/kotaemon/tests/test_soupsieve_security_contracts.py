"""Selector semantics and bounded regressions for the two Soup Sieve advisories."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import bs4
import psutil
import pytest
import soupsieve

HTML = (
    '<a><b id="first"></b><b id="second"></b></a><b id="outside"></b>'
    '<div id="café" data-kind="x y"><span id="leaf"></span></div>'
    '<p id="a:b"><em id="em"></em></p>'
    '<ul><li id="li1"></li><li id="li2"></li></ul>'
)
PROBE = """
import json
import os
import sys
from pathlib import Path

if os.name == "posix":
    import resource
    resource.setrlimit(resource.RLIMIT_CPU, (3, 4))
    resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024,) * 2)

import bs4
import soupsieve

case = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
soup = bs4.BeautifulSoup(case["html"], "html.parser")
soupsieve.purge()
try:
    result = {"status": "ok", "ids": [tag.get("id") for tag in soup.select(case["selector"])]}
except soupsieve.SelectorSyntaxError:
    result = {"status": "SelectorSyntaxError"}
result.update(soupsieve_path=soupsieve.__file__, bs4_path=bs4.__file__)
print(json.dumps(result))
"""


def run_bounded_selector(tmp_path, selector):
    """One fresh process; Linux hard limits plus a portable process-tree monitor."""
    assert len(selector) <= 64004
    probe, payload = tmp_path / "selector_probe.py", tmp_path / "selector.json"
    probe.write_text(PROBE, encoding="utf-8")
    payload.write_text(
        json.dumps({"html": HTML, "selector": selector}), encoding="utf-8"
    )
    violation = None
    with subprocess.Popen(
        [sys.executable, "-I", "-B", str(probe), str(payload)],
        cwd=tmp_path,
        env=os.environ.copy(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    ) as process:
        owner = psutil.Process(process.pid)
        started = time.monotonic()
        try:
            while process.poll() is None:
                rss, cpu = 0, 0.0
                try:
                    active = [owner, *owner.children(recursive=True)]
                    for child in active:
                        rss += child.memory_info().rss
                        times = child.cpu_times()
                        cpu += times.user + times.system
                except psutil.NoSuchProcess:
                    continue
                if (
                    rss > 256 * 1024 * 1024
                    or cpu > 3
                    or time.monotonic() - started > 10
                ):
                    violation = {"rss_bytes": rss, "cpu_seconds": cpu}
                    break
                time.sleep(0.01)
        finally:
            if process.poll() is None:
                descendants = owner.children(recursive=True)
                for child in descendants:
                    child.kill()
                process.kill()
                psutil.wait_procs(descendants, timeout=5)
            stdout, stderr = process.communicate(timeout=5)
    assert violation is None, f"Selector exceeded resource budget: {violation}"
    assert process.returncode == 0, stderr
    result = json.loads(stdout)
    assert (
        Path(result["soupsieve_path"]).resolve() == Path(soupsieve.__file__).resolve()
    )
    assert Path(result["bs4_path"]).resolve() == Path(bs4.__file__).resolve()
    return result


@pytest.mark.parametrize("family", ["attribute", "identifier"])
def test_identifier_value_backtracking_is_bounded(tmp_path, family):
    """GHSA-gjv8-xp57-g29c: retain the syntax error without costly backtracking."""
    selector = "[a=" + "a" * 2048 if family == "attribute" else "a" * 64000 + "!"
    assert run_bounded_selector(tmp_path, selector)["status"] == "SelectorSyntaxError"


@pytest.mark.parametrize("family", ["whitespace", "comments"])
def test_internal_whitespace_and_comment_trimming_is_bounded(tmp_path, family):
    """GHSA-j934-xhv5-fg8f: valid selectors must retain ordered matches."""
    gap = " " * 64000 if family == "whitespace" else "/*x*/" * 12800
    result = run_bounded_selector(tmp_path, "a " + gap + " b")
    assert result["status"] == "ok"
    assert result["ids"] == ["first", "second"]


@pytest.mark.parametrize(
    ("selector", "expected"),
    [
        ("a b, a b", ["first", "second"]),
        ("#café > span", ["leaf"]),
        (r"#a\:b", ["a:b"]),
        ('[data-kind~="y"]', ["café"]),
        ("ul > li:nth-child(2)", ["li2"]),
        (":is(a,p) > :first-child", ["first", "em"]),
        ("a /* internal */ b", ["first", "second"]),
        ("a" * 8000, []),
        ("[a=" + "a" * 8000 + "]", []),
    ],
    ids=[
        "ordered-deduplicated",
        "unicode",
        "escaped",
        "attribute",
        "nth",
        "is",
        "comments",
        "long-name",
        "long-value",
    ],
)
def test_normal_selector_results_and_order(selector, expected):
    soup = bs4.BeautifulSoup(HTML, "html.parser")
    assert [tag.get("id") for tag in soup.select(selector)] == expected


def test_xml_namespace_selector_results_and_order():
    soup = bs4.BeautifulSoup(
        '<root xmlns:h="urn:owned"><h:item id="first"/><item id="plain"/>'
        '<h:item id="second"/></root>',
        "xml",
    )
    assert [
        tag["id"] for tag in soup.select("h|item", namespaces={"h": "urn:owned"})
    ] == [
        "first",
        "second",
    ]


@pytest.mark.parametrize("selector", ["[a=", "a!", '[data-kind="x]'])
def test_invalid_selector_retains_syntax_error(selector):
    soup = bs4.BeautifulSoup(HTML, "html.parser")
    with pytest.raises(soupsieve.SelectorSyntaxError):
        soup.select(selector)
