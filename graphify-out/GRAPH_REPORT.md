# Graph Report - academia  (2026-10-06)

## Corpus Check
- 52 files · ~12,960 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 364 nodes · 1054 edges · 23 communities (9 shown, 7 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 82 edges (avg confidence: 0.94)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `61e6000e`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- png
- vision.py
- AcademicError
- Config
- QuizDesktop
- load_config
- QuestionRunner
- RunControl
- CliTests
- release-notes.md
- verify.py
- LiveApiKeyTests
- build.py
- main.sh script
- academic-helper
- package_release.py

## God Nodes (most connected - your core abstractions)
1. `AcademicError` - 93 edges
2. `png()` - 39 edges
3. `QuizDesktop` - 34 edges
4. `RunnerTests` - 29 edges
5. `Config` - 26 edges
6. `WindowsDesktop` - 26 edges
7. `DesktopTests` - 26 edges
8. `load_config()` - 25 edges
9. `Window` - 25 edges
10. `question()` - 25 edges

## Surprising Connections (you probably didn't know these)
- `HttpTests` --uses--> `Config`  [INFERRED]
  tests/integration/test_http.py → main/config.py
- `CliTests` --uses--> `Config`  [INFERRED]
  tests/unit/test_cli.py → main/config.py
- `CliTests` --uses--> `RunControl`  [INFERRED]
  tests/unit/test_cli.py → main/control.py
- `QuizDesktop` --uses--> `Window`  [INFERRED]
  tests/support/helpers.py → main/desktop.py
- `LiveApiKeyTests` --uses--> `AcademicError`  [INFERRED]
  tests/live/router.py → main/errors.py

## Import Cycles
- None detected.

## Communities (23 total, 7 thin omitted)

### Community 0 - "png"
Cohesion: 0.07
Nodes (22): Desktop, Frame, HyprlandDesktop, screen_point(), Window, Point, Input, InputUnion (+14 more)

### Community 1 - "vision.py"
Cohesion: 0.13
Nodes (12): _boolean(), _fields(), NextButton, Observation, Option, parse_observation(), Validate a model's proposed actions before they reach the desktop., _text() (+4 more)

### Community 2 - "AcademicError"
Cohesion: 0.07
Nodes (33): ArgumentParser, Exception, main(), parser(), positive_count(), CLI routing for the Python application., _terminated(), create_desktop() (+25 more)

### Community 3 - "Config"
Cohesion: 0.14
Nodes (11): Config, ApiError, complete_text(), CurlTransport, RouterClient, probe(), Synthetic chat completion responses and an in-memory transport., response() (+3 more)

### Community 4 - "QuizDesktop"
Cohesion: 0.11
Nodes (8): question(), QuizDesktop, QuizVision, A deterministic quiz exercising the real screenshot guard and runner., stop_screen(), RunnerTests, main(), Smoke-check a Linux executable using synthetic configuration and desktop tools.

### Community 5 - "load_config"
Cohesion: 0.13
Nodes (11): config_path(), load_config(), parse_env(), Path, Read simple dotenv assignments and update the model atomically., read_env(), set_model(), validate_base_url() (+3 more)

### Community 6 - "QuestionRunner"
Cohesion: 0.20
Nodes (5): QuestionRunner, RunResult, Vision, HttpTests, skipUnless

### Community 7 - "RunControl"
Cohesion: 0.22
Nodes (6): Path, One runner at a time, with a stop command usable from a second terminal., request_stop(), RunControl, state_directory(), ControlTests

### Community 9 - "release-notes.md"
Cohesion: 0.14
Nodes (12): Academia v0.2.0 — Linux Hyprland preview, Academia v0.2.1 — Linux Hyprland preview, Academic v0.1.0 — prerelease (historical), Acceptance testing still required, Included behavior, Release assets, Unreleased — 9Router migration, Verification (+4 more)

## Knowledge Gaps
- **14 isolated node(s):** `main.sh script`, `MouseInput`, `InputUnion`, `academic-helper`, `Start` (+9 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 81 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **7 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `AcademicError` connect `AcademicError` to `png`, `vision.py`, `Config`, `QuizDesktop`, `load_config`, `QuestionRunner`, `RunControl`, `CliTests`, `LiveApiKeyTests`?**
  _High betweenness centrality (0.395) - this node is a cross-community bridge._
- **Why does `RunnerTests` connect `QuizDesktop` to `AcademicError`, `Config`, `QuestionRunner`?**
  _High betweenness centrality (0.066) - this node is a cross-community bridge._
- **Why does `QuizDesktop` connect `QuizDesktop` to `png`, `vision.py`, `AcademicError`, `Config`, `QuestionRunner`, `CliTests`?**
  _High betweenness centrality (0.054) - this node is a cross-community bridge._
- **Are the 21 inferred relationships involving `AcademicError` (e.g. with `RunControl` and `Desktop`) actually correct?**
  _`AcademicError` has 21 INFERRED edges - model-reasoned connections that need verification._
- **Are the 5 inferred relationships involving `QuizDesktop` (e.g. with `HttpTests` and `Window`) actually correct?**
  _`QuizDesktop` has 5 INFERRED edges - model-reasoned connections that need verification._
- **Are the 6 inferred relationships involving `RunnerTests` (e.g. with `AcademicError` and `ApiError`) actually correct?**
  _`RunnerTests` has 6 INFERRED edges - model-reasoned connections that need verification._
- **Are the 5 inferred relationships involving `Config` (e.g. with `RouterClient` and `HttpTests`) actually correct?**
  _`Config` has 5 INFERRED edges - model-reasoned connections that need verification._