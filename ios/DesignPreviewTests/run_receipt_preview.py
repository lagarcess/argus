"""Run receipt arithmetic and durable preview journeys without a simulator."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
canvas = root / "ios/ArgusFoundation/Cuadrao"
with tempfile.TemporaryDirectory(prefix="cuadrao-receipt-checks-") as temporary:
    folder = Path(temporary)
    source = (canvas / "CuadraoAccountsPreview.swift").read_text().split("struct CanvasAccountIcon:")[0]
    (folder / "Accounts.swift").write_text(source)
    (folder / "Household.swift").write_text("enum CanvasHouseholdState { case alone, joined(String) }")
    files = [folder / "Accounts.swift", folder / "Household.swift"]
    files += [canvas / name for name in [
        "CanvasMoney.swift", "CuadraoSpacesPreview.swift", "CuadraoCollectionOrder.swift",
        "CuadraoSpendingHistory.swift", "CuadraoSpendingStory.swift", "CuadraoBalanceHistory.swift", "CuadraoBalancePeriod.swift",
        "Planning/CuadraoPlanPreview.swift", "Planning/CuadraoGroupPreview.swift",
        "Receipts/CuadraoReceipt.swift", "Receipts/CuadraoReceiptStore.swift",
    ]]
    files.append(Path(__file__).with_name("ReceiptPreviewChecks.swift"))
    subprocess.run(["xcrun", "swiftc", "-module-cache-path", str(folder / "modules"),
                    *map(str, files), "-o", str(folder / "checks")], check=True)
    subprocess.run([str(folder / "checks")], check=True)
