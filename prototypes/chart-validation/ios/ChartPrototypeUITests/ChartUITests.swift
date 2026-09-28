import XCTest

final class ChartUITests: XCTestCase {
    override func setUpWithError() throws { continueAfterFailure = false }
    func launch(_ scenario: String = "stress", locale: String = "en", theme: String = "light", cancelDrag: Bool = false) -> XCUIApplication {
        let app = XCUIApplication()
        app.launchEnvironment = ["CHART_CASE": scenario, "CHART_LOCALE": locale, "CHART_THEME": theme, "CHART_CANCEL_DRAG": cancelDrag ? "1" : "0"]
        app.launch()
        XCTAssertTrue(app.staticTexts["selectedDate"].waitForExistence(timeout: 15))
        return app
    }
    func capture(_ name: String) {
        let attachment = XCTAttachment(screenshot: XCUIScreen.main.screenshot())
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
    }
    func testReadoutEndpointsMissingResetAndLocale() throws {
        let url = Bundle(for: Self.self).url(forResource: "series", withExtension: "json")!
        let fixtures = try JSONDecoder().decode(FixtureBundle.self, from: Data(contentsOf: url))
        let stress = fixtures.cases.first { $0.id == "stress" }!
        let english = Presentation(spanish: false)
        let app = launch()
        app.buttons["next"].tap()
        XCTAssertEqual(app.staticTexts["selectedDate"].label, english.date(stress.points[0].date))
        XCTAssertEqual(app.staticTexts["actualValue"].label, "Actual: " + english.amount(stress.points[0].actual, currency: stress.currency))
        let missing = stress.points.firstIndex { $0.actual == nil && $0.projected == nil }!
        for _ in 0..<missing { app.buttons["next"].tap() }
        XCTAssertTrue(app.staticTexts["actualValue"].label.contains("No data"))
        capture("light-en-missing")
        app.buttons["reset"].tap()
        XCTAssertEqual(app.staticTexts["selectedDate"].label, "Select a date")
        app.buttons["previous"].tap()
        let endpoint = app.staticTexts["selectedDate"].label
        app.buttons["next"].tap()
        XCTAssertEqual(app.staticTexts["selectedDate"].label, endpoint)
        app.switches["locale"].tap()
        XCTAssertTrue(app.staticTexts["projectedValue"].label.contains("Proyectada"))
        app.buttons["Oscuro"].tap()
        capture("dark-es-endpoint")
    }
    func testHorizontalReleaseAndVerticalScroll() {
        let app = launch()
        let chart = app.otherElements["financialChart"]
        XCTAssertTrue(chart.exists)
        chart.coordinate(withNormalizedOffset: CGVector(dx: 0.2, dy: 0.5))
            .press(forDuration: 0.05, thenDragTo: chart.coordinate(withNormalizedOffset: CGVector(dx: 0.85, dy: 0.5)))
        let selected = app.staticTexts["selectedDate"].label
        XCTAssertNotEqual(selected, "Select a date")
        capture("horizontal-release")
        XCTAssertEqual(app.staticTexts["selectedDate"].label, selected)
        let beforeY = chart.frame.minY
        chart.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.85))
            .press(forDuration: 0.05, thenDragTo: chart.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.05)))
        XCTAssertEqual(app.staticTexts["selectedDate"].label, selected)
        XCTAssertLessThan(chart.frame.minY, beforeY - 40, "Chart-originated vertical drag must scroll the page")
        app.swipeUp()
        XCTAssertTrue(app.staticTexts["scrollEnd"].isHittable)
        capture("vertical-scroll")
    }
    func testNativeRecognizerCancellationRestoresSelection() {
        let app = launch(cancelDrag: true)
        app.buttons["next"].tap()
        let before = app.staticTexts["selectedDate"].label
        let chart = app.otherElements["financialChart"]
        chart.coordinate(withNormalizedOffset: CGVector(dx: 0.2, dy: 0.5))
            .press(forDuration: 0.05, thenDragTo: chart.coordinate(withNormalizedOffset: CGVector(dx: 0.85, dy: 0.5)))
        XCTAssertEqual(app.staticTexts["selectedDate"].label, before)
        capture("native-recognizer-cancellation")
    }
    func testScenarioResetsSelection() {
        let app = launch()
        app.buttons["next"].tap()
        app.buttons["scenario"].tap()
        app.buttons["empty"].tap()
        XCTAssertEqual(app.staticTexts["selectedDate"].label, "Select a date")
        XCTAssertFalse(app.buttons["next"].isEnabled)
    }
    func testEmptySingleAndContribution() {
        let empty = launch("empty")
        XCTAssertFalse(empty.buttons["next"].isEnabled)
        capture("empty")
        empty.terminate()
        let single = launch("single", theme: "system")
        single.buttons["next"].tap()
        let date = single.staticTexts["selectedDate"].label
        single.buttons["next"].tap()
        single.buttons["previous"].tap()
        XCTAssertEqual(single.staticTexts["selectedDate"].label, date)
        capture("single-system")
        single.terminate()
        let recurring = launch("recurring-contributions", locale: "es-419", theme: "dark")
        recurring.buttons["next"].tap()
        XCTAssertFalse(recurring.staticTexts["contributionValue"].label.contains("Sin datos"))
        capture("recurring-es-dark")
    }
    func testLongSeriesInteractionPerformance() {
        let app = launch("long")
        let chart = app.otherElements["financialChart"]
        let options = XCTMeasureOptions()
        options.iterationCount = 5
        var metrics: [XCTMetric] = [XCTClockMetric(), XCTCPUMetric(application: app), XCTMemoryMetric(application: app)]
        if #available(iOS 26.0, *) { metrics.append(XCTHitchMetric(application: app)) }
        measure(metrics: metrics, options: options) {
            chart.coordinate(withNormalizedOffset: CGVector(dx: 0.15, dy: 0.5))
                .press(forDuration: 0.05, thenDragTo: chart.coordinate(withNormalizedOffset: CGVector(dx: 0.9, dy: 0.5)))
            XCTAssertNotEqual(app.staticTexts["selectedDate"].label, "Select a date")
        }
        capture("long-series")
    }
}
