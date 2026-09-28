import XCTest

/// T3 and T4: the interactive test sitekey renders a challenge in the web view,
/// and cancelling it closes the check without sending a request. The challenge
/// itself is never completed. run-app-demos.sh screenshots both states.
final class CancelSecurityCheckUITests: XCTestCase {
    func testCancellingTheSecurityCheckSendsNoRequest() {
        let app = XCUIApplication()
        app.launchArguments = ["-autorun", "turnstile", "-sitekey", "3x00000000000000000000FF"]
        app.launchEnvironment = ProcessInfo.processInfo.environment.filter { $0.key.hasPrefix("NATIVE_AUTH_") }
        app.launch()

        let challenge = app.descendants(matching: .any)["log-turnstile.interactive"]
        XCTAssertTrue(challenge.waitForExistence(timeout: 45), "Turnstile reported an interactive challenge")
        // Holds the challenge on screen while the run script takes its screenshot.
        sleep(8)
        app.buttons["Cancel"].tap()

        let cancelled = app.descendants(matching: .any)["log-turnstile.cancelled"]
        XCTAssertTrue(cancelled.waitForExistence(timeout: 10), "cancellation logged")
        XCTAssertFalse(app.descendants(matching: .any)["log-guest.start"].exists, "no request sent")
        XCTAssertFalse(app.descendants(matching: .any)["log-turnstile.token"].exists, "challenge not completed")
        // Holds the cancelled state on screen for the second screenshot.
        sleep(6)
    }
}
