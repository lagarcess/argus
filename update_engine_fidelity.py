import re

with open("src/argus/engine.py", "r") as f:
    content = f.read()

# Make sure we use np.corrcoef as requested in instructions
fidelity_replacement = """        if isinstance(ideal_returns_series, pd.DataFrame):
            ideal_var = ideal_returns_series.var().mean()
            real_var = real_returns_series.var().mean()
            if ideal_var > 0 and real_var > 0:
                # Use numpy for high performance matrix correlation
                ideal_arr = ideal_returns_series.sum(axis=1).values
                real_arr = real_returns_series.sum(axis=1).values
                fidelity_score = float(np.corrcoef(ideal_arr, real_arr)[0, 1])
            else:
                fidelity_score = 1.0
        else:
            if ideal_returns_series.var() > 0 and real_returns_series.var() > 0:
                fidelity_score = float(np.corrcoef(ideal_returns_series.values, real_returns_series.values)[0, 1])
            else:
                fidelity_score = 1.0"""

content = re.sub(
    r"        if isinstance\(ideal_returns_series, pd\.DataFrame\):[\s\S]*?            else:\n                fidelity_score = 1\.0",
    fidelity_replacement,
    content,
)

# Add numpy import to engine.py if missing
if "import numpy as np" not in content:
    content = content.replace(
        "import pandas as pd", "import pandas as pd\nimport numpy as np"
    )

with open("src/argus/engine.py", "w") as f:
    f.write(content)

with open("src/argus/api/main.py", "r") as f:
    content = f.read()

# Add psutil Memory Gate to run_backtest before strategy fetch / execution
memory_gate = """    logger.info(f"Fetching strategy {payload.strategy_id} for backtest")

    # Memory Gate: Check if available memory is < 15%
    import psutil
    mem = psutil.virtual_memory()
    if mem.percent > 85.0:
        logger.error(f"OOM Risk: Available memory is at {100 - mem.percent:.1f}%. Rejecting backtest.")
        raise HTTPException(
            status_code=503,
            detail="System memory is critically low. Please try again later."
        )"""

content = content.replace(
    '    logger.info(f"Fetching strategy {payload.strategy_id} for backtest")',
    memory_gate,
)

with open("src/argus/api/main.py", "w") as f:
    f.write(content)
