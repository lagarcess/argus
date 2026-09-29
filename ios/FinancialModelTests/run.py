"""Test the actual native presentation models without changing signing/project files."""
from pathlib import Path
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory(prefix="argus-financial-models-") as temporary:
    package = Path(temporary)
    source = package / "Sources/FinancialModels"
    tests = package / "Tests/FinancialModelTests"
    source.mkdir(parents=True)
    tests.mkdir(parents=True)
    for name in ("AccountsModel.swift", "FinancialLoopModel.swift", "AccountEntry.swift"):
        shutil.copy(root / "ios/ArgusFoundation/Accounts" / name, source / name)
    # The formatter remains one production source; copy its exact declaration.
    presentation = (root / "ios/ArgusFoundation/Accounts/AccountsView.swift").read_text()
    (source / "AccountPresentation.swift").write_text("import Foundation\nimport ArgusSession\n" + presentation[presentation.index("enum AccountPresentation {"):])
    shutil.copy(root / "ios/Packages/ArgusSession/Tests/ArgusSessionTests/TestSupport.swift", tests / "TestSupport.swift")
    shutil.copy(Path(__file__).with_name("FinancialModelTests.swift"), tests / "FinancialModelTests.swift")
    (package / "Package.swift").write_text('''// swift-tools-version: 6.0
import PackageDescription
let package = Package(name: "FinancialModels", platforms: [.macOS(.v14)], dependencies: [
    .package(path: "''' + str(root / "ios/Packages/ArgusSession") + '''"),
    .package(url: "https://github.com/supabase/supabase-swift.git", exact: "2.55.2")
], targets: [
    .target(name: "FinancialModels", dependencies: [.product(name: "ArgusSession", package: "ArgusSession")]),
    .testTarget(name: "FinancialModelTests", dependencies: ["FinancialModels", .product(name: "ArgusSession", package: "ArgusSession"), .product(name: "Auth", package: "supabase-swift")])
])
''')
    subprocess.run(["swift", "test", "--package-path", str(package), "--scratch-path", str(root / "ios/.build/financial-model-tests")], check=True)
