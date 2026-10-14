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

The Python test asserts the actual imported extension path. `python/controller.py` validates the approved implementation configuration and the actual G0 file before mapping frozen G2-A/G1 message fields. These are component checks, not a claim that G3 scenarios, HIL or flight have passed.
