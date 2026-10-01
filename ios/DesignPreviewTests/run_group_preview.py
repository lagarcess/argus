"""Verify the actual UI-only group state without a simulator, service, or model call."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory(prefix="cuadrao-group-checks-") as folder:
    binary = Path(folder) / "checks"
    subprocess.run([
        "xcrun", "swiftc", "-module-cache-path", "/private/tmp/cuadrao-native-design-build/ModuleCache.noindex",
        str(root / "ios/ArgusFoundation/Cuadrao/Planning/CuadraoPlanPreview.swift"),
        str(root / "ios/ArgusFoundation/Cuadrao/Planning/CuadraoGroupPreview.swift"),
        str(Path(__file__).with_name("GroupPreviewChecks.swift")), "-o", str(binary)
    ], check=True)
    subprocess.run([str(binary)], check=True)
