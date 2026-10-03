import XCTest

final class CuadraoPolishUITests: XCTestCase {
    func testHomeNativeSwipeDragAndArchiveRecovery() {
        continueAfterFailure = false
        let app = launch()
        let rows = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH %@", "home-account-"))
        let first = app.buttons["home-account-00000000-0000-4000-8000-000000000001"]
        let second = app.buttons["home-account-00000000-0000-4000-8000-000000000002"]
        reveal(app, second)
        let firstY = first.frame.minY
        first.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5)).press(forDuration: 0.7, thenDragTo: second.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.95)))
        XCTAssertGreaterThan(first.frame.minY, firstY)
        shot(app, "home-inline-reorder-es")
        first.swipeRight()
        XCTAssertTrue(app.buttons["Editar"].waitForExistence(timeout: 3))
        app.buttons["Editar"].tap()
        XCTAssertTrue(app.textFields.firstMatch.waitForExistence(timeout: 3))
        app.buttons["Cancelar"].tap()
        first.swipeLeft()
        XCTAssertTrue(app.buttons["Archivar"].waitForExistence(timeout: 3))
        shot(app, "home-swipe-archive-es")
        app.buttons["Archivar"].tap()
        XCTAssertFalse(first.exists)
        app.buttons["Deshacer"].tap()
        XCTAssertTrue(first.exists)
        XCTAssertGreaterThan(rows.count, 1)
    }
    func testArchivesRemainReachableWhenAllAccountsArchived() {
        continueAfterFailure = false
        let app = launch()
        app.buttons["cuadrao-space-household"].tap()
        reveal(app, app.buttons["home-accounts-open"])
        app.buttons["home-accounts-open"].tap()
        let rows = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH %@", "accounts-row-"))
        let count = rows.count
        XCTAssertGreaterThan(count, 0)
        for _ in 0..<count {
            rows.firstMatch.tap()
            app.buttons["Opciones de cuenta"].tap()
            app.buttons["Archivar"].tap()
            app.buttons["Archivar"].tap()
        }
        XCTAssertEqual(rows.count, 0)
        app.buttons["Cerrar"].tap()
        reveal(app, app.buttons["home-accounts-open"])
        app.buttons["home-accounts-open"].tap()
        XCTAssertFalse(app.buttons["accounts-order-toggle"].isEnabled)
        app.buttons["accounts-archives"].tap()
        XCTAssertEqual(app.buttons.matching(identifier: "Restaurar").count, count)
        shot(app, "all-accounts-archived-es")
        app.buttons.matching(identifier: "Restaurar").firstMatch.tap()
        app.buttons["Listo"].tap()
        XCTAssertEqual(rows.count, 1)
    }
    func testLargeEnglishAccountManagement() {
        continueAfterFailure = false
        let app = XCUIApplication.cuadraoPreview()
        app.launchArguments = CuadraoPreviewLaunch.arguments + ["--plan-reset", "--design-english", "-cuadrao.design.appearance", "dark",
                               "-UIPreferredContentSizeCategoryName", "UICTContentSizeCategoryAccessibilityM"]
        app.launch()
        reveal(app, app.buttons["home-accounts-open"])
        app.buttons["home-accounts-open"].tap()
        XCTAssertTrue(app.buttons["accounts-order-toggle"].waitForExistence(timeout: 3))
        shot(app, "accounts-dark-large-en")
        app.swipeUp()
        shot(app, "accounts-dark-large-lower-en")
    }
    func testLargeEnglishPlanControls() {
        continueAfterFailure = false
        let app = XCUIApplication.cuadraoPreview()
        app.launchArguments = CuadraoPreviewLaunch.arguments + ["--plan-reset", "--design-english", "-cuadrao.design.appearance", "dark",
                               "-UIPreferredContentSizeCategoryName", "UICTContentSizeCategoryAccessibilityM"]
        app.launch(); app.buttons["tab.plan"].tap()
        reveal(app, app.buttons["plan-forecast-scope"])
        app.buttons["plan-forecast-scope"].tap()
        shot(app, "forecast-choice-dark-large-en")
        app.buttons["Household"].tap()
        shot(app, "plan-dark-large-en")
        XCTAssertFalse(app.buttons["plan-space-filter"].exists)
        reveal(app, app.buttons["plan-archives"])
        shot(app, "plan-all-spaces-dark-large-en")
    }
    func testPlanScopeDoesNotChangeCreationDefault() {
        continueAfterFailure = false
        let app = launch()
        app.buttons["tab.plan"].tap()
        app.buttons["plan-forecast-scope"].tap()
        shot(app, "forecast-choice-aligned-es")
        app.buttons["Hogar"].tap()
        XCTAssertTrue(app.buttons["plan-forecast-scope"].label.contains("Hogar"))
        XCTAssertFalse(app.buttons["plan-space-filter"].exists)
        shot(app, "plan-local-forecast-scope-es")
        app.buttons["plan-create"].tap()
        XCTAssertTrue(app.buttons["plan-edit-space"].waitForExistence(timeout: 3))
        reveal(app, app.buttons["plan-edit-space"])
        XCTAssertTrue(app.buttons["plan-edit-space"].label.contains("Personal"))
        app.buttons["plan-edit-space"].tap()
        shot(app, "plan-space-choice-aligned-es")
        app.buttons["Hogar"].tap()
        XCTAssertTrue(app.buttons["plan-edit-space"].label.contains("Hogar"))
        shot(app, "plan-explicit-space-es")
    }
    func testAccountCurrencySearch() {
        continueAfterFailure = false
        let app = launch()
        reveal(app, app.buttons["home-account-add"])
        app.buttons["home-account-add"].tap()
        let currency = app.buttons["account-edit-currency"]
        for _ in 0..<4 {
            if currency.exists { break }
            let cash = app.buttons["Efectivo"]
            if cash.exists { cash.tap() } else { app.swipeUp() }
        }
        reveal(app, currency); currency.tap()
        XCTAssertTrue(app.navigationBars["Moneda"].waitForExistence(timeout: 3))
        let search = app.searchFields.firstMatch
        search.tap(); search.typeText("EUR")
        shot(app, "currency-search-es")
        app.buttons.containing(NSPredicate(format: "label CONTAINS %@", "EUR")).firstMatch.tap()
        XCTAssertTrue(currency.label.contains("EUR"))
    }
    private func launch() -> XCUIApplication {
        let app = XCUIApplication.cuadraoPreview()
        app.launchArguments = CuadraoPreviewLaunch.arguments + ["--plan-reset", "-cuadrao.design.appearance", "light"]
        app.launch(); return app
    }
    private func reveal(_ app: XCUIApplication, _ element: XCUIElement) {
        for _ in 0..<6 {
            if element.isHittable && element.frame.maxY < app.frame.maxY - 110 { return }
            let goingDown = !element.exists || element.frame.minY > app.frame.midY
            let start = app.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: goingDown ? 0.65 : 0.35))
            let end = app.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: goingDown ? 0.4 : 0.6))
            start.press(forDuration: 0.01, thenDragTo: end)
        }
        XCTAssertTrue(element.isHittable)
    }
    private func shot(_ app: XCUIApplication, _ name: String) {
        let a = XCTAttachment(screenshot: app.screenshot()); a.name = name; a.lifetime = .keepAlways; add(a)
    }
}
