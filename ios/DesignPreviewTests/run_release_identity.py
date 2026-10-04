"""Run pure identity-state checks without a simulator, account service or provider."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
identity = root / "ios/ArgusFoundation/ReleaseUI/Identity"
with tempfile.TemporaryDirectory(prefix="cuadrao-identity-checks-") as folder:
    executable = str(Path(folder) / "checks")
    subprocess.run([
        "xcrun", "swiftc", "-module-cache-path", str(Path(folder) / "ModuleCache"),
        str(identity / "ReleaseIdentityModels.swift"),
        str(Path(__file__).with_name("ReleaseIdentityChecks.swift")), "-o", executable,
    ], check=True)
    subprocess.run([executable], check=True)
