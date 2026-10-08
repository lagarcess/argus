"""Run N fresh pytest processes through run.sh; append one line per run to runs.log."""
import subprocess, sys, time, re, xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

P = Path(__file__).parent
mode, n = sys.argv[1], int(sys.argv[2])
targets = {
    "storage": ["tests/test_document_source_objects_postgres.py"],
    "combined": ["tests/test_document_jobs_postgres.py", "tests/test_document_source_objects_postgres.py"],
}[mode]
NAMED = (
    "test_disconnect_removes_the_object_and_keeps_confirmed_activity",
    "test_disconnect_during_preparation_leaves_no_object_and_no_row",
)
tally: Counter = Counter()
with open(P / "runs.log", "a") as log:
    log.write(f"\n== {mode}: {n} runs, targets {' '.join(targets)} ({time.strftime('%Y-%m-%dT%H:%M:%S%z')})\n")
    for i in range(1, n + 1):
        label = f"{mode}-{i:02d}"
        started = time.time()
        try:
            code = subprocess.run([str(P / "run.sh"), label, *targets], timeout=900).returncode
        except subprocess.TimeoutExpired:
            code = "TIMEOUT"
        text = (P / "runs" / f"{label}.log").read_text()
        summary = [l for l in text.splitlines() if re.match(r"^=+ .*(passed|failed|error).* in ", l)]
        cases = {}
        if (P / "runs" / f"{label}.xml").exists():
            for tc in ET.parse(P / "runs" / f"{label}.xml").getroot().iter("testcase"):
                bad = tc.find("failure") is not None or tc.find("error") is not None
                skipped = tc.find("skipped") is not None
                status = "FAIL" if bad else "SKIP" if skipped else "PASS"
                cases[f"{tc.get('classname')}::{tc.get('name')}"] = status
                tally[(tc.get("classname"), tc.get("name"), status)] += 1
        named = " ".join(f"{name[:40]}={next((s for k, s in cases.items() if k.endswith('::' + name)), 'MISSING')}" for name in NAMED)
        failed = [k for k, s in cases.items() if s != "PASS"]
        log.write(f"{label} exit={code} {time.time() - started:5.1f}s | {summary[-1].strip('= ') if summary else 'NO SUMMARY LINE'} | {named}" + (f" | NOT PASSED: {failed}" if failed else "") + "\n")
        log.flush()
    log.write(f"-- {mode} per-test tally (classname, name, status): count\n")
    for (cls, name, status), count in sorted(tally.items()):
        log.write(f"   {cls}::{name} {status} {count}/{n}\n")
