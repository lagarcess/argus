"""Verify the actual UI-only Plan state without a simulator, service, or model call."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory(prefix="cuadrao-plan-checks-") as folder:
    binary = Path(folder) / "checks"
    subprocess.run([
        "xcrun", "swiftc", "-module-cache-path", "/private/tmp/cuadrao-native-design-build/ModuleCache.noindex",
        str(root / "ios/ArgusFoundation/Cuadrao/Planning/CuadraoPlanPreview.swift"),
        str(Path(__file__).with_name("PlanPreviewChecks.swift")), "-o", str(binary)
    ], check=True)
    subprocess.run([str(binary)], check=True)
