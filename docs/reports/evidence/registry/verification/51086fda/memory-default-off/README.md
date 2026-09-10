# Default-off memory test diagnosis

The unexpected test failure is caused by local configuration reaching a non-hermetic test, not a registry runtime regression or prior test ordering.

At test time `.env:426` supplies `ARGUS_ENABLE_PERSONALIZATION_MEMORY=true`. The autouse `reset_guest_funnel_milestones` fixture (`tests/conftest.py:28`) imports `argus.api.state`, which invokes `load_project_dotenv()` (`src/argus/api/state.py:20`). The loader preserves explicit shell environment values (`src/argus/env.py:32`). `MemoryServiceConfig.available` intentionally derives from that flag (`src/argus/memory/service.py:118-132`). The target test (`tests/memory/test_saved_decision_lifecycle.py:271-293`) neither clears it nor supplies a disabled config, so the enabled service correctly reaches its clock. The default-off guard still raises before the clock when the flag is absent/false.

Free fresh-process evidence:

| Probe | Flag at target test | Result |
| --- | --- | --- |
| Target test, shell flag absent and local dotenv retained | true | 1 failed, original clock assertion |
| Entire lifecycle file, explicit shell flag false | false | 10 passed |
| Target test, shell flag true but temporary pytest hook clears it immediately before the test | absent | 1 passed |

The temporary hook only models the proposed test isolation; it does not change repository tests or service code. Exact commands, logs, exit codes and hashes are in `results.json`; `run_probes.py` and `memory_flag_probe.py` reproduce them. No provider evaluation was requested. All child processes completed.

At observation, HEAD was `5d6261a3a82bb2979c8abfa5db1a65ef972f0f32`; root was reconciling integration `51086fda2014ddac2aba821a827c7b19234be779`. The memory service, target test, memory conftest, global conftest, and dotenv loader are byte-identical to that integration commit; hashes are retained in `results.json`. These are source-equality controls, not an independently executed full integration suite.

Smallest optional fix: give this one test a `monkeypatch: pytest.MonkeyPatch` argument and call `monkeypatch.delenv("ARGUS_ENABLE_PERSONALIZATION_MEMORY", raising=False)` before constructing the service. This preserves the test's absent-flag/default-off assertion. For a clean deterministic run without changing any file, explicitly set `ARGUS_ENABLE_PERSONALIZATION_MEMORY=false`. No runtime fix is indicated. No source or Git edits were made.
