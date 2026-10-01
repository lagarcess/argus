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
        app.buttons["home-view-distribution"].tap()
        XCTAssertFalse(app.buttons["home-period-year"].exists)
        XCTAssertFalse(period.exists)
        XCTAssertTrue(app.staticTexts["Activos · Hoy"].exists)
        app.buttons["home-view-history"].tap()
        XCTAssertEqual(period.label, previous, "Returning restores the history period")
        chart.swipeLeft(velocity: .fast)
        XCTAssertEqual(period.label, current)
        chart.swipeLeft(velocity: .fast)
        XCTAssertEqual(period.label, current, "No future periods")
        XCTAssertFalse(app.buttons["home-period-next"].isEnabled)
        app.buttons["home-period-year"].tap()
        app.buttons["home-period-previous"].tap()
        XCTAssertFalse(app.buttons["home-period-previous"].isEnabled, "Stop at oldest available year")
        app.buttons["home-period-next"].tap()
        XCTAssertFalse(app.buttons["home-period-next"].isEnabled)
        shot(app, "history-year-es")
        app.buttons["home-view-distribution"].tap()
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
        app.buttons["home-view-distribution"].tap()
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
    func testDistributionAccountRoundTrip() {
        continueAfterFailure = false
        let app = launch()
        app.buttons["home-history-expand"].tap()
        app.buttons["home-view-distribution"].tap()
        app.buttons["home-distribution-checking"].tap()
        let content = app.scrollViews["home-insights-content"]
        let link = content.buttons.matching(NSPredicate(format: "identifier BEGINSWITH %@ AND label CONTAINS %@", "home-distribution-account-", "Gastos de casa")).firstMatch
        for _ in 0..<3 {
            if link.isHittable && link.frame.maxY < app.frame.maxY - 50 { break }
            content.swipeUp()
        }
        XCTAssertTrue(link.isHittable)
        let linkID = link.identifier
        let originalY = link.frame.minY
        shot(app, "distribution-before-account-es")
        link.tap()
        XCTAssertEqual(app.staticTexts["account-detail-title"].label, "Gastos de casa")
        shot(app, "distribution-account-detail-es")
        app.buttons["account-detail-record"].tap()
        XCTAssertTrue(app.navigationBars["Añadir movimiento"].waitForExistence(timeout: 3))
        app.buttons["Cancelar"].tap()
        app.buttons["Opciones de cuenta"].tap()
        app.buttons["Cambiar nombre"].tap()
        let field = app.textFields.firstMatch
        XCTAssertTrue(field.waitForExistence(timeout: 3))
        field.tap()
        field.typeText(String(repeating: XCUIKeyboardKey.delete.rawValue, count: (field.value as? String ?? "").count))
        field.typeText("Gastos del hogar")
        app.buttons["Guardar"].tap()
        XCTAssertEqual(app.staticTexts["account-detail-title"].label, "Gastos del hogar")
        app.navigationBars.buttons.element(boundBy: 0).tap()
        XCTAssertEqual(app.buttons["home-distribution-checking"].value as? String, "Expandido")
        let returned = content.buttons[linkID]
        XCTAssertTrue(returned.label.contains("Gastos del hogar"), "Return must reflect the same account state")
        XCTAssertEqual(returned.frame.minY, originalY, accuracy: 3, "Return preserves scroll position")
        shot(app, "distribution-account-return-es")
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
