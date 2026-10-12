"""Generate controlled review projections for the G1.5-B structured pilot."""

from __future__ import annotations

import argparse
from html import escape
from pathlib import Path
from typing import Any

try:  # direct script execution and package import are both supported in CI
    from .pilot_contract import PILOT_ROOT, PilotError, load_validated_pilot
except ImportError:  # pragma: no cover - exercised by the direct CLI invocation
    from pilot_contract import PILOT_ROOT, PilotError, load_validated_pilot


OUTPUTS = {
    "sdoc": PILOT_ROOT / "strictdoc" / "b0_phase1_pilot.sdoc",
    "markdown": PILOT_ROOT / "lightweight" / "b0_phase1_pilot.md",
    "model_view": PILOT_ROOT / "model" / "b0_truth_control_slice_view.md",
}


def _lines(value: str) -> list[str]:
    return value.strip().splitlines() or [""]


def _sdoc_block(field: str, value: str) -> list[str]:
    return [f"{field}: >>>", *_lines(value), "<<<"]


def _locator_map(contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["id"]: item for item in contract["source_locators"]}


def _relation_rows(contract: dict[str, Any], source_id: str) -> list[dict[str, Any]]:
    return [relation for relation in contract["relations"] if relation["source_id"] == source_id]


def _identity_link(identity: str, label: str | None = None) -> str:
    """Render an internal review-page link for a stable pilot identity."""

    visible = label if label is not None else identity
    return f'<a href="#{escape(identity)}"><code>{escape(visible)}</code></a>'


def render_sdoc(contract: dict[str, Any]) -> str:
    """Render body and native Parent hierarchy as a StrictDoc projection.

    This projection deliberately uses the default grammar. StrictDoc 0.30.1
    also supports declared custom grammars; the separate comparison fixture
    evaluates that option without making this generated file another source.
    """

    result = [
        "[DOCUMENT]",
        "TITLE: B0 G1.5-B structured requirements-tooling pilot",
        "UID: PILOT-ONLY-DOCUMENT",
        "VERSION: @GIT_VERSION (Git branch: @GIT_BRANCH)",
        "CLASSIFICATION: Internal",
        "PREFIX: PILOT-ONLY-",
        "OPTIONS:",
        "  MARKUP: Text",
        "",
    ]
    for record in contract["records"]:
        result.extend(
            [
                "[REQUIREMENT]",
                f"UID: {record['key']}",
                f"LEVEL: {record['level']}",
                f"STATUS: {record['status']}",
                f"TAGS: {', '.join(record['tags'])}",
                f"TITLE: {record['title']}",
                *_sdoc_block("STATEMENT", record["statement"]),
                *_sdoc_block("RATIONALE", record["rationale"]),
            ]
        )
        result.extend(
            [
                "COMMENT: >>>",
                "Generated review projection; edit pilot_structure.json, not this file.",
                "<<<",
            ]
        )
        if record["parent"] is not None:
            result.extend(["RELATIONS:", "- TYPE: Parent", f"  VALUE: {record['parent']}"])
        result.append("")
    return "\n".join(result).rstrip() + "\n"


def render_markdown(contract: dict[str, Any]) -> str:
    """Render a no-tool reader projection from the single body source."""

    locators = _locator_map(contract)
    result = [
        "# G1.5-B phase-one structured pilot",
        "",
        "**Generated review projection.** Edit `contract/pilot_structure.json`; do not edit this Markdown file.",
        "",
        "This is a non-authoritative five-record trial. It does not freeze formal requirements, assert G2/G3 implementation, or claim execution evidence.",
        "",
    ]
    for record in contract["records"]:
        result.extend(
            [
                f"## {record['key']}",
                "",
                f"- **Title:** {record['title']}",
                f"- **Record type:** {record['level']}",
                "- **Approval status:** candidate_only",
                f"- **Applicability:** {record['applicability']['state']}",
                f"- **Scope:** {record['applicability']['scope']}",
                f"- **Parent:** {record['parent'] or 'none'}",
                f"- **Evidence status:** {record['evidence_status']}",
                "- **Source locators:**",
            ]
        )
        for locator_id in record["source_locator_ids"]:
            result.append(f"  - `{locators[locator_id]['locator']}`")
        if record["applicability"]["state"] == "not_applicable":
            result.append(f"- **Approval locator:** `{locators[record['applicability']['approval_ref']]['locator']}`")
        trace_rows = _relation_rows(contract, record["key"])
        if trace_rows:
            result.append("- **Cross-domain links:**")
            for relation in trace_rows:
                result.append(f"  - `{relation['type']}` → `{relation['target_id']}` (project_extension)")
        result.extend(
            [
                "",
                "### Statement",
                "",
                record["statement"],
                "",
                "### Rationale",
                "",
                record["rationale"],
                "",
                "### Planned acceptance condition",
                "",
                record["acceptance_condition"],
                "",
            ]
        )
    return "\n".join(result)


def render_model_view(contract: dict[str, Any], model: Any) -> str:
    """Render a readable project view from contract relations and parser AST."""

    model_elements = {item["id"]: item for item in contract["model_elements"]}
    related_records: dict[str, list[str]] = {identity: [] for identity in model_elements}
    for relation in contract["relations"]:
        if relation["type"] == "models":
            related_records[relation["target_id"]].append(relation["source_id"])
    result = [
        "# B0 truth/control model slice — generated review view",
        "",
        "**Generated from:** `contract/pilot_structure.json` and the `sysmlpy` AST of `b0_truth_control_slice.sysml`.",
        "",
        "This is a textual project reading aid, not a SysML graphical notation view, simulation, or conformance claim.",
        "",
        "## Declared model elements",
        "",
        "| Identity | Display name | Parsed type | Scope | Related records | Intended bounded role |",
        "|---|---|---|---|---|---|",
    ]
    for identity in sorted(model.definitions):
        if identity in model_elements:
            element = model_elements[identity]
            records = ", ".join(f"`{record}`" for record in sorted(related_records[identity]))
            result.append(
                f"| `{identity}` | {element['display_name']} | `{model.definitions[identity]}` | {element['scope']} | {records} | {element['intended_role']} |"
            )
    result.extend(["", "## Parsed flow endpoints", ""])
    for source, source_feature, target, target_feature in sorted(model.flows):
        result.append(f"- `{source}.{source_feature}` → `{target}.{target_feature}`")
    result.extend(["", "## Cross-domain trace links", "", "| Relation | Source | Target | Status boundary |", "|---|---|---|---|"])
    for relation in contract["relations"]:
        result.append(
            f"| `{relation['type']}` | `{relation['source_id']}` | `{relation['target_id']}` | project_extension / planned where stated |"
        )
    if model.analysis_warnings:
        result.extend(["", "## Parser analysis warnings", "", "The fixed parser reports the following non-error warnings; they are retained as a tool limitation rather than suppressed:", ""])
        for warning in model.analysis_warnings:
            result.append(f"- `{warning}`")
    return "\n".join(result) + "\n"


def render_outputs(contract: dict[str, Any], model: Any) -> dict[Path, str]:
    return {
        OUTPUTS["sdoc"]: render_sdoc(contract),
        OUTPUTS["markdown"]: render_markdown(contract),
        OUTPUTS["model_view"]: render_model_view(contract, model),
    }


def write_outputs(rendered: dict[Path, str]) -> None:
    for path, content in rendered.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")


def check_outputs(rendered: dict[Path, str]) -> None:
    for path, expected in rendered.items():
        if not path.is_file():
            raise PilotError(f"generated pilot projection is missing: {path}")
        actual = path.read_text(encoding="utf-8")
        if actual != expected:
            raise PilotError(f"generated pilot projection drifted: {path}")


def render_preview_html(contract: dict[str, Any], model: Any) -> str:
    """Create a local-only review page; it is intentionally never committed."""

    locators = _locator_map(contract)
    model_elements = {element["id"]: element for element in contract["model_elements"]}
    related_records: dict[str, list[str]] = {identity: [] for identity in model_elements}
    for relation in contract["relations"]:
        if relation["type"] == "models":
            related_records[relation["target_id"]].append(relation["source_id"])
    development_objects = {
        element["id"]: element for element in contract["development_objects"]
    }
    verification_provisions = {
        element["id"]: element for element in contract["verification_provisions"]
    }
    known_targets = set(model_elements) | set(development_objects) | set(verification_provisions)
    records = []
    for record in contract["records"]:
        source_list = "".join(f"<li><code>{escape(locators[key]['locator'])}</code></li>" for key in record["source_locator_ids"])
        parent = _identity_link(record["parent"]) if record["parent"] is not None else "none"
        relation_items = []
        for relation in _relation_rows(contract, record["key"]):
            target_id = relation["target_id"]
            target = _identity_link(target_id) if target_id in known_targets else f"<code>{escape(target_id)}</code>"
            relation_items.append(
                f"<li><code>{escape(relation['type'])}</code> → {target} (project_extension)</li>"
            )
        relation_list = "".join(relation_items)
        records.append(
            "\n".join(
                [
                    f'<article id="{escape(record["key"])}">',
                    f"<h2>{escape(record['key'])}: {escape(record['title'])}</h2>",
                    "<dl>",
                    f"<dt>Type</dt><dd>{escape(record['level'])}</dd>",
                    "<dt>Approval</dt><dd>candidate_only</dd>",
                    f"<dt>Applicability</dt><dd>{escape(record['applicability']['state'])}</dd>",
                    f"<dt>Scope</dt><dd>{escape(record['applicability']['scope'])}</dd>",
                    f"<dt>Parent</dt><dd>{parent}</dd>",
                    f"<dt>Evidence</dt><dd>{escape(record['evidence_status'])}</dd>",
                    "</dl>",
                    "<h3>Statement</h3>",
                    f"<p>{escape(record['statement'])}</p>",
                    "<h3>Rationale</h3>",
                    f"<p>{escape(record['rationale'])}</p>",
                    "<h3>Planned acceptance</h3>",
                    f"<p>{escape(record['acceptance_condition'])}</p>",
                    "<h3>Source locators</h3>",
                    f"<ul>{source_list}</ul>",
                    "<h3>Cross-domain links</h3>",
                    f"<ul>{relation_list}</ul>",
                    "</article>",
                ]
            )
        )
    nav = "".join(f'<li><a href="#{escape(record["key"])}">{escape(record["key"])}</a></li>' for record in contract["records"])
    flow_rows = "".join(
        f"<li><code>{escape(source)}.{escape(source_feature)}</code> → <code>{escape(target)}.{escape(target_feature)}</code></li>"
        for source, source_feature, target, target_feature in sorted(model.flows)
    )
    model_rows = "".join(
        f'<tr id="{escape(identity)}">'
        f"<td>{_identity_link(identity)}</td>"
        f"<td>{escape(model_elements[identity]['display_name'])}</td>"
        f"<td><code>{escape(kind)}</code></td>"
        f"<td>{escape(model_elements[identity]['scope'])}</td>"
        "<td>"
        + ", ".join(
            _identity_link(record_key)
            for record_key in sorted(related_records[identity])
        )
        + "</td>"
        "</tr>"
        for identity, kind in sorted(model.definitions.items())
        if identity in model_elements
    )
    development_rows = "".join(
        f'<tr id="{escape(identity)}">'
        f"<td>{_identity_link(identity)}</td>"
        f"<td>{escape(object_['kind'])}</td>"
        f"<td>{escape(object_['responsible_component'])}</td>"
        f"<td>{escape(object_['lifecycle'])}</td>"
        "</tr>"
        for identity, object_ in development_objects.items()
    )
    verification_rows = "".join(
        f'<tr id="{escape(identity)}">'
        f"<td>{_identity_link(identity)}</td>"
        f"<td>{escape(provision['method'])}</td>"
        f"<td>{escape(provision['planning_status'])} / {escape(provision['execution_status'])}</td>"
        f"<td>{escape(provision['acceptance_condition'])}</td>"
        "</tr>"
        for identity, provision in verification_provisions.items()
    )
    trace_rows = "".join(
        "<tr>"
        f"<td>{escape(relation['type'])}</td>"
        f"<td>{_identity_link(relation['source_id'])}</td>"
        f"<td>{_identity_link(relation['target_id'])}</td>"
        "</tr>"
        for relation in contract["relations"]
    )
    return f"""<!doctype html>
<html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
<title>B0 G1.5-B structured pilot review</title>
<style>
:root {{ color-scheme: light; font-family: Inter, Segoe UI, sans-serif; color: #172033; background: #f4f7fb; }}
body {{ margin: 0; line-height: 1.5; }} header {{ background: #102a43; color: #fff; padding: 1.5rem max(1.2rem, calc((100vw - 1120px)/2)); }}
header p {{ max-width: 70rem; margin: .4rem 0 0; }} main {{ max-width: 1120px; margin: 0 auto; padding: 1.2rem; }}
nav {{ background: #e6f0ff; border: 1px solid #b9d2f2; padding: .8rem 1rem; border-radius: .45rem; }} nav ul {{ columns: 2; margin: .3rem 0; padding-left: 1.2rem; }}
article, section {{ background: #fff; border: 1px solid #d8e0eb; border-radius: .45rem; margin: 1rem 0; padding: 1rem 1.2rem; box-shadow: 0 1px 2px #102a4312; }}
h1, h2, h3 {{ line-height: 1.2; }} h2 {{ color: #0c4a6e; }} h3 {{ margin-bottom: .25rem; }} dl {{ display: grid; grid-template-columns: max-content 1fr; gap: .25rem .8rem; }} dt {{ font-weight: 700; }} dd {{ margin: 0; }}
code {{ overflow-wrap: anywhere; color: #7c2d12; }} .scroll-table {{ overflow-x: auto; }} table {{ border-collapse: collapse; width: 100%; }} th, td {{ border: 1px solid #cbd5e1; padding: .45rem; text-align: left; vertical-align: top; }} th {{ background: #edf4ff; }}
@media (max-width: 720px) {{ nav ul {{ columns: 1; }} dl {{ grid-template-columns: 1fr; gap: .1rem; }} dd {{ margin-bottom: .5rem; }} main {{ padding: .7rem; }} article, section {{ padding: .8rem; }} }}
</style></head><body>
<header><h1>B0 G1.5-B structured pilot review</h1><p>Local review-only projection. Non-authoritative; planned/not-run is not execution evidence, a satisfied requirement, or a frozen baseline.</p></header>
<main><nav aria-label=\"Pilot record navigation\"><strong>Five candidate records</strong><ul>{nav}</ul></nav>
{''.join(records)}
<section><h2>Parsed model slice</h2><div class="scroll-table"><table><thead><tr><th>Identity</th><th>Name</th><th>Parsed type</th><th>Scope</th><th>Related records</th></tr></thead><tbody>{model_rows}</tbody></table></div></section>
<section><h2>Parsed model flow endpoints</h2><ul>{flow_rows}</ul><p>This textual view is generated from the fixed parser AST; it is not standard SysML graphical notation.</p></section>
<section><h2>Planned development allocation</h2><div class="scroll-table"><table><thead><tr><th>Identity</th><th>Kind</th><th>Responsible component</th><th>Lifecycle</th></tr></thead><tbody>{development_rows}</tbody></table></div></section>
<section><h2>Planned verification provisions</h2><div class="scroll-table"><table><thead><tr><th>Identity</th><th>Method</th><th>Planning / execution</th><th>Acceptance condition</th></tr></thead><tbody>{verification_rows}</tbody></table></div></section>
<section><h2>Cross-domain trace links</h2><table><thead><tr><th>Relation</th><th>Source</th><th>Target</th></tr></thead><tbody>{trace_rows}</tbody></table></section>
</main></body></html>"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--write", action="store_true", help="write controlled repository projections")
    actions.add_argument("--check", action="store_true", help="fail if a controlled projection drifted")
    actions.add_argument("--preview-output", type=Path, metavar="DIR", help="write a local review.html outside Git")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[3])
    args = parser.parse_args(argv)
    try:
        contract, model = load_validated_pilot(args.repo_root.resolve())
        rendered = render_outputs(contract, model)
        if args.write:
            write_outputs(rendered)
            print(f"wrote {len(rendered)} controlled pilot projections")
        elif args.check:
            check_outputs(rendered)
            print(f"controlled pilot projections are current ({len(rendered)} files)")
        else:
            output = args.preview_output.resolve()
            output.mkdir(parents=True, exist_ok=True)
            preview = output / "review.html"
            preview.write_text(render_preview_html(contract, model), encoding="utf-8", newline="\n")
            print(preview)
    except PilotError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":  # pragma: no cover - command-line entry point
    raise SystemExit(main())
