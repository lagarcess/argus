import XCTest

final class CuadraoReceiptPermissionUITests: XCTestCase {
    func testDeniedLocationKeepsReceiptUsable() {
        let app = openReceipt()
        requestLocation(app, choice: "Don’t Allow", fallback: "Don't Allow")
        let unavailable = app.staticTexts["Your location is unavailable. You can continue without it."]
        XCTAssertTrue(unavailable.waitForExistence(timeout: 8))
        capture(app, "receipt-location-denied-en")
        app.buttons["receipt-later"].tap()
        let card = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH %@", "receipt-card-")).firstMatch
        XCTAssertTrue(card.waitForExistence(timeout: 5)); card.tap()
        reveal(app, app.buttons["receipt-confirm"])
        XCTAssertTrue(app.buttons["receipt-confirm"].isEnabled)
    }

    func testAllowedLocationCanBeRemoved() {
        let app = openReceipt()
        requestLocation(app, choice: "Allow While Using App", fallback: "Allow While Using App")
        let remove = app.buttons["Remove location"]
        XCTAssertTrue(remove.waitForExistence(timeout: 15))
        reveal(app, remove)
        capture(app, "receipt-location-added-en")
        remove.tap()
        XCTAssertTrue(app.buttons["Add current location"].waitForExistence(timeout: 5))
        app.buttons["receipt-later"].tap()
        let card = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH %@", "receipt-card-")).firstMatch
        XCTAssertTrue(card.waitForExistence(timeout: 5)); card.tap()
        reveal(app, app.buttons["Add current location"])
        XCTAssertTrue(app.buttons["Add current location"].exists)
        XCTAssertFalse(remove.exists)
    }

    private func openReceipt() -> XCUIApplication {
        continueAfterFailure = false
        let app = XCUIApplication()
        app.resetAuthorizationStatus(for: .location)
        app.launchArguments = ["--cuadrao-design", "--home-populated", "--design-english", "--plan-reset", "--receipt-reset"]
        app.launch()
        app.buttons["cuadrao-tab-1"].tap()
        app.segmentedControls["plan-audience"].buttons["Together"].tap()
        app.buttons["group-card-trip"].tap()
        app.segmentedControls["group-sections"].buttons["Expenses"].tap()
        app.buttons["group-add-receipt"].tap()
        app.buttons["receipt-sample"].tap()
        XCTAssertTrue(app.staticTexts["receipt-status"].waitForExistence(timeout: 5))
        return app
    }
    private func requestLocation(_ app: XCUIApplication, choice: String, fallback: String) {
        let add = app.buttons["Add current location"]
        reveal(app, add); add.tap()
        let system = XCUIApplication(bundleIdentifier: "com.apple.springboard")
        let button = system.buttons[choice]
        if button.waitForExistence(timeout: 5) { button.tap() }
        else { system.buttons[fallback].tap() }
    }
    private func reveal(_ app: XCUIApplication, _ element: XCUIElement) {
        for _ in 0..<12 where !element.isHittable { app.swipeUp() }
    }
    private func capture(_ app: XCUIApplication, _ name: String) {
        let image = XCTAttachment(screenshot: app.screenshot())
        image.name = name; image.lifetime = .keepAlways; add(image)
    }
}
