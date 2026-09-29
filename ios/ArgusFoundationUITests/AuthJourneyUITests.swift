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
        XCTAssertTrue(app.textFields["auth.email"].waitForExistence(timeout: 10))
        capture("auth-entry")
        app.textFields["auth.email"].tap()
        app.textFields["auth.email"].typeText(email)
        pastePassword(password)
        let submit = app.buttons["auth.submit"]
        if !submit.isHittable { app.swipeUp() }
        submit.tap()
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
        XCTAssertTrue(app.textFields["auth.email"].waitForExistence(timeout: 20))
        XCTAssertFalse(app.buttons["auth.signOut"].exists)
        capture("auth-signed-out")
        app.terminate()
        app.launch()
        openProfile()
        XCTAssertTrue(app.textFields["auth.email"].waitForExistence(timeout: 10))
        XCTAssertFalse(app.buttons["auth.signOut"].exists)
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
        openProfile()
        app.buttons["auth.createAccount"].tap()
        XCTAssertTrue(app.textFields["auth.name"].waitForExistence(timeout: 5))
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
        XCTAssertTrue(app.buttons["header.profile"].waitForExistence(timeout: 10))
        app.buttons["header.profile"].tap()
    }

    private func pastePassword(_ value: String) {
        UIPasteboard.general.setItems([[UTType.utf8PlainText.identifier: value]],
                                     options: [.localOnly: true, .expirationDate: Date().addingTimeInterval(60)])
        let field = app.secureTextFields["auth.password"]
        field.tap()
        field.press(forDuration: 1.1)
        let paste = app.menuItems["Paste"].firstMatch
        if paste.waitForExistence(timeout: 3) { paste.tap() }
        else { app.buttons["Paste"].firstMatch.tap() }
        let permission = app.alerts.buttons["Allow Paste"]
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
