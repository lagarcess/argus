import XCTest

final class CuadraoContextUITests: XCTestCase {
    func testGroupContextPreservesDraftAttachmentsAndReturn() {
        let app = launch()
        tap(app, "cuadrao-tab-2")
        tap(app, "chat-composer-entry")
        let composer = app.descendants(matching: .any)["chat-composer"].firstMatch
        composer.typeText("Keep my unfinished question")
        tap(app, "chat-dismiss-keyboard")
        tap(app, "chat-attach")
        tap(app, "File")
        tap(app, "Attach example")
        tap(app, "cuadrao-tab-1")
        app.segmentedControls["plan-audience"].buttons["Together"].tap()
        tap(app, "group-card-trip")
        app.segmentedControls["group-sections"].buttons["People"].tap()
        tap(app, "group-options")
        tap(app, "group-open-chat")
        XCTAssertTrue(app.buttons["chat-context-close"].waitForExistence(timeout: 5))
        XCTAssertEqual(composer.value as? String, "Keep my unfinished question")
        XCTAssertTrue(app.buttons["chat-focus-remove"].exists)
        XCTAssertTrue(app.buttons["chat-send"].exists)
        XCTAssertTrue(app.staticTexts["Example document.pdf"].exists)
        XCTAssertFalse(app.staticTexts["EXAMPLE RESPONSE"].exists)
        shot(app, "context-group-draft-en")
        tap(app, "chat-context-close")
        XCTAssertTrue(app.segmentedControls["group-sections"].buttons["People"].isSelected)
        tap(app, "group-options")
        tap(app, "group-open-chat")
        tap(app, "chat-focus-remove")
        XCTAssertEqual(composer.value as? String, "Keep my unfinished question")
        tap(app, "chat-context-close")
        tap(app, "cuadrao-tab-2")
        XCTAssertEqual(composer.value as? String, "Keep my unfinished question")
        XCTAssertFalse(app.buttons["chat-focus-remove"].exists)
        XCTAssertTrue(app.staticTexts["Example document.pdf"].exists)
        tap(app, "chat-send")
        XCTAssertTrue(app.staticTexts["EXAMPLE RESPONSE"].waitForExistence(timeout: 5))
        shot(app, "context-main-chat-continuity-en")
    }

    func testChartContextKeepsPeriodAndDistributionSelection() {
        let app = launch()
        tap(app, "home-history-expand")
        tap(app, "home-view-distribution")
        tap(app, "home-distribution-checking")
        let ask = app.buttons["insight-open-chat"].firstMatch
        reveal(app, ask); ask.tap()
        XCTAssertTrue(app.buttons["chat-context-close"].waitForExistence(timeout: 5))
        let focus = app.descendants(matching: .any)["chat-focus-chip"].firstMatch
        XCTAssertTrue(focus.exists)
        XCTAssertTrue(focus.staticTexts.containing(NSPredicate(format: "label CONTAINS %@", "Distribution")).firstMatch.exists)
        XCTAssertTrue(focus.staticTexts.containing(NSPredicate(format: "label CONTAINS %@", "DOP")).firstMatch.exists)
        shot(app, "context-chart-selection-en")
        tap(app, "chat-context-close")
        let checking = app.buttons["home-distribution-checking"]
        for _ in 0..<10 where !checking.isHittable { app.swipeDown() }
        XCTAssertEqual(checking.value as? String, "Expanded")
        tap(app, "home-history-done")
        XCTAssertTrue(app.buttons["home-history-expand"].waitForExistence(timeout: 5))
    }

    func testReceiptContextReturnsToSameReview() {
        let app = launch()
        tap(app, "cuadrao-tab-1")
        app.segmentedControls["plan-audience"].buttons["Together"].tap()
        tap(app, "group-card-trip")
        app.segmentedControls["group-sections"].buttons["Expenses"].tap()
        tap(app, "group-add-receipt")
        tap(app, "receipt-sample")
        XCTAssertTrue(app.buttons["receipt-source"].waitForExistence(timeout: 5))
        let total = app.staticTexts["receipt-total"].label
        tap(app, "Receipt options")
        tap(app, "receipt-open-chat")
        XCTAssertTrue(app.buttons["chat-context-close"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.buttons["chat-focus-remove"].exists)
        shot(app, "context-receipt-en")
        tap(app, "chat-context-close")
        XCTAssertTrue(app.buttons["receipt-source"].waitForExistence(timeout: 5))
        XCTAssertEqual(app.staticTexts["receipt-total"].label, total)
        XCTAssertTrue(app.buttons["receipt-later"].exists)
    }

    func testContextVoiceReturnsToConversation() {
        let app = launch()
        tap(app, "cuadrao-tab-1")
        app.segmentedControls["plan-audience"].buttons["Together"].tap()
        tap(app, "group-card-trip")
        tap(app, "group-options")
        tap(app, "group-open-chat")
        tap(app, "chat-voice-entry")
        XCTAssertTrue(app.buttons["voice-end"].waitForExistence(timeout: 5))
        tap(app, "voice-end")
        XCTAssertTrue(app.buttons["chat-context-close"].waitForExistence(timeout: 5))
        tap(app, "chat-context-close")
        XCTAssertTrue(app.segmentedControls["group-sections"].exists)
    }

    private func launch() -> XCUIApplication {
        continueAfterFailure = false
        let app = XCUIApplication()
        app.launchArguments = ["--cuadrao-design", "--home-populated", "--plan-reset", "--receipt-reset", "--design-english", "-cuadrao.design.appearance", "light"]
        app.launch()
        return app
    }
    private func tap(_ app: XCUIApplication, _ id: String) {
        let button = app.buttons[id].firstMatch
        XCTAssertTrue(button.waitForExistence(timeout: 5), id)
        reveal(app, button)
        button.tap()
    }
    private func reveal(_ app: XCUIApplication, _ element: XCUIElement) {
        for _ in 0..<12 where !element.isHittable { app.swipeUp() }
    }
    private func shot(_ app: XCUIApplication, _ name: String) {
        let attachment = XCTAttachment(screenshot: app.screenshot())
        attachment.name = name; attachment.lifetime = .keepAlways; add(attachment)
    }
}
