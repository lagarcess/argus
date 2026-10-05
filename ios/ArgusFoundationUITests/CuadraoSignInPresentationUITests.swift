import XCTest

/// Apple and Google flags default off (#795): no social sign-in is offered, in Connected or in the design preview.
final class CuadraoSignInPresentationUITests: XCTestCase {
    override func setUp() {
        continueAfterFailure = false
    }

    /// Auth is on. Provider expectations describe the flags and public ids of the tested build.
    /// The test runner must opt in because the default build has auth off.
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
            assertConnectedProviders(app)
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

    private func assertConnectedProviders(_ app: XCUIApplication, file: StaticString = #filePath, line: UInt = #line) {
        let environment = ProcessInfo.processInfo.environment
        for (id, key) in [("cuadrao.auth.apple", "ARGUS_TEST_EXPECT_APPLE"),
                          ("cuadrao.auth.google", "ARGUS_TEST_EXPECT_GOOGLE")] {
            let expected = environment[key] == "true"
            XCTAssertEqual(app.buttons[id].exists, expected, "Unexpected availability for \(id)", file: file, line: line)
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
