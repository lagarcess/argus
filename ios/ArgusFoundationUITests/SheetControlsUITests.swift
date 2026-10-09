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
        XCTAssertTrue(cancel.waitForExistence(timeout: 10), "profile Cancel")
        XCTAssertEqual(cancel.label, "Cancel")
        let save = app.buttons["cuadrao.profile.save"]
        XCTAssertTrue(save.exists)
        XCTAssertEqual(save.label, "Save")
        XCTAssertLessThan(cancel.frame.midX, save.frame.midX, "Cancel is on the left, the check on the right")
        XCTAssertEqual(cancel.frame.midY, save.frame.midY, accuracy: 4, "both sit on the same bar")
        capture("sheet-controls-edit-profile")
        cancel.tap()

        // A sheet with its own button has Cancel only: nothing else sits in the navigation bar.
        app.buttons["nav.add"].tap()
        app.buttons["add.tray.account"].tap()
        let accountCancel = app.buttons["Cancel"].firstMatch
        XCTAssertTrue(accountCancel.waitForExistence(timeout: 10), "account sheet Cancel")
        let barButtons = app.navigationBars.firstMatch.buttons.allElementsBoundByIndex
        XCTAssertFalse(barButtons.contains { $0.frame.midX > app.frame.width / 2 }, "no second confirm beside the sheet's own button")
        capture("sheet-controls-account-sheet")
        accountCancel.tap()

        // Typing in a plan field shows the keyboard's own Done, and it closes the keyboard.
        app.buttons["nav.add"].tap()
        app.buttons["add.tray.plan"].tap()
        let name = app.textFields.matching(NSPredicate(format: "identifier IN {'goal.name', 'budget.name', 'debt.name', 'plan-name'}")).firstMatch
        XCTAssertTrue(name.waitForExistence(timeout: 10), "plan name field")
        name.tap()
        name.typeText("Trip")
        let keyboardDone = app.toolbars.buttons["Done"]
        XCTAssertTrue(keyboardDone.waitForExistence(timeout: 5), "the keyboard has its own Done")
        XCTAssertFalse(app.buttons["plan-rate-done"].exists, "no second Done above the Create plan button")
        capture("sheet-controls-plan-keyboard")
        keyboardDone.tap()
        XCTAssertTrue(app.keyboards.firstMatch.waitForNonExistence(timeout: 5), "Done closes the keyboard on the name field")
        app.buttons["Cancel"].firstMatch.tap()
    }
}
