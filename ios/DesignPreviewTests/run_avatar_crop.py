"""Verify the hidden personal-photo crop geometry without a simulator, service, or model call."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory(prefix="cuadrao-avatar-checks-") as folder:
    binary = Path(folder) / "checks"
    subprocess.run([
        "xcrun", "swiftc", "-module-cache-path", "/private/tmp/cuadrao-native-design-build/ModuleCache.noindex",
        str(root / "ios/ArgusFoundation/Cuadrao/CuadraoAvatarCropGeometry.swift"),
        str(Path(__file__).with_name("AvatarCropChecks.swift")), "-o", str(binary)
    ], check=True)
    subprocess.run([str(binary)], check=True)
