"""Check which edges a connected Home row registers with the iOS 27 swipe container."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory(prefix="cuadrao-connected-swipe-") as temporary:
    folder = Path(temporary)
    source = (root / "ios/ArgusFoundation/Connected/ConnectedSwipeRow.swift").read_text()
    registration = source[source.index("struct ConnectedSwipeRegistration:"):source.index("struct ConnectedSwipeRow<")]
    (folder / "ConnectedSwipeRegistration.swift").write_text("import SwiftUI\n" + registration)
    binary = folder / "checks"
    subprocess.run([
        "xcrun", "swiftc", "-module-cache-path", str(folder / "module-cache"),
        str(folder / "ConnectedSwipeRegistration.swift"),
        str(Path(__file__).with_name("ConnectedSwipeChecks.swift")), "-o", str(binary),
    ], check=True)
    subprocess.run([str(binary)], check=True)
