from __future__ import annotations

import os

try:
    from render_sdk import Retry, Workflows
except ModuleNotFoundError as exc:  # pragma: no cover - exercised in workflow env
    raise RuntimeError(
        "render_sdk is required to run the Render Workflow service. Install "
        "the Poetry workflows group with: "
        "poetry install --only workflows --no-root --no-interaction."
    ) from exc

try:
    from workflows.proof import PostgresProofJobGateway, run_workflow_proof
except ModuleNotFoundError:  # pragma: no cover - supports `python workflows/main.py`
    from proof import PostgresProofJobGateway, run_workflow_proof


app = Workflows(
    default_retry=Retry(max_retries=0, wait_duration_ms=1000),
    default_timeout=60,
    default_plan=os.getenv("ARGUS_WORKFLOW_PROOF_PLAN", "starter"),
)


@app.task(name="workflow_proof", timeout_seconds=60)
def workflow_proof(job_id: str, nonce: str) -> dict[str, object]:
    return run_workflow_proof(
        PostgresProofJobGateway.from_env(),
        job_id=job_id,
        nonce=nonce,
        workflow_run_id=os.getenv("RENDER_TASK_RUN_ID"),
    )


if __name__ == "__main__":
    app.start()
