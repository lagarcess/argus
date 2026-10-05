import XCTest

final class NativeProviderAppearanceUITests: XCTestCase {
    override func setUp() {
        continueAfterFailure = false
    }

    func testConnectedProviderAppearance() throws {
        guard ProcessInfo.processInfo.environment["ARGUS_TEST_NATIVE_PROVIDER_APPEARANCE"] == "true" else {
            throw XCTSkip("Requires the isolated synthetic Debug build with both native providers enabled.")
        }
        for language in ["en", "es-419"] {
            for appearance in ["light", "dark"] {
                for largeText in [false, true] {
                    for createAccount in [true, false] {
                        let name = "\(createAccount ? "signup" : "signin")-\(language)-\(appearance)-\(largeText ? "accessibility" : "standard")"
                        let app = XCUIApplication()
                        app.launchArguments = ["-AppleLanguages", "(\(language))", "-AppleLocale", language == "en" ? "en_US" : "es_DO",
                                               "-appearancePreference", appearance,
                                               "-UIPreferredContentSizeCategoryName", largeText ? "UICTContentSizeCategoryAccessibilityXXXL" : "UICTContentSizeCategoryL"]
                        app.launch()
                        let entry = app.buttons[createAccount ? "cuadrao.welcome.signup" : "cuadrao.welcome.signin"]
                        XCTAssertTrue(entry.waitForExistence(timeout: 10), name)
                        entry.tap()
                        let apple = app.buttons["cuadrao.auth.apple"]
                        let google = app.buttons["cuadrao.auth.google"]
                        let email = app.buttons[createAccount ? "cuadrao.signup.email" : "cuadrao.signin.emailChoice"]
                        XCTAssertTrue(apple.waitForExistence(timeout: 10), name)
                        XCTAssertTrue(google.exists, name)
                        XCTAssertTrue(email.exists, name)
                        XCTAssertTrue(apple.isEnabled && google.isEnabled, name)
                        XCTAssertTrue(apple.isHittable && google.isHittable && email.isHittable, name)
                        XCTAssertLessThan(apple.frame.maxY, google.frame.minY, name)
                        XCTAssertLessThan(google.frame.maxY, email.frame.minY, name)
                        XCTAssertTrue(apple.label.contains("Apple"), name)
                        XCTAssertTrue(google.label.contains("Google"), name)
                        let screenshot = XCTAttachment(screenshot: app.screenshot())
                        screenshot.name = name
                        screenshot.lifetime = .keepAlways
                        add(screenshot)
                        app.terminate()
                    }
                }
            }
        }
    }
}
