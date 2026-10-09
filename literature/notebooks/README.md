# Literature notebooks

Run these notebooks from the repository root so their relative paths resolve:

```powershell
.\.venv\Scripts\Activate.ps1
python -m jupyterlab literature/notebooks
```

Select the `UAV-FMS Research (.venv)` kernel if Jupyter prompts for a kernel.

Recommended order:

1. `deduplicate.ipynb` — normalize DOI/title fields and generate duplicate
   candidates without silently deleting records.
2. `search_audit.ipynb` — validate search-log completeness and reconcile screening
   flow counts.
3. `evidence_summary.ipynb` — summarize populated evidence by topic, method, fault,
   platform, and validation level.

Notebooks read version-controlled source artifacts and write temporary derived files
under ignored `literature/exports/`. Review outputs before transferring any result
into the protocol, evidence matrix, claim ledger, thesis, or figures.

Restart the kernel and run all cells before review. Do not commit notebook output
containing copyrighted text, credentials, local file paths, or sensitive metadata.
