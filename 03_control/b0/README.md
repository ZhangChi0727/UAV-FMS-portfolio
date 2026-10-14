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

After a successful build, retain a deterministic component trace with the
matching module and build tree (shown for Debug):

```sh
python 03_control/b0/evidence.py \
  --module-dir build/b0-controller/debug/03_control/b0 \
  --build-dir build/b0-controller/debug \
  --build-type Debug \
  --output build/b0-controller/debug/g2b_controller_evidence_debug.json
```

The generator rejects a module imported from outside the declared build tree
and records its binary hash, Python ABI, CMake cache, approved configuration,
G0 validator, independent numeric oracles, paired timing, and state before and
after an invalid-input rejection. CI retains the JSON together with CTest XML
and logs for both Debug and Release. These are component checks, not a claim
that G3 scenarios, SIL, HIL, board execution, or flight have passed.
