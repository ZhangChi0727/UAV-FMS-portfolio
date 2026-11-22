# UAV FMS Portfolio

A small, reproducible engineering project with two parts:

1. **B0 attitude platform** (historical component baselines approved; migrated
   requirement text awaiting review and freeze): rigid-body and sensor
   models, a complementary attitude estimator, and a C++17 cascaded
   attitude/rate controller with a Python binding and tests.
2. **EDGE track** (planned): distributed edge AI for UAV bridge inspection.
   Language-model and vision-language inference is placed across onboard, edge
   and cloud resources, and measured by replay. See
   [requirements/edge.sdoc](requirements/edge.sdoc).

No flight, hardware or closed-loop performance result is claimed.
All numbers below come from the commands listed in this file.

## Status

| Area | Requirements | State | Evidence |
|---|---|---|---|
| B0 plant, IMU, actuator | B0-REQ-0004 to 0011 | implemented, unit-tested | `01_simulation/b0`, 25 pytest cases |
| B0 estimator | B0-REQ-0012 to 0015, 0019 | implemented, unit-tested | `02_estimation/b0`, 52 pytest cases |
| B0 controller | B0-REQ-0007, 0016 to 0019, 0026 | implemented, C++ and binding tested | `03_control/b0`, 25 CTest cases (Debug) |
| B0 closed-loop integration | B0-REQ-0002, 0003, 0020 to 0025 | not in active tree | archived at tag `pre-surgery-2026-11-22` |
| EDGE track | EDG-REQ-0001 to 0033 | planned; requirements proposed, not frozen | none yet |

B0 is not accepted as a whole. Its closed-loop integration layer, a saturation
reachability negative finding, and several evidence chains were removed from the
active tree by the lean-restructuring PR. They remain in git history at the tag
and the [archived commit](https://github.com/ZhangChi0727/UAV-FMS-portfolio/tree/d102a9e018c9b9b0b0e5385f509c2fb2c3adffbd).

## Repository layout

| Path | Content |
|---|---|
| `requirements/` | StrictDoc requirements: the single systems-engineering source |
| `01_simulation/b0/` | Frame and quaternion conventions, rigid-body plant, IMU, actuator |
| `02_estimation/b0/` | Complementary attitude estimator and its configuration |
| `03_control/b0/` | C++17 controller core, pybind11 binding, Python adapter, tests |
| `05_integration/b0/` | G0 contract (v1 and v2), its validator, and validator tests |
| `edge_inference/` | Planned learning modules for the EDGE track |
| `research/` | Scheduler and probe-timing study code and data |
| `literature/references.bib` | Bibliography |

`05_integration/b0` is kept only because the estimator and controller load and
validate the G0 contract at runtime. The approval records for the estimator and
controller are read by the same loaders.

## Reproduce

### Windows PowerShell (Python 3.11 and MinGW)

Run these commands in order from the repository root. Supply the full path to
a Python 3.11 executable and the MinGW `bin` directory when prompted. Git and
network access are needed if the pinned Catch2 source is not already available.

```powershell
$Python311 = (Read-Host 'Full path to Python 3.11 executable').Trim('"')
if (-not (Test-Path -LiteralPath $Python311 -PathType Leaf)) { throw 'Python executable not found' }
& $Python311 -c 'import sys; assert sys.version_info[:2] == (3, 11)'
if ($LASTEXITCODE -ne 0) { throw 'Python 3.11 is required' }
& $Python311 -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed' }
$VenvScripts = (Resolve-Path .venv/Scripts).Path
$Python = Join-Path $VenvScripts 'python.exe'
& $Python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }

$MinGWBin = (Read-Host 'Full path to MinGW bin directory').Trim('"')
foreach ($Name in @('g++.exe', 'libstdc++-6.dll', 'libgcc_s_seh-1.dll')) {
    if (-not (Test-Path -LiteralPath (Join-Path $MinGWBin $Name) -PathType Leaf)) {
        throw "Missing MinGW file: $Name"
    }
}
$env:PATH = "$MinGWBin;$env:PATH"
$CMake = Join-Path $VenvScripts 'cmake.exe'
$CTest = Join-Path $VenvScripts 'ctest.exe'
$Ninja = Join-Path $VenvScripts 'ninja.exe'

foreach ($Track in @('01_simulation/b0', '02_estimation/b0', '05_integration/b0')) {
    Push-Location $Track
    try {
        & $Python -B -m pytest -q
        if ($LASTEXITCODE -ne 0) { throw "Tests failed in $Track" }
    } finally { Pop-Location }
}

$BuildDir = Join-Path (Get-Location).Path 'build/win-b0-debug'
& $CMake -S . -B $BuildDir -G Ninja `
    '-DCMAKE_BUILD_TYPE=Debug' '-DBUILD_TESTING=ON' `
    "-DCMAKE_CXX_COMPILER=$(Join-Path $MinGWBin 'g++.exe')" `
    "-DCMAKE_MAKE_PROGRAM=$Ninja" "-DPython3_EXECUTABLE=$Python"
if ($LASTEXITCODE -ne 0) { throw 'CMake configuration failed' }
& $CMake --build $BuildDir --parallel 2
if ($LASTEXITCODE -ne 0) { throw 'CMake build failed' }

# Put the MinGW runtime DLLs next to the actual Python module before CTest.
$Modules = @(Get-ChildItem -LiteralPath $BuildDir -Recurse -File -Filter 'b0_controller*.pyd')
if ($Modules.Count -ne 1) { throw 'Expected exactly one controller Python module' }
foreach ($Name in @('libstdc++-6.dll', 'libgcc_s_seh-1.dll')) {
    Copy-Item -LiteralPath (Join-Path $MinGWBin $Name) -Destination $Modules[0].DirectoryName
}
& $CTest --test-dir $BuildDir --output-on-failure
if ($LASTEXITCODE -ne 0) { throw 'CTest failed' }

& (Join-Path $VenvScripts 'strictdoc.exe') export requirements --output-dir (Join-Path $BuildDir 'strictdoc')
if ($LASTEXITCODE -ne 0) { throw 'StrictDoc export failed' }
```

To use a previously retained Catch2 source without fetching it, add
`-DFETCHCONTENT_SOURCE_DIR_CATCH2=<path-to-Catch2-source>` to the configure
command. The build directory and StrictDoc output are ignored by Git. The
commands above describe the Windows Debug path; they do not claim a Linux,
Release, clean-machine, closed-loop or hardware result.

## Roadmap

1. **Now**: the lean-restructuring PR is merged; review the proposed requirements before any future freeze.
2. **EDGE-1**: task instruction to structured task (EDG-REQ-0001) on the development GPU.
3. **EDGE-2**: image to structured finding with abstention (EDG-REQ-0002).
4. **EDGE-3**: latency and resource profiling of the models (EDG-REQ-0004).
5. **EDGE-4**: placement policy and fallback on replayed scenarios (EDG-REQ-0005 to 0007).

Each step adds code, tests and a requirement update in the same change. See
[edge_inference/README.md](edge_inference/README.md) for the module structure.

## Conventions

NED navigation frame, body frame x forward, y right, z down. SI units. Quaternions
are scalar-first Hamilton, rotating body vectors into the navigation frame.
Simulation truth is never an estimator or controller input after initialization.
