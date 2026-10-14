# B0 G2-B cascaded controller

This track contains the platform-independent C++17 cascaded attitude/body-rate controller and its mandatory pybind11 boundary. It consumes estimated state and paired actuator feedback only; it has no plant-truth input. G3 owns scheduling and complete closed-loop performance evaluation.

Configure, build and test each required build type from an environment containing `requirements/b0-dev.txt`:

```sh
cmake --preset b0-controller-debug
cmake --build --preset b0-controller-debug
ctest --preset b0-controller-debug
cmake --preset b0-controller-release
cmake --build --preset b0-controller-release
ctest --preset b0-controller-release
```

The Python test asserts the actual imported extension path. `python/controller.py` validates the approved implementation configuration and the actual G0 file before mapping frozen G2-A/G1 message fields.

After a successful build, first retain CTest and pytest JUnit from that same
module/build identity, then generate the deterministic component trace (shown
for Debug):

```sh
repo_root="$PWD"
evidence_dir="$repo_root/build/b0-controller/debug/evidence"
mkdir -p "$evidence_dir"
ctest --preset b0-controller-debug --output-on-failure \
  --output-log "$evidence_dir/ctest-debug.log" \
  --output-junit "$evidence_dir/ctest-debug.xml"
(
  cd 03_control/b0
  B0_CONTROLLER_MODULE_DIR="$repo_root/build/b0-controller/debug/03_control/b0" \
  B0_CONTROLLER_REPO="$repo_root" \
    python -m pytest -q python/tests \
    --junitxml="$evidence_dir/pytest-debug.xml"
)
python 03_control/b0/evidence.py \
  --module-dir build/b0-controller/debug/03_control/b0 \
  --build-dir build/b0-controller/debug \
  --build-type Debug \
  --ctest-junit "$evidence_dir/ctest-debug.xml" \
  --pytest-junit "$evidence_dir/pytest-debug.xml" \
  --output "$evidence_dir/g2b_controller_evidence_debug.json"
```

The generator rejects a module imported from outside the declared build tree
and records its binary hash, Python ABI, CMake cache, approved configuration,
G0 validator, and all 26 S0 matrix rows. Each row binds the actual collected
CTest/pytest node to bounded raw traces containing inputs, independent expected
values, actual values, units, tolerances, comparisons, and—where applicable—
P/I/D, anti-windup, pairing, or atomic-rejection snapshots. CI retains the JSON
together with CTest/pytest XML and logs for both Debug and Release. These are
component checks, not a claim that G3 scenarios, SIL, HIL, board execution, or
flight have passed.
