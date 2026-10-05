import XCTest
import UIKit
import UniformTypeIdentifiers

/// Opt-in, isolated-service acceptance. Passwords enter via a local-only
/// pasteboard so XCTest never records a typeText(password) activity.
final class AuthJourneyUITests: XCTestCase {
    private var app: XCUIApplication!

    override func tearDown() {
        UIPasteboard.general.items = []
        app?.terminate()
        super.tearDown()
    }

    func testPrimaryCurrencySurvivesRelaunch() throws {
        let environment = ProcessInfo.processInfo.environment
        guard let email = environment["ARGUS_TEST_EMAIL"], let password = environment["ARGUS_TEST_PASSWORD"] else {
            throw XCTSkip("Requires lane-owned synthetic credentials.")
        }
        continueAfterFailure = false
        let spanish = environment["ARGUS_TEST_LANGUAGE"] == "es-419"
        app = XCUIApplication()
        app.launchArguments = ["-AppleLanguages", spanish ? "(es)" : "(en)", "-AppleLocale", spanish ? "es_DO" : "en_US"]
        app.launch()
        app.openSignedOutAuthEntry()
        app.textFields["auth.email"].tap(); app.textFields["auth.email"].typeText(email)
        pastePassword(password)
        let submit = app.buttons["auth.submit"]
        if !submit.isHittable { app.swipeUp() }
        submit.tap()
        XCTAssertTrue(app.buttons["header.profile"].waitForExistence(timeout: 30))
        app.openProfileSurface()
        let choice = app.buttons["profile.primaryCurrency"]
        XCTAssertTrue(choice.waitForExistence(timeout: 10))
        choice.tap(); app.buttons["USD"].tap()
        let saved = NSPredicate(format: "label CONTAINS %@", "USD")
        expectation(for: saved, evaluatedWith: choice)
        waitForExpectations(timeout: 15)
        capture(spanish ? "primary-currency-es-saved" : "primary-currency-en-saved")
        app.terminate(); app.launch()
        XCTAssertTrue(app.buttons["header.profile"].waitForExistence(timeout: 30))
        app.openProfileSurface()
        XCTAssertTrue(choice.waitForExistence(timeout: 10))
        XCTAssertTrue(choice.label.contains("USD"))
        capture(spanish ? "primary-currency-es-restored" : "primary-currency-en-restored")
        app.buttons["auth.signOut"].tap()
    }

    func testRegisteredSessionSurvivesRelaunchAndSignsOut() throws {
        let environment = ProcessInfo.processInfo.environment
        guard let email = environment["ARGUS_TEST_EMAIL"], let password = environment["ARGUS_TEST_PASSWORD"] else {
            throw XCTSkip("Requires lane-owned synthetic credentials supplied to the test runner.")
        }
        continueAfterFailure = false
        app = XCUIApplication()
        app.launchArguments = ["-AppleLanguages", "(en)", "-AppleLocale", "en_US"]
        app.launch()
        openProfile()
        if app.buttons["auth.signOut"].exists {
            app.buttons["auth.signOut"].tap()
        }
        openEmailAuthAfterSignOut()
        capture("auth-entry")
        app.textFields["auth.email"].tap()
        app.textFields["auth.email"].typeText(email)
        pastePassword(password)
        let submit = app.buttons["auth.submit"]
        if !submit.isHittable { app.swipeUp() }
        submit.tap()
        // Connected lands on Home; tip left the profile sheet open after login.
        if !app.buttons["auth.signOut"].waitForExistence(timeout: 5) {
            XCTAssertTrue(app.buttons["header.profile"].waitForExistence(timeout: 30)
                || app.buttons["tab.home"].waitForExistence(timeout: 30))
            app.openProfileSurface()
        }
        XCTAssertTrue(app.buttons["auth.signOut"].waitForExistence(timeout: 30))
        XCTAssertTrue(app.descendants(matching: .any)["auth.identity"].exists)
        capture("auth-verified")

        app.terminate()
        app.launch()
        openProfile()
        XCTAssertTrue(app.buttons["auth.signOut"].waitForExistence(timeout: 15))
        XCTAssertFalse(app.textFields["auth.email"].exists)
        capture("auth-restored")
        app.buttons["auth.signOut"].tap()
        openEmailAuthAfterSignOut()
        XCTAssertFalse(app.buttons["auth.signOut"].exists)
        capture("auth-signed-out")
        app.terminate()
        app.launch()
        openProfile()
        XCTAssertTrue(app.textFields["auth.email"].waitForExistence(timeout: 10)
            || app.buttons["cuadrao.welcome.signin"].waitForExistence(timeout: 10))
        if !app.textFields["auth.email"].exists {
            app.openSignedOutAuthEntry()
        }
        XCTAssertTrue(app.textFields["auth.email"].waitForExistence(timeout: 10))
        XCTAssertFalse(app.buttons["auth.signOut"].exists)
    }

    /// Connected sign-out returns to welcome; tip returns to the profile email sheet.
    private func openEmailAuthAfterSignOut() {
        if app.textFields["auth.email"].waitForExistence(timeout: 3) { return }
        XCTAssertTrue(
            app.buttons["cuadrao.welcome.signin"].waitForExistence(timeout: 20)
                || app.buttons["cuadrao.welcome.signup"].exists
                || app.buttons["header.profile"].exists,
            "Signed-out Connected must show welcome; tip must show profile entry."
        )
        app.openSignedOutAuthEntry()
        XCTAssertTrue(app.textFields["auth.email"].waitForExistence(timeout: 10))
    }

    func testCaptchaCancellationKeepsEntry() throws {
        try prepareChallenge()
        XCTAssertTrue(app.buttons["auth.captcha.cancel"].waitForExistence(timeout: 10))
        capture("auth-captcha-cancel")
        app.buttons["auth.captcha.cancel"].tap()
        XCTAssertTrue(app.textFields["auth.email"].waitForExistence(timeout: 5))
        XCTAssertFalse(app.buttons["auth.signOut"].exists)
    }

    func testCaptchaFailureShowsRetryableEntry() throws {
        try prepareChallenge()
        XCTAssertTrue(app.staticTexts["auth.error"].waitForExistence(timeout: 30))
        XCTAssertTrue(app.textFields["auth.email"].exists)
        XCTAssertFalse(app.buttons["auth.signOut"].exists)
        capture("auth-captcha-failed")
    }

    func testSignupRequiresEmailConfirmation() throws {
        guard ProcessInfo.processInfo.environment["ARGUS_TEST_AUTH_UI_ENABLED"] == "true" else {
            throw XCTSkip("Requires isolated local signup service.")
        }
        app = XCUIApplication()
        app.launchArguments = ["-AppleLanguages", "(en)", "-AppleLocale", "en_US"]
        app.launch()
        app.openSignedOutAuthEntry(createAccount: true)
        if app.textFields["auth.name"].waitForExistence(timeout: 2) {
            // Tip ProfileAccountSection signup still collects an optional name.
        }
        app.textFields["auth.email"].tap()
        app.textFields["auth.email"].typeText("native-signup-\(UUID().uuidString.lowercased())@example.test")
        pastePassword(UUID().uuidString)
        let submit = app.buttons["auth.submit"]
        if !submit.isHittable { app.swipeUp() }
        submit.tap()
        XCTAssertTrue(app.staticTexts["auth.confirmation"].waitForExistence(timeout: 30))
        XCTAssertFalse(app.buttons["auth.signOut"].exists)
        capture("auth-confirmation-required")
        app.buttons["auth.return.signIn"].tap()
        XCTAssertTrue(app.textFields["auth.email"].waitForExistence(timeout: 5))
    }

    private func prepareChallenge() throws {
        guard ProcessInfo.processInfo.environment["ARGUS_TEST_AUTH_UI_ENABLED"] == "true" else {
            throw XCTSkip("Requires isolated local test bridge configuration.")
        }
        app = XCUIApplication()
        app.launchArguments = ["-AppleLanguages", "(en)", "-AppleLocale", "en_US"]
        app.launch()
        openProfile()
        XCTAssertTrue(app.textFields["auth.email"].waitForExistence(timeout: 10))
        app.textFields["auth.email"].tap()
        app.textFields["auth.email"].typeText("captcha-ui@example.test")
        pastePassword("NotAnAccountPassword123!")
        let submit = app.buttons["auth.submit"]
        if !submit.isHittable { app.swipeUp() }
        submit.tap()
    }

    private func openProfile() {
        app.openProfileSurface()
    }

    private func pastePassword(_ value: String) {
        UIPasteboard.general.setItems([[UTType.utf8PlainText.identifier: value]],
                                     options: [.localOnly: true, .expirationDate: Date().addingTimeInterval(60)])
        let field = app.secureTextFields["auth.password"]
        field.tap()
        field.press(forDuration: 1.1)
        let paste = app.menuItems.matching(NSPredicate(format: "label IN %@", ["Paste", "Pegar"])).firstMatch
        if paste.waitForExistence(timeout: 3) { paste.tap() }
        else { app.buttons.matching(NSPredicate(format: "label IN %@", ["Paste", "Pegar"])).firstMatch.tap() }
        let permission = app.alerts.buttons.matching(NSPredicate(format: "label IN %@", ["Allow Paste", "Permitir pegar"])).firstMatch
        if permission.waitForExistence(timeout: 1) { permission.tap() }
        UIPasteboard.general.items = []
    }

    private func capture(_ name: String) {
        let attachment = XCTAttachment(screenshot: app.screenshot())
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
    }
}
