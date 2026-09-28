import XCTest

/// Accepts iOS's "Open in ArgusAuthProbeApp?" prompt for custom-scheme
/// callbacks, as a user would, so T5 needs no person. iOS asks on the first
/// delivery to a new install; later deliveries may not ask at all.
final class CustomSchemePromptUITests: XCTestCase {
    func testAcceptEveryCustomSchemePrompt() {
        let springboard = XCUIApplication(bundleIdentifier: "com.apple.springboard")
        let open = springboard.buttons["Open"]
        var accepted = 0
        var waitForFirst = true
        // Keeps watching while callbacks are delivered; stops after a quiet spell.
        while open.waitForExistence(timeout: waitForFirst ? 120 : 20) {
            // Leaves the prompt up long enough for the run script's screenshot.
            sleep(3)
            open.tap()
            accepted += 1
            waitForFirst = false
        }
        print("SCHEME_PROMPTS_ACCEPTED \(accepted)")
    }
}
