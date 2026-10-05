"""Check connected summary presentation using its production types and formatter."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory(prefix="cuadrao-connected-balance-") as temporary:
    folder = Path(temporary)
    types = (root / "ios/Packages/ArgusSession/Sources/ArgusSession/FinancialLoopTypes.swift").read_text()
    summary = types[types.index("public struct FinancialCurrencySummary:"):types.index("public struct FinancialHomePeriod:")]
    (folder / "Summary.swift").write_text("import Foundation\n" + summary)
    formatter = (root / "ios/ArgusFoundation/Accounts/AccountsView.swift").read_text()
    (folder / "AccountPresentation.swift").write_text(
        "import Foundation\nenum AccountPresentation {\n" + formatter[formatter.index("    static func decimal("):])
    source = (root / "ios/ArgusFoundation/Connected/ConnectedBalanceSummary.swift").read_text()
    (folder / "ConnectedBalanceSummary.swift").write_text(source.replace("import ArgusSession\n", ""))
    binary = folder / "checks"
    subprocess.run([
        "xcrun", "swiftc", "-module-cache-path", str(folder / "module-cache"),
        str(folder / "Summary.swift"), str(folder / "AccountPresentation.swift"),
        str(folder / "ConnectedBalanceSummary.swift"),
        str(Path(__file__).with_name("ConnectedBalanceSummaryChecks.swift")), "-o", str(binary),
    ], check=True)
    subprocess.run([str(binary)], check=True)
