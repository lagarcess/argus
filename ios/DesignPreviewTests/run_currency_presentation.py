"""Check currency ordering and forecast selection without a service or simulator."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory(prefix="cuadrao-currency-presentation-") as temporary:
    folder = Path(temporary)
    binary = folder / "checks"
    subprocess.run([
        "xcrun", "swiftc", "-module-cache-path", str(folder / "module-cache"),
        str(root / "ios/ArgusFoundation/Currency/CurrencyPresentation.swift"),
        str(Path(__file__).with_name("CurrencyPresentationChecks.swift")), "-o", str(binary),
    ], check=True)
    subprocess.run([str(binary)], check=True)
