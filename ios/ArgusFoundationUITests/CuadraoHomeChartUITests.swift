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
        XCTAssertNotEqual(app.staticTexts["home-chart-date"].label, "Balance neto registrado")
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
        XCTAssertLessThanOrEqual(app.staticTexts["home-chart-amount"].frame.maxX, app.frame.maxX)
        shot(app,"home-chart-household-return-es")
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
    func testHistoryRangesAndDistribution() {
        continueAfterFailure = false
        let app = XCUIApplication()
        app.launchArguments = ["--plan-reset", "-cuadrao.design.appearance", "light"]
        app.launch()
        XCTAssertTrue(app.staticTexts["home-greeting"].label.hasPrefix("Hola"))
        app.buttons["home-range-all"].tap()
        shot(app, "home-history-all-es")
        app.segmentedControls["home-chart-view"].buttons["Distribución"].tap()
        XCTAssertEqual(app.staticTexts["home-chart-amount"].label, "153,920.00")
        XCTAssertTrue(app.otherElements.matching(identifier: "home-distribution-bar").firstMatch.exists)
        shot(app, "home-distribution-es")
        app.buttons["home-distribution-savings"].tap()
        XCTAssertTrue(app.staticTexts["Mi tranquilidad"].exists)
        shot(app, "home-distribution-accounts-es")
        app.segmentedControls["home-chart-view"].buttons["Evolución"].tap()
        app.buttons["home-history-expand"].tap()
        XCTAssertTrue(app.buttons["home-history-month"].waitForExistence(timeout: 3))
        app.buttons["home-history-month"].tap()
        app.buttons["enero de 2026"].tap()
        let history = app.scrollViews["home-history-content"]
        XCTAssertFalse(history.buttons["home-range-all"].exists)
        XCTAssertTrue(history.staticTexts["home-chart-date"].label.contains("ene"))
        shot(app, "home-history-january-es")
        app.buttons["home-history-done"].tap()
        XCTAssertTrue(app.staticTexts["home-greeting"].exists)
    }
    private func shot(_ app: XCUIApplication,_ name: String) {
        let a = XCTAttachment(screenshot: app.screenshot()); a.name = name; a.lifetime = .keepAlways; add(a)
    }
}
