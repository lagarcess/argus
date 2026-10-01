import XCTest

final class CuadraoPolishUITests: XCTestCase {
    func testHomeHoldReorderAndArchiveRecovery() {
        continueAfterFailure = false
        let app = launch()
        let homeAccounts = app.buttons["home-accounts-open"]
        reveal(app, homeAccounts)
        XCTAssertFalse(app.buttons["Opciones de cuentas"].exists)
        XCTAssertTrue(app.buttons["home-account-add"].exists)
        let account = app.buttons.containing(NSPredicate(format: "label CONTAINS %@", "Día a día")).firstMatch
        reveal(app, account)
        account.press(forDuration: 0.7)
        XCTAssertTrue(app.buttons["account-reorder"].waitForExistence(timeout: 3))
        shot(app, "home-account-hold-es")
        app.buttons["account-reorder"].tap()
        XCTAssertEqual(app.buttons["accounts-order-toggle"].label, "Listo")
        let handles = app.buttons.matching(NSPredicate(format: "label BEGINSWITH %@", "Reorder"))
        XCTAssertTrue(handles.firstMatch.waitForExistence(timeout: 3))
        let first = handles.element(boundBy: 0)
        let second = handles.element(boundBy: 1)
        first.press(forDuration: 0.4, thenDragTo: second)
        app.buttons["accounts-order-toggle"].tap()
        shot(app, "accounts-management-es")
        let rows = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH %@", "accounts-row-"))
        XCTAssertTrue(rows.element(boundBy: 1).label.contains("Día a día"))
        rows.element(boundBy: 1).tap()
        app.buttons["Opciones de cuenta"].tap()
        app.buttons["Archivar"].tap()
        XCTAssertTrue(app.buttons["accounts-archives"].waitForExistence(timeout: 3))
        app.buttons["accounts-archives"].tap()
        XCTAssertTrue(app.staticTexts["Día a día"].waitForExistence(timeout: 3))
        shot(app, "account-archive-recovery-es")
        app.buttons["Restaurar"].tap()
        XCTAssertTrue(app.staticTexts["No hay cuentas archivadas"].exists)
        app.buttons["Listo"].tap()
        XCTAssertTrue(rows.containing(NSPredicate(format: "label CONTAINS %@", "Día a día")).firstMatch.exists)
        app.buttons["Cerrar"].tap()
        reveal(app, app.buttons["home-activity-add"])
        shot(app, "home-section-shortcuts-es")
        app.buttons["home-activity-add"].tap()
        XCTAssertTrue(app.navigationBars["Añadir movimiento"].waitForExistence(timeout: 3))
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
    func testLargeEnglishPlanControls() {
        continueAfterFailure = false
        let app = XCUIApplication()
        app.launchArguments = ["--plan-reset", "--design-english", "-cuadrao.design.appearance", "dark",
                               "-UIPreferredContentSizeCategoryName", "UICTContentSizeCategoryAccessibilityM"]
        app.launch(); app.buttons["cuadrao-tab-1"].tap()
        reveal(app, app.buttons["plan-forecast-scope"])
        app.buttons["plan-forecast-scope"].tap(); app.buttons["Household"].tap()
        shot(app, "plan-dark-large-en")
        reveal(app, app.buttons["plan-space-filter"])
        app.buttons["plan-space-filter"].tap(); app.buttons["Household"].tap()
        XCTAssertEqual(app.buttons["plan-space-filter"].value as? String, "Household")
        shot(app, "plan-filter-dark-large-en")
    }
    func testPlanScopeDoesNotChangeCreationDefault() {
        continueAfterFailure = false
        let app = launch()
        app.buttons["cuadrao-tab-1"].tap()
        app.buttons["plan-forecast-scope"].tap()
        app.buttons["Hogar"].tap()
        XCTAssertTrue(app.buttons["plan-forecast-scope"].label.contains("Hogar"))
        XCTAssertEqual(app.buttons["plan-space-filter"].value as? String, "Todos los espacios")
        shot(app, "plan-local-forecast-scope-es")
        app.buttons["plan-create"].tap()
        XCTAssertTrue(app.buttons["plan-edit-space"].waitForExistence(timeout: 3))
        reveal(app, app.buttons["plan-edit-space"])
        XCTAssertTrue(app.buttons["plan-edit-space"].label.contains("Personal"))
        app.buttons["plan-edit-space"].tap(); app.buttons["Hogar"].tap()
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
        let app = XCUIApplication()
        app.launchArguments = ["--plan-reset", "-cuadrao.design.appearance", "light"]
        app.launch(); return app
    }
    private func reveal(_ app: XCUIApplication, _ element: XCUIElement) {
        for _ in 0..<6 {
            if element.isHittable && element.frame.maxY < app.frame.maxY - 110 { return }
            app.swipeUp()
        }
        XCTAssertTrue(element.isHittable)
    }
    private func shot(_ app: XCUIApplication, _ name: String) {
        let a = XCTAttachment(screenshot: app.screenshot()); a.name = name; a.lifetime = .keepAlways; add(a)
    }
}
