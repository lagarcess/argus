"""Exercise the actual Household presentation model with controlled transport delays."""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory(prefix="argus-household-models-") as temporary:
    package = Path(temporary)
    source = package / "Sources/FinancialModels"
    tests = package / "Tests/FinancialModelTests"
    source.mkdir(parents=True)
    tests.mkdir(parents=True)
    shutil.copy(root / "ios/ArgusFoundation/Household/HouseholdModel.swift", source)
    shutil.copy(root / "ios/ArgusFoundation/Accounts/AccountEntry.swift", source)
    editor = (
        root / "ios/ArgusFoundation/Household/HouseholdActivityEditor.swift"
    ).read_text()
    (source / "HouseholdActivityEditor.swift").write_text(
        editor[: editor.index("struct HouseholdActivityEditorView:")]
    )
    presentation = (root / "ios/ArgusFoundation/Accounts/AccountsView.swift").read_text()
    (source / "AccountPresentation.swift").write_text(
        "import Foundation\nimport ArgusSession\n"
        + presentation[presentation.index("enum AccountPresentation {") :]
    )
    shutil.copy(
        root / "ios/Packages/ArgusSession/Tests/ArgusSessionTests/TestSupport.swift",
        tests,
    )
    shutil.copy(Path(__file__).with_name("HouseholdModelTests.swift"), tests)
    (package / "Package.swift").write_text(
        '''// swift-tools-version: 6.0
import PackageDescription
let package = Package(name: "FinancialModels", platforms: [.macOS(.v14)], dependencies: [
    .package(path: "'''
        + str(root / "ios/Packages/ArgusSession")
        + """"),
    .package(url: "https://github.com/supabase/supabase-swift.git", exact: "2.55.2")
], targets: [
    .target(name: "FinancialModels", dependencies: [.product(name: "ArgusSession", package: "ArgusSession")]),
    .testTarget(name: "FinancialModelTests", dependencies: ["FinancialModels", .product(name: "ArgusSession", package: "ArgusSession"), .product(name: "Auth", package: "supabase-swift")])
])
"""
    )
    shutil.copy(
        root / "ios/Packages/ArgusSession/Package.resolved", package / "Package.resolved"
    )
    scratch = Path(
        os.environ.get(
            "ARGUS_HOUSEHOLD_MODEL_SCRATCH_PATH",
            root / "ios/.build/household-model-tests",
        )
    )
    subprocess.run(
        [
            "swift",
            "test",
            "--package-path",
            str(package),
            "--scratch-path",
            str(scratch),
            "--disable-sandbox",
            "--disable-automatic-resolution",
        ],
        check=True,
    )
