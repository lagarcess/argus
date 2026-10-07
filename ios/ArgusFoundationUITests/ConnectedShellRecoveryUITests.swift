import XCTest

extension FinancialLoopUITests {
    func testConnectedReceiptDraftSurvivesRelaunchWithoutPosting() throws {
        #if !DEBUG
        throw XCTSkip("Receipt capture remains a development-only local draft.")
        #else
        try signIn(fresh: true)
        let balance = homeValue()
        openConnectedSavedReceipts()
        tapVisible(app.buttons["saved-add-receipt"])
        tapVisible(app.buttons["receipt-sample"])
        XCTAssertTrue(app.staticTexts["receipt-local-draft-notice"].waitForExistence(timeout: 5))
        XCTAssertFalse(app.buttons["receipt-confirm"].exists)
        XCTAssertFalse(app.buttons["receipt-account"].exists)
        XCTAssertFalse(app.segmentedControls["receipt-split"].exists)
        XCTAssertFalse(app.buttons["Add current location"].exists)
        capture("connected-receipt-local-draft")
        app.buttons["receipt-later"].tap()
        openConnectedSavedReceipts()
        let card = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'receipt-card-' ")).firstMatch
        XCTAssertTrue(card.waitForExistence(timeout: 5))
        let id = card.identifier
        app.terminate(); app.launch()
        openConnectedSavedReceipts()
        tapVisible(app.buttons[id])
        XCTAssertTrue(app.staticTexts["receipt-local-draft-notice"].waitForExistence(timeout: 5))
        XCTAssertFalse(app.buttons["receipt-confirm"].exists)
        tapVisible(app.buttons["receipt-source"])
        XCTAssertTrue(app.navigationBars["Original receipt"].waitForExistence(timeout: 5))
        capture("connected-receipt-original-after-relaunch")
        app.buttons["Done"].tap()
        app.buttons["receipt-later"].tap()
        assertHome(balance)
        try signIn(fresh: true, user: "B")
        openConnectedSavedReceipts()
        XCTAssertTrue(app.buttons["saved-add-receipt"].waitForExistence(timeout: 5))
        XCTAssertFalse(app.buttons[id].exists)
        capture("connected-receipt-isolated-from-other-person")
        app.buttons["Done"].tap()
        try signIn(fresh: true)
        openConnectedSavedReceipts()
        tapVisible(app.buttons[id])
        let options = app.buttons["Receipt options"]
        XCTAssertTrue(options.waitForExistence(timeout: 5))
        options.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5)).tap()
        let discard = app.buttons["Discard receipt"]
        XCTAssertTrue(discard.waitForExistence(timeout: 5))
        discard.tap()
        XCTAssertTrue(app.staticTexts["Discard this receipt?"].waitForExistence(timeout: 5))
        app.buttons["Discard receipt"].tap()
        XCTAssertTrue(app.buttons["receipt-later"].waitForNonExistence(timeout: 5))
        assertHome(balance)
        #endif
    }

    func openConnectedSavedReceipts() {
        XCTAssertTrue(app.buttons["tab.argus"].waitForExistence(timeout: 5))
        app.buttons["tab.argus"].tap()
        app.buttons["chat-attach"].tap()
        XCTAssertTrue(app.buttons["chat-saved-receipts"].waitForExistence(timeout: 5))
        app.buttons["chat-saved-receipts"].tap()
        XCTAssertTrue(app.buttons["saved-add-receipt"].waitForExistence(timeout: 5))
    }

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
        app.openPlanSurface()
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
