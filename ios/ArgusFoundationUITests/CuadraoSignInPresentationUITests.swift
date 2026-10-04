import XCTest

/// Apple and Google flags default off (#795): no social sign-in is offered, in Connected or in the design preview.
final class CuadraoSignInPresentationUITests: XCTestCase {
    override func setUp() {
        continueAfterFailure = false
    }

    /// Auth on, social flags at their defaults: Connected's sign-up and sign-in entries offer email only.
    /// The default build has auth off and never shows these entries, so the run must opt in.
    func testDefaultLaunchOffersNoAppleSignIn() throws {
        guard ProcessInfo.processInfo.environment["ARGUS_TEST_AUTH_UI_ENABLED"] == "true" else {
            throw XCTSkip("Requires a build with ARGUS_AUTH_ENABLED=true (cuadrao-design-mac-pass.sh tests builds one).")
        }
        for createAccount in [true, false] {
            let app = XCUIApplication()
            app.launchArguments = ["-AppleLanguages", "(en)", "-AppleLocale", "en_US"]
            app.launch()
            assertNoSocialSignIn(app)
            let welcome = app.buttons[createAccount ? "cuadrao.welcome.signup" : "cuadrao.welcome.signin"]
            XCTAssertTrue(welcome.waitForExistence(timeout: 10))
            welcome.tap()
            let email = app.buttons[createAccount ? "cuadrao.signup.email" : "cuadrao.signin.emailChoice"]
            XCTAssertTrue(email.waitForExistence(timeout: 10))
            assertNoSocialSignIn(app)
            app.terminate()
        }
    }

    /// `--cuadrao-design` welcome: the preview's own Apple control stays behind
    /// `CuadraoFirstRelease.showsSocialSignIn`.
    func testDesignPreviewOffersNoAppleSignIn() {
        for (entry, email) in [("Crear cuenta", "cuadrao.signup.email"), ("Iniciar sesión", "cuadrao.signin.emailChoice")] {
            let app = XCUIApplication()
            app.launchArguments = ["--cuadrao-design"]
            app.launch()
            let button = app.buttons[entry]
            XCTAssertTrue(button.waitForExistence(timeout: 10))
            button.tap()
            XCTAssertTrue(app.buttons[email].waitForExistence(timeout: 10))
            assertNoSocialSignIn(app)
            app.terminate()
        }
    }

    private func assertNoSocialSignIn(_ app: XCUIApplication, file: StaticString = #filePath, line: UInt = #line) {
        for id in ["cuadrao.signup.apple", "cuadrao.signin.apple"] {
            XCTAssertFalse(app.buttons[id].exists, "\(id) is offered", file: file, line: line)
        }
        let social = NSPredicate(format: "label CONTAINS[c] 'Apple' OR label CONTAINS[c] 'Google'")
        XCTAssertEqual(app.buttons.matching(social).count, 0, "A social sign-in button is offered", file: file, line: line)
    }
}
