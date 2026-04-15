# P6 XER EVM Analyzer

This project is a standalone-friendly Python desktop application for comparing:

- duration-weighted baseline planned progress by the current schedule data date
- duration-weighted current actualized progress
- progress variance by matched WBS branch
- current remaining WBS span versus SPI-revised remaining WBS span

The app reads Primavera P6 `.xer` files directly and lets the user:

- choose one baseline XER file
- choose one current update XER file
- add or remove WBS search rows
- match against both `wbs_short_name` and `wbs_name` using partial text matching
- include all descendant WBS activities under each matched WBS
- review the results in a desktop table
- export the results to CSV

## Current calculation rules

- Baseline activity sum uses `TASK.target_drtn_hr_cnt` summed across all matched activities in the WBS branch.
- Baseline planned activity sum uses the baseline task dates against the current schedule data date.
- If the current data date is inside a baseline activity, planned duration is prorated linearly between start and finish.
- Current actualized activity sum uses `target_drtn_hr_cnt - remain_drtn_hr_cnt`.
- Percentages are duration-weighted percentages based on the summed activity duration within each matched WBS branch.
- These values are not the true WBS time span from earliest start to latest finish.
- XER duration fields are stored in hours, but the app converts reported results to days using each schedule's configured hours-per-day value.
- SPI is calculated as `current actual % / baseline planned %`.
- The SPI-based remaining span analysis uses the baseline file only for SPI. The remaining-span forecast itself is derived from the current schedule's data date and current forecast finish.
- Current remaining span and revised remaining span are calculated using a Monday-Friday working-day assumption, not elapsed calendar days.

## Run locally

```bash
python3 -m evm_xer_analyzer
```

## Package installation

```bash
python3 -m pip install -e .
```

After installation, the GUI launcher is:

```bash
evm-xer-analyzer
```

## Standalone packaging path

The code is separated into:

- `evm_xer_analyzer/xer_parser.py` for XER parsing
- `evm_xer_analyzer/analysis.py` for business logic
- `evm_xer_analyzer/gui.py` for the desktop interface

That split is intentional so later packaging is simpler on both macOS and Windows.

### Local PyInstaller build

Install the build dependencies:

```bash
python3 -m pip install -e ".[build]"
```

Build from the project root:

```bash
python3 scripts/package_app.py --clean
```

This writes zipped standalone artifacts into `release/`.

For Windows, build on Windows. For macOS, build on macOS. PyInstaller does not cross-compile native desktop executables reliably across operating systems.

## GitHub Actions Build

The repository includes a GitHub Actions workflow at `.github/workflows/build.yml`.

It will:

- build the app on `macos-latest` and `windows-latest`
- run the unit tests before packaging
- upload zipped build artifacts for each workflow run
- publish those zipped artifacts to a GitHub Release when you push a tag like `v0.1.0`

### Push flow

Initialize the local repository if needed:

```bash
git init
git add .
git commit -m "Initial commit"
```

Add your GitHub remote:

```bash
git remote add origin <YOUR_GITHUB_REPO_URL>
git branch -M main
git push -u origin main
```

To create a release build later:

```bash
git tag v0.1.0
git push origin v0.1.0
```

That tag push will trigger the workflow and publish macOS and Windows release assets on GitHub.
