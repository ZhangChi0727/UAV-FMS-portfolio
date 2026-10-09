# Shared literature record

This directory supports the independent [research packages](../research/README.md).
Zotero is the bibliographic source of truth; repository records capture searches,
screening, evidence extraction and scoped claims. July 2026 pilot records are
historical; they are not a completed systematic review or proof of novelty.

## Workflow

1. Review protocol.md and define package-specific search questions and limits.
2. Record exact queries and execution dates in search_log.csv.
3. Validate metadata with publisher/Crossref records and import into Zotero.
4. Deduplicate and screen in screening.csv, preserving exclusions and uncertainty.
5. Extract full-text findings with page/section/table locators into evidence_matrix.xlsx.
6. Link claims and counter-evidence in claim_ledger.md.
7. Run notebooks for descriptive audits; do not infer formal review coverage from
   a selected semantic-search seed set.

## Environment

Create a Python virtual environment and install literature/requirements.txt.
Register the notebook kernel with:

```sh
python -m ipykernel install --prefix .venv --name uav-fms-research --display-name "UAV-FMS Research (.venv)"
```

Use Zotero with Better BibTeX. Export real bibliographic records to references.bib,
keeping DOI/URL and stable citation keys. Configure automatic export locally;
never export attachment paths or private notes. The current bibliography placeholder
is intentional until authoritative records are exported. LaTeX is optional for
manuscript preparation and is not a B0 dependency.

Organize collections by surveys, estimation/control, faults/recovery, real-time
implementation, verification/evidence transfer, datasets, and screening status.
Keep controlled tags consistent with the workbook vocabulary.

## Artifacts and boundaries

- protocol.md: eligibility, scope and amendments.
- search_log.csv / screening.csv: dated provenance and decisions.
- evidence_matrix.xlsx: study metadata and source-located extraction.
- claim_ledger.md: candidate claims and evidence gaps.
- notebooks/: reproducible audits; see its README for execution.
- references.bib: bibliographic export.

Do not commit copyrighted full texts, credentials, private notes, generated exports,
or notebook outputs. Local full_text/ and exports/ are ignored. Existing workbook
study metadata is preliminary; missing full-text evidence must remain explicit.
