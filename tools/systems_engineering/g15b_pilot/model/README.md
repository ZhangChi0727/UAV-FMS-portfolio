# B0 truth/control SysML v2 textual slice

`b0_truth_control_slice.sysml` is a deliberately small, non-authoritative
SysML v2 textual model slice for the G1.5-B phase-one pilot.  It contains
stable `PILOT-MODEL-*` identities for items, parts, interfaces, flows, one
requirement proxy, and one verification definition.  It does not represent a
complete B0 architecture, an implemented G2 controller, or a standard
graphical notation view.

## Source and review boundary

- The authoritative pilot record body is
  `../contract/pilot_structure.json`; this model does not duplicate it.
- The model proxy and verification definition are intentionally planned-only.
  The model contains no `satisfy requirement` or `verify requirement` usage,
  because neither implementation nor execution evidence exists in this pilot.
- The generated `b0_truth_control_slice_view.md` is a controlled reading aid
  generated from the structured contract and parser AST.  It is not a SysML
  graphical notation claim and must not be edited.
- Project cross-domain links live in the JSON contract and are labelled
  `project_extension`; the source only uses the native textual constructs it
  actually declares.

## Fixed tool and commands

The isolated tool dependency is `sysmlpy==0.33.2`, declared in
`requirements/g15b-pilot.txt`.  It is a third-party parser/analyser, not an
OMG reference implementation.  With the isolated G1.5-B environment active,
the scoped checker is the canonical command:

```text
python tools/systems_engineering/check_g15b_phase1_pilot.py
python -m pytest -q tools/systems_engineering/g15b_pilot/tests -p no:cacheprovider
```

The checker uses the parser AST to verify declared model identities and flow
endpoints.  It covers the adopted textual subset only.  It does not provide
OMG conformance certification, graphical rendering, execution, simulation,
formal verification, or model interchange validation.

## Rebuild and inspect the generated reading aid

```text
python tools/systems_engineering/g15b_pilot/build_pilot_views.py --write
python tools/systems_engineering/g15b_pilot/build_pilot_views.py --check
```

For a review-only local page, use `--preview-output <temporary-directory>`.
The output must be outside Git, named for the exact reviewed SHA, and served
only from a loopback address.  The normal checker does not depend on a browser
or retain a preview artifact.
