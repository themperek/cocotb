# Code Review Report

## Overview
Refactors the cocotb pytest plugin to use pytest fixtures (a new `runner` fixture returning `FixtureRunner`, plus the existing `dut` fixture) to build the HDL design and prepare simulation runtime, replacing the previous collector-based approach (Runner, Testbench, `hdl.py`, `hookspecs.py`). Introduces two regression manager modes (pytest-native vs. cocotb-wrapped) and substantially restructures the plugin test suite. 4,525-line diff across 31 files.

## Scope
Most recent commit: 6de7c813 "feat(pytest-plugin): using fixtures to build HDL design and prepare runtime to run simulation"
Git diff command: `git diff HEAD^..HEAD`

## Issues

### 1. [CRITICAL] src/cocotb_tools/_pytest/runner.py:210 — Infinite recursion in FixtureRunner._get_parameter_options
**Confidence:** 100
**Flagged by:** Bug Scanner
**Description:** `FixtureRunner._get_parameter_options` calls itself instead of delegating to the wrapped `Runner` instance:
```python
def _get_parameter_options(self, parameters: Mapping[str, object]) -> _Command:
    return self._get_parameter_options(parameters)
```
Every sibling passthrough (`_simulator_in_path`, `_build_command`, `_test_command`, `_get_include_options`, `_get_define_options`) correctly delegates to `self.instance.*`. This one recurses without bound and will raise `RecursionError` the first time any backend `_build_command`/`_test_command` calls `self._get_parameter_options(...)` — i.e. on any `build()`/`test()` invocation through the new `runner` fixture (Icarus, Verilator, Questa backends all take this path).
**Suggested fix:**
```python
def _get_parameter_options(self, parameters: Mapping[str, object]) -> _Command:
    return self.instance._get_parameter_options(parameters)
```

### 2. [CRITICAL] docs/source/pytest_plugin_reference.rst:21-94 — Sphinx autodoc directives reference deleted symbols
**Confidence:** 100
**Flagged by:** Historical Context / Previous Commit / Code Comments
**Description:** This commit deletes `src/cocotb_tools/_pytest/hdl.py` (the `HDL` class), `src/cocotb_tools/_pytest/hookspecs.py` (`pytest_cocotb_make_hdl`, `pytest_cocotb_make_runner`), the `hdl_session`/`hdl` fixtures, and 17 of ~19 `cocotb_*` markers, but leaves `docs/source/pytest_plugin_reference.rst` completely untouched. Its `.. autofixture::`/`.. autoclass::`/`.. autofunction::` directives for `hdl_session`, `hdl`, `HDL`, both `pytest_cocotb_*` hooks, and ~17 deleted markers are all now unresolvable. `docs/source/conf.py` loads `sphinx_autofixture` and `.readthedocs.yml` builds this file via Sphinx, so the docs build will error out. This directly violates the intent of the immediately-prior commit a1a7d211, which co-located this reference doc specifically to keep it in lockstep with the private module's public surface.
**Suggested fix:** Rewrite `pytest_plugin_reference.rst` to document the new fixtures (`dut`, `runner`) and remaining markers (`cocotb`, `cocotb_timeout`); drop the "HDL Fixture Request" and "Hook Specifications" sections entirely.

### 3. [CRITICAL] docs/source/pytest_plugin.rst:99-565 — Narrative doc still teaches the deleted HDL/hookspecs API
**Confidence:** 100
**Flagged by:** Previous Commit / Code Comments
**Description:** The narrative guide (including the "By Hooks" extensibility section, which the doc recommends as the primary integration path) walks users through `@pytest.mark.cocotb_runner`, `@pytest.mark.cocotb_test`, the `HDL` class, the `<Runner>`/`<Testbench>` collection-tree UI, and the `hookspecs` module with multiple full code examples. All of that machinery is deleted in this commit. Not touched at all. Same a1a7d211 co-location intent violated as Finding 2.
**Suggested fix:** Full rewrite of the narrative to match the new fixture-based plugin.

### 4. [MAJOR] src/cocotb_tools/_pytest/_controller.py:263 — Dedup key uses filesystem path, silently drops class-scoped fixture collisions
**Confidence:** 100
**Flagged by:** Bug Scanner
**Description:** In `Controller._collect`, the seen-set key is `(parent.path, name)`. `Path` is a filesystem path — for `class`-scoped DUT fixtures, `parent` is a `pytest.Class` node and `Class.path` equals the containing `Module.path`. If a single test module defines two classes each with their own same-named class-scoped sim-handle fixture (e.g. both named `dut`), the second class's `(path, "dut")` collides with the first's, `_collect` returns `None`, and that class's tests are silently dropped from collection — no error, no skip marker.
**Suggested fix:** Key on the parent's identity, e.g. `seen: tuple[str, str] = (parent.nodeid, name)`.

### 5. [MAJOR] src/cocotb_tools/_pytest/_controller.py:14 — Module docstring still claims responsibility for deleted nodeid mangling
**Confidence:** 100
**Flagged by:** Code Comments
**Description:** The module docstring lists nodeid "mangling" as one of `Controller`'s responsibilities, but `_get_mangled_nodeid` and its call site were deleted in this commit; no mangling logic remains anywhere in the plugin (the equivalent responsibility now lives in `_regression.py`'s in-child-process nodeid rewrite).
**Suggested fix:** Remove the mangling bullet from the docstring, or replace with a reference to the new location.

### 6. [MAJOR] src/cocotb_tools/_pytest/_controller.py:222 — _collect docstring documents the old generator signature
**Confidence:** 100
**Flagged by:** Code Comments
**Description:** `_collect`'s docstring documents parameters `collector, items` and a `Yields:` section, but the method was rewritten to `_collect(self, item: Item | Collector) -> Item | Collector | None` — a single-argument method that returns rather than yields.
**Suggested fix:** Rewrite the docstring to describe the new signature and return-value semantics.

### 7. [MINOR] tests/pytest_plugin/conftest.py:46,52 — Docstrings/example reintroduce old `cocotb_tools.pytest.plugin` path
**Confidence:** 100
**Flagged by:** Previous Commit
**Description:** Prose and a toml example reference `cocotb_tools.pytest.plugin`, but the working code three lines away and the actual packaging in `pyproject.toml` use `cocotb_tools._pytest.plugin`. Commit a1a7d211 explicitly fixed exactly this docstring; this commit rewrote the file and reintroduced the pre-a1a7d211 name in fresh prose.
**Suggested fix:** Replace `cocotb_tools.pytest.plugin` with `cocotb_tools._pytest.plugin` in both docstring and toml example.

### 8. [MINOR] tests/pytest_plugin/test_mark.py:15,23 — Docstrings reference old `cocotb_tools.pytest.mark` path
**Confidence:** 100
**Flagged by:** Previous Commit
**Description:** Same regression pattern as Finding 7 in a newly added file: import uses `cocotb_tools._pytest` correctly, but docstrings reference `cocotb_tools.pytest.mark`.
**Suggested fix:** Replace `cocotb_tools.pytest.mark` with `cocotb_tools._pytest.mark` in both docstrings.

### 9. [MINOR] tests/pytest_plugin/test_handle.py:15 — Docstring references old `cocotb_tools.pytest._handle` path
**Confidence:** 100
**Flagged by:** Previous Commit
**Description:** Same pattern: the module docstring on line 5 correctly uses `cocotb_tools._pytest._handle`, but the docstring on line 15 uses `cocotb_tools.pytest._handle`. Internally inconsistent, and inconsistent with the import.
**Suggested fix:** Fix the line-15 docstring to match line 5.

### 10. [CRITICAL] src/cocotb_tools/_pytest/runner.py:111-123 — FixtureRunner.build ignores stored hdl_toplevel on rebuild
**Confidence:** 75
**Flagged by:** Bug Scanner
**Description:** `FixtureRunner.build()` records `self.hdl_toplevel = hdl_toplevel` when the arg is truthy, then forwards the raw parameter to `self.instance.build(hdl_toplevel=hdl_toplevel, ...)`. Unlike `test()` (line 165) which does `hdl_toplevel=hdl_toplevel or self.hdl_toplevel`, `build()` does not fall back to the stored value. A second `build()` call without re-passing `hdl_toplevel` will pass `None` to the backend even though `self.hdl_toplevel` still holds a value — inconsistent with `test()`, and simulators like Icarus raise `ValueError` when `hdl_toplevel is None` at build time.
**Suggested fix:** `hdl_toplevel=hdl_toplevel or self.hdl_toplevel` in the `self.instance.build(...)` call, matching `test()`.

### 11. [MAJOR] src/cocotb_tools/_pytest/plugin.py:460-463 — Session-scoped multi-toplevel build sharing dropped
**Confidence:** 75
**Flagged by:** Historical Context
**Description:** The deleted `hdl_session` fixture (session-scoped, added in `41957a2e`) supported building a single HDL project containing multiple toplevels once per session and handing out per-toplevel views via `HDL.build_dir`/`HDL.toplevel` reassignment; the deleted `tests/pytest_plugin/test_session.py` exercised this scenario (and carried the Icarus-unpacked-structs skip fix from `91c613cb`). The new `runner` fixture is `@fixture(scope="module")` only, with no session-scoped counterpart, and `FixtureRunner.__init__` derives `build_dir` from `request.node.path` (the test file). Users could hand-roll `FixtureRunner(request)` in their own session-scoped fixture, but that path is untested and undocumented.
**Suggested fix:** Either add a session-scoped `runner` variant, document/test the manual workaround, or explicitly call out the dropped capability in the changelog/docs.

### 12. [MINOR] src/cocotb_tools/_pytest/_regression.py:112 — nodeid docstring disagrees with _init.py call-site comment
**Confidence:** 75
**Flagged by:** Code Comments
**Description:** `RegressionManager.__init__`'s docstring describes `nodeid` as "Node identifier of cocotb runner," but the updated call site comment in `_init.py` says "Node identifier of simulation process" (nodeid is now derived from the simulator subprocess's own `PYTEST_CURRENT_TEST` after stripping the `" (call)"` suffix, not from the parent-process runner item). The two comments disagree on the semantic meaning; user-facing JUnit XML `user_properties` (`runner_nodeid`) inherits whichever description is authoritative.
**Suggested fix:** Update the `RegressionManager` docstring to match the new "simulation process" semantics, or pick one term and use it consistently across `_init.py`, `_regression.py`, and the JUnit XML property description.

---

No issues scoring below 75 are included. 2 additional findings were filtered out (Finding 7 "test_fixture.py sync/generator coverage gap" scored 50; Finding 11 "deleted array_module Icarus skip" scored 50 — both plausible but likely intentional narrowing).
