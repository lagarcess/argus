import XCTest

/// Sheets close and confirm the same way everywhere: plain-text Cancel on the left, a check on the right only
/// when the sheet has no button of its own, plain-text Done on sheets that only show something.
extension FinancialLoopUITests {
    func testSheetsCancelAndConfirmTheSameWay() throws {
        try signIn()
        app.terminate()
        app.launchArguments = ["-AppleLanguages", "(en)", "-AppleLocale", "en_US", "--cuadrao-release-gates"]
        app.launch()
        XCTAssertTrue(app.buttons["header.profile"].waitForExistence(timeout: 20))

        // Edit profile has no button of its own: Cancel and a check.
        app.buttons["header.profile"].tap()
        app.staticTexts["Edit profile"].firstMatch.tap()
        let cancel = app.buttons["cuadrao.profile.cancel"]
        XCTAssertTrue(cancel.waitForExistence(timeout: 10))
        XCTAssertEqual(cancel.label, "Cancel")
        let save = app.buttons["cuadrao.profile.save"]
        XCTAssertTrue(save.exists)
        XCTAssertEqual(save.label, "Save")
        XCTAssertLessThan(cancel.frame.midX, save.frame.midX, "Cancel is on the left, the check on the right")
        XCTAssertEqual(cancel.frame.midY, save.frame.midY, accuracy: 4, "both sit on the same bar")
        capture("sheet-controls-edit-profile")
        cancel.tap()

        // A sheet with its own button has Cancel only, and one Done above the keyboard, not stacked on the button.
        app.buttons["nav.add"].tap()
        app.buttons["add.tray.account"].tap()
        let accountCancel = app.buttons["Cancel"].firstMatch
        XCTAssertTrue(accountCancel.waitForExistence(timeout: 10))
        XCTAssertFalse(app.buttons["checkmark"].exists, "no second confirm beside the sheet's own button")
        capture("sheet-controls-account-sheet")
        accountCancel.tap()
    }
}
