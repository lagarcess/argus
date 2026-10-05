import XCTest

final class AppleSessionJourneyUITests: XCTestCase {
    override func setUp() { continueAfterFailure = false }

    func testCaptureFailureRecoveryAndRevocationInEnglishAndSpanish() {
        for language in ["en", "es-419"] {
            let app = launch(language)
            reset(app)
            app.buttons["harness.apple"].tap()
            XCTAssertTrue(app.alerts.firstMatch.waitForExistence(timeout: 8))
            capture(app, "apple-capture-failed-" + language)
            app.alerts.buttons.firstMatch.tap()
            XCTAssertTrue(app.staticTexts["auth.apple.capture.notice"].waitForExistence(timeout: 5))
            app.buttons["harness.error"].tap()
            app.buttons["harness.check"].tap()
            XCTAssertTrue(app.buttons["auth.validation.retry"].waitForExistence(timeout: 5))
            waitEnabled(app.buttons["auth.validation.retry"])
            XCTAssertTrue(app.buttons["auth.signOut"].exists)
            capture(app, "apple-validation-retry-" + language)
            app.buttons["harness.authorized"].tap()
            app.buttons["auth.validation.retry"].tap()
            if app.alerts.firstMatch.waitForExistence(timeout: 2) { app.alerts.buttons.firstMatch.tap() }
            XCTAssertTrue(app.staticTexts["auth.identity"].waitForExistence(timeout: 5))
            app.buttons["harness.check"].tap()
            waitEnabled(app.buttons["harness.check"])
            XCTAssertFalse(app.alerts.firstMatch.exists)
            app.buttons["harness.revoked"].tap()
            app.buttons["harness.notify"].tap()
            XCTAssertTrue(app.textFields["auth.email"].waitForExistence(timeout: 8))
            capture(app, "apple-revoked-signed-out-" + language)
            app.terminate()
        }
    }

    func testKnownEmailIgnoresLinkedAppleAndMissingAppleSubjectRequiresNewSignIn() {
        let app = launch("en")
        reset(app)
        app.buttons["harness.revoked"].tap()
        app.buttons["harness.email"].tap()
        XCTAssertTrue(app.staticTexts["auth.identity"].waitForExistence(timeout: 8))
        app.buttons["harness.check"].tap()
        waitEnabled(app.buttons["harness.check"])
        XCTAssertTrue(app.staticTexts["auth.identity"].exists)
        capture(app, "email-with-apple-link")
        app.buttons["auth.signOut"].tap()
        XCTAssertTrue(app.textFields["auth.email"].waitForExistence(timeout: 8))
        app.buttons["harness.authorized"].tap()
        app.buttons["harness.apple"].tap()
        XCTAssertTrue(app.alerts.firstMatch.waitForExistence(timeout: 8))
        app.alerts.buttons.firstMatch.tap()
        app.buttons["harness.unlink"].tap()
        app.buttons["harness.check"].tap()
        XCTAssertTrue(app.buttons["auth.validation.retry"].waitForExistence(timeout: 5))
        waitEnabled(app.buttons["auth.validation.retry"])
        XCTAssertEqual(app.buttons["auth.validation.retry"].label, "Sign out and sign in again")
        capture(app, "apple-explicit-sign-in-again")
        app.buttons["auth.validation.retry"].tap()
        XCTAssertTrue(app.textFields["auth.email"].waitForExistence(timeout: 8))
        app.buttons["harness.link"].tap()
        app.terminate()
    }

    func testNotificationDuringBusyValidationIsCoalescedByTheActualModel() {
        let app = launch("en")
        reset(app)
        app.buttons["harness.apple"].tap()
        XCTAssertTrue(app.alerts.firstMatch.waitForExistence(timeout: 8))
        app.alerts.buttons.firstMatch.tap()
        let before = app.staticTexts["harness.checks"].label
        let count = Int(before.split(separator: " ").last!)!
        app.buttons["harness.hold-check"].tap()
        expectation(for: NSPredicate(format: "enabled == false"), evaluatedWith: app.buttons["harness.check"])
        waitForExpectations(timeout: 5)
        app.buttons["harness.revoke-notify"].tap()
        XCTAssertFalse(app.buttons["harness.check"].isEnabled)
        app.buttons["harness.release"].tap()
        XCTAssertTrue(app.textFields["auth.email"].waitForExistence(timeout: 8))
        XCTAssertEqual(app.staticTexts["harness.checks"].label, "Checks: \(count + 2)")
        capture(app, "apple-notification-during-validation")
        app.terminate()
    }

    func testUnavailableAppleCanBeSignedOutManually() {
        let app = launch("en")
        reset(app)
        app.buttons["harness.apple"].tap()
        XCTAssertTrue(app.alerts.firstMatch.waitForExistence(timeout: 8))
        app.alerts.buttons.firstMatch.tap()
        app.buttons["harness.transferred"].tap()
        app.buttons["harness.check"].tap()
        XCTAssertTrue(app.buttons["auth.validation.retry"].waitForExistence(timeout: 5))
        waitEnabled(app.buttons["auth.signOut"])
        app.buttons["auth.signOut"].tap()
        XCTAssertTrue(app.textFields["auth.email"].waitForExistence(timeout: 8))
        app.terminate()
    }

    private func launch(_ language: String) -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments = ["--apple-session-harness", "--reset-apple-session-harness", "-AppleLanguages", "(\(language))", "-AppleLocale", language == "en" ? "en_US" : "es_DO"]
        app.launch()
        XCTAssertTrue(app.buttons["harness.check"].waitForExistence(timeout: 8))
        return app
    }
    private func reset(_ app: XCUIApplication) {
        if app.alerts.firstMatch.exists { app.alerts.buttons.firstMatch.tap() }
        if app.buttons["auth.signOut"].exists { waitEnabled(app.buttons["auth.signOut"]); app.buttons["auth.signOut"].tap() }
        XCTAssertTrue(app.textFields["auth.email"].waitForExistence(timeout: 8))
        app.buttons["harness.link"].tap()
        app.buttons["harness.authorized"].tap()
    }
    private func waitEnabled(_ element: XCUIElement) {
        expectation(for: NSPredicate(format: "enabled == true"), evaluatedWith: element)
        waitForExpectations(timeout: 8)
    }
    private func capture(_ app: XCUIApplication, _ name: String) {
        let attachment = XCTAttachment(screenshot: app.screenshot())
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
    }
}
