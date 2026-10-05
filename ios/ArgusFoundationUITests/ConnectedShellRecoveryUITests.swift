import XCTest

extension FinancialLoopUITests {
    func testConnectedChatDraftAndUpdatesReturnKeepMoneyUnchanged() throws {
        try signIn()
        let balance = homeValue()
        app.buttons["tab.argus"].tap()
        XCTAssertTrue(app.staticTexts["chat.preview.notice"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.buttons["chat-history"].exists)
        if app.buttons["chat-composer-entry"].exists { app.buttons["chat-composer-entry"].tap() }
        let composer = app.descendants(matching: .any)["chat-composer"].firstMatch
        XCTAssertTrue(composer.waitForExistence(timeout: 5))
        let draft = "Keep this question while I check my plan"
        composer.tap()
        composer.typeText(draft)
        XCTAssertFalse(app.buttons["tab.home"].exists)
        app.buttons["chat-dismiss-keyboard"].tap()
        XCTAssertTrue(app.buttons["tab.home"].waitForExistence(timeout: 5))
        app.buttons["chat-attach"].tap()
        app.buttons["File"].tap()
        XCTAssertTrue(app.buttons["Attach example"].waitForExistence(timeout: 5))
        app.buttons["Attach example"].tap()
        app.buttons["tab.plan"].tap()
        XCTAssertTrue(app.staticTexts["plan-heading"].waitForExistence(timeout: 5))
        app.buttons["tab.argus"].tap()
        XCTAssertEqual(composer.value as? String, draft)
        XCTAssertTrue(app.staticTexts["Example document.pdf"].exists)
        capture("connected-chat-approved-composer-preserves-draft")

        app.buttons["tab.home"].tap()
        tapVisible(app.buttons["cuadrao.updates.open"])
        XCTAssertTrue(app.descendants(matching: .any)["cuadrao.updates.empty"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.staticTexts["Updates aren't connected in this version yet. Your transactions and plans are still available."].exists)
        app.buttons["cuadrao.updates.preferences"].tap()
        XCTAssertTrue(app.navigationBars["Notifications"].waitForExistence(timeout: 5))
        XCTAssertFalse(app.buttons["tab.home"].exists)
        app.navigationBars.buttons.firstMatch.tap()
        XCTAssertTrue(app.buttons["tab.home"].waitForExistence(timeout: 5))
        assertHome(balance)
        capture("connected-updates-return-to-profile")
    }
}
