"""Compare CanvasMoney with the formatter-per-call implementation it replaced, per device locale."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory(prefix="cuadrao-money-checks-") as folder:
    binary = Path(folder) / "checks"
    subprocess.run([
        "xcrun", "swiftc", "-O", "-module-cache-path", "/private/tmp/cuadrao-native-design-build/ModuleCache.noindex",
        str(root / "ios/ArgusFoundation/Cuadrao/CanvasMoney.swift"),
        str(Path(__file__).with_name("MoneyFormatChecks.swift")), "-o", str(binary)
    ], check=True)
    subprocess.run([str(binary)], check=True)
    for locale in ["en_US", "es_419", "es_DO", "es_US", "ja_JP", "de_CH", "ar_KW", "en_US@currency=JPY"]:
        subprocess.run([str(binary), "-AppleLocale", locale], check=True)
