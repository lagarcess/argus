import XCTest

final class CuadraoHomeChartUITests: XCTestCase {
    func testHomeBalanceChartAndSpaces() {
        continueAfterFailure = false
        let app = launch()
        XCTAssertEqual(app.staticTexts["home-chart-amount"].label, "153,920.00")
        XCTAssertFalse(app.segmentedControls["home-chart-view"].exists)
        XCTAssertFalse(app.buttons["home-range-year"].exists)
        shot(app, "quiet-home-es")
        let chart = app.otherElements.matching(identifier: "home-balance-chart").firstMatch
        chart.coordinate(withNormalizedOffset: CGVector(dx: 0.2, dy: 0.5)).tap()
        XCTAssertNotEqual(app.staticTexts["home-chart-date"].label, "Balance neto")
        let earlier = app.staticTexts["home-chart-date"].label
        chart.coordinate(withNormalizedOffset: CGVector(dx: 0.2, dy: 0.5)).press(forDuration: 0.35, thenDragTo: chart.coordinate(withNormalizedOffset: CGVector(dx: 0.75, dy: 0.5)))
        XCTAssertNotEqual(app.staticTexts["home-chart-date"].label, earlier)
        app.buttons["home-chart-today"].tap()
        XCTAssertEqual(app.staticTexts["home-chart-amount"].label, "153,920.00")
        app.buttons["cuadrao-space-household"].tap()
        XCTAssertEqual(app.staticTexts["home-chart-amount"].label, "43,500.00")
        shot(app, "quiet-home-household-es")
    }
    func testHistoryRangesAndDistribution() {
        continueAfterFailure = false
        let app = launch()
        app.buttons["home-history-expand"].tap()
        let period = app.staticTexts["home-history-period"]
        XCTAssertTrue(period.waitForExistence(timeout: 3))
        let current = period.label
        let chart = app.otherElements.matching(identifier: "home-balance-chart").firstMatch
        chart.swipeRight(velocity: .fast)
        XCTAssertNotEqual(period.label, current)
        let previous = period.label
        chart.coordinate(withNormalizedOffset: CGVector(dx: 0.2, dy: 0.5)).press(forDuration: 0.35, thenDragTo: chart.coordinate(withNormalizedOffset: CGVector(dx: 0.75, dy: 0.5)))
        XCTAssertEqual(period.label, previous, "Inspection must not page the calendar")
        shot(app, "history-previous-inspect-es")
        chart.swipeLeft(velocity: .fast)
        XCTAssertEqual(period.label, current)
        chart.swipeLeft(velocity: .fast)
        XCTAssertEqual(period.label, current, "No future periods")
        app.segmentedControls["home-history-range"].buttons["Año"].tap()
        shot(app, "history-year-es")
        app.segmentedControls["home-chart-view"].buttons["Distribución"].tap()
        XCTAssertTrue(app.buttons["home-distribution-segment-savings"].waitForExistence(timeout: 3))
        shot(app, "distribution-whole-es")
        app.buttons["home-distribution-savings"].tap()
        XCTAssertTrue(app.scrollViews["home-insights-content"].staticTexts.containing(NSPredicate(format: "label CONTAINS %@", "Mi tranquilidad")).firstMatch.exists)
        shot(app, "distribution-savings-es")
        app.buttons["home-distribution-all"].tap()
        XCTAssertEqual(app.buttons["home-distribution-savings"].value as? String, "Contraído")
        app.buttons["home-distribution-segment-checking"].tap()
        XCTAssertEqual(app.buttons["home-distribution-checking"].value as? String, "Expandido")
        shot(app, "distribution-checking-es")
        app.buttons["home-history-done"].tap()
        XCTAssertTrue(app.staticTexts["home-greeting"].exists)
    }
    func testDarkAndLargeEnglish() {
        continueAfterFailure = false
        let app = launch(english: true)
        shot(app, "quiet-home-dark-large-en")
        app.buttons["home-history-expand"].tap()
        app.segmentedControls["home-chart-view"].buttons["Breakdown"].tap()
        shot(app, "distribution-dark-large-en")
        let row = app.buttons["home-distribution-savings"]
        for _ in 0..<4 {
            if row.isHittable { break }
            app.scrollViews["home-insights-content"].swipeUp()
        }
        XCTAssertTrue(row.isHittable)
        row.tap()
        shot(app, "distribution-dark-large-expanded-en")
        app.buttons["home-history-done"].tap()
        XCTAssertTrue(app.staticTexts["home-greeting"].exists)
    }
    private func launch(english: Bool = false) -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments = ["--plan-reset", "-cuadrao.design.appearance", english ? "dark" : "light"]
        if english { app.launchArguments += ["--design-english", "-UIPreferredContentSizeCategoryName", "UICTContentSizeCategoryAccessibilityM"] }
        app.launch()
        return app
    }
    private func shot(_ app: XCUIApplication, _ name: String) {
        let a = XCTAttachment(screenshot: app.screenshot()); a.name = name; a.lifetime = .keepAlways; add(a)
    }
}
