import XCTest

final class CuadraoHomeChartUITests: XCTestCase {
    func testHomeBalanceChartAndSpaces() {
        continueAfterFailure = false
        let app = XCUIApplication()
        app.launchArguments = ["--plan-reset", "-cuadrao.design.appearance", "light"]
        app.launch()
        XCTAssertEqual(app.staticTexts["home-chart-amount"].label, "153,920.00")
        shot(app,"home-chart-personal-es")
        let chart = app.otherElements.matching(identifier: "home-balance-chart").firstMatch
        XCTAssertTrue(chart.waitForExistence(timeout: 3))
        chart.coordinate(withNormalizedOffset: CGVector(dx: 0.2, dy: 0.5)).tap()
        XCTAssertNotEqual(app.staticTexts["home-chart-date"].label, "Balance registrado")
        shot(app,"home-chart-inspect-es")
        let earlier = app.staticTexts["home-chart-date"].label
        chart.coordinate(withNormalizedOffset: CGVector(dx: 0.2, dy: 0.5)).press(forDuration: 0.35, thenDragTo: chart.coordinate(withNormalizedOffset: CGVector(dx: 0.65, dy: 0.5)))
        XCTAssertNotEqual(app.staticTexts["home-chart-date"].label, earlier)
        shot(app,"home-chart-scrub-es")
        app.buttons["home-chart-today"].tap()
        XCTAssertEqual(app.staticTexts["home-chart-amount"].label, "153,920.00")
        app.buttons["cuadrao-space-household"].tap()
        XCTAssertEqual(app.staticTexts["home-chart-amount"].label, "43,500.00")
        shot(app,"home-chart-household-es")
        app.buttons["home-chart-plan"].tap()
        XCTAssertTrue(app.buttons["plan-explore"].waitForExistence(timeout: 3))
        app.buttons["cuadrao-tab-0"].tap()
        XCTAssertEqual(app.staticTexts["home-chart-amount"].label, "43,500.00")
    }
    func testDarkAndLargeEnglish() {
        continueAfterFailure = false
        let app = XCUIApplication()
        app.launchArguments = ["--design-english", "-cuadrao.design.appearance", "dark", "-UIPreferredContentSizeCategoryName", "UICTContentSizeCategoryAccessibilityM"]
        app.launch()
        XCTAssertTrue(app.staticTexts["home-chart-amount"].exists)
        shot(app,"home-chart-dark-large-en")
        let link = app.buttons["home-chart-plan"]
        for _ in 0..<4 {
            if link.isHittable && link.frame.maxY < app.buttons["cuadrao-tab-0"].frame.minY { break }
            app.coordinate(withNormalizedOffset: CGVector(dx: 0.95, dy: 0.75)).press(forDuration: 0.1, thenDragTo: app.coordinate(withNormalizedOffset: CGVector(dx: 0.95, dy: 0.5)))
        }
        shot(app,"home-chart-dark-large-scroll-en")
        XCTAssertTrue(app.buttons["home-chart-plan"].isHittable)
        app.buttons["home-chart-plan"].tap()
        XCTAssertTrue(app.buttons["plan-create"].waitForExistence(timeout: 3))
    }
    private func shot(_ app: XCUIApplication,_ name: String) {
        let a = XCTAttachment(screenshot: app.screenshot()); a.name = name; a.lifetime = .keepAlways; add(a)
    }
}
