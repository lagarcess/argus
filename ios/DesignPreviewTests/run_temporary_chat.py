"""Run the native preview's actual chat model, using the existing build cache."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
canvas = root / "ios/ArgusFoundation/Cuadrao"
with tempfile.TemporaryDirectory(prefix="cuadrao-chat-checks-") as folder:
    work = Path(folder)
    # Use the exact fixture declarations; the view below them is irrelevant to state checks.
    fixtures = (canvas / "CuadraoSearchReferences.swift").read_text().split("struct CuadraoSearchReferenceDetail: View {")[0]
    (work / "References.swift").write_text(fixtures)
    binary = work / "checks"
    subprocess.run([
        "xcrun", "swiftc", "-module-cache-path", "/private/tmp/cuadrao-native-design-build/ModuleCache.noindex",
        str(canvas / "CuadraoChatPreview.swift"), str(canvas / "CuadraoVoicePreview.swift"), str(canvas / "CuadraoVoiceMessagePreview.swift"), str(work / "References.swift"),
        str(Path(__file__).with_name("TemporaryChatChecks.swift")), "-o", str(binary)
    ], check=True)
    subprocess.run([str(binary)], check=True)
