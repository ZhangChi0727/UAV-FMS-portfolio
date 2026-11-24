"""Render the compact offline view. MarkdownIt is a StrictDoc dependency."""
import argparse
from html import escape
from pathlib import Path
import re

from markdown_it import MarkdownIt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUTPUT = ROOT / "overview.html"


def section(path):
    # Read the named fields of this repository's REQUIREMENT grammar only.
    nodes = re.split(r"^\[REQUIREMENT\]$", path.read_text(encoding="utf-8"), flags=re.M)[1:]
    if not nodes:
        raise ValueError(f"No REQUIREMENT entries in {path.name}")
    rows = []
    for node in nodes:
        fields = dict(re.findall(r"^(UID|TITLE|STATUS|STATE|EVIDENCE): (.+)$", node, re.M))
        uid, title, status, state, evidence = (
            escape(fields[key]) for key in ("UID", "TITLE", "STATUS", "STATE", "EVIDENCE")
        )
        rows.append(f'<tr id="{uid}"><th scope="row">{uid}</th>'
                    f'<td><details><summary>{title}</summary><p>{evidence}</p></details></td>'
                    f'<td>{status}</td><td>{state}</td></tr>')
    name = escape(path.name)
    opened = " open" if path.name == "edge.sdoc" else ""
    return (f'<details{opened}><summary>{name} · {len(nodes)} requirements</summary>'
            f'<p><a href="requirements/{name}">StrictDoc source</a></p><table>'
            '<thead><tr><th>ID</th><th>Title / evidence</th><th>Lifecycle</th>'
            '<th>Implementation</th></tr></thead><tbody>\n' + "\n".join(rows)
            + '\n</tbody></table></details>')


def render():
    readme = MarkdownIt("commonmark", {"html": False}).render((ROOT / "README.md").read_text(encoding="utf-8"))
    docs = sorted(HERE.glob("*.sdoc"), key=lambda p: (p.name != "edge.sdoc", p.name))
    return ('''<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>UAV FMS Portfolio | Requirements overview</title>
<style>
body{max-width:64rem;margin:2rem auto;padding:0 1rem;font:1rem/1.5 system-ui;color:#172b39}
a{color:#075781}table{width:100%;border-collapse:collapse}th,td{text-align:left;vertical-align:top;
padding:.45rem;border-bottom:1px solid #ccd5db}summary{cursor:pointer}section>details{margin:1rem 0;overflow:auto}
</style><main>
''' + readme + '<section id="requirements"><h2>Requirements</h2>'
            '<p>Open a title to read its evidence. Implementation state is not system verification. '
            '<a href="requirements/README.md">Field definitions and full export instructions</a>.</p>\n'
            + "\n".join(section(p) for p in docs) + "\n</section></main></html>\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    page = render()
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != page:
            parser.exit(1, "overview.html is stale; run python requirements/render_overview.py\n")
    else:
        OUTPUT.write_text(page, encoding="utf-8", newline="\n")
