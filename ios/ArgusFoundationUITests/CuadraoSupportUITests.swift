import XCTest

final class CuadraoSupportUITests: XCTestCase {
    func testProfileDraftSaveCancelAndValidation() {
        let app = launch()
        app.buttons["cuadrao-tab-4"].tap()
        app.buttons["cuadrao.profile.identity"].tap()
        app.buttons["cuadrao.profile.avatar.coast"].tap()
        let preferred = app.textFields["cuadrao.profile.preferred"]
        reveal(app, preferred); replace(preferred, with: "Luna")
        app.buttons["cuadrao.profile.cancel"].tap()
        app.buttons["cuadrao.profile.identity"].tap()
        XCTAssertTrue(app.buttons["cuadrao.profile.avatar.initial"].isSelected)
        reveal(app, preferred)
        XCTAssertEqual(preferred.value as? String, "Alex")
        replace(preferred, with: "Luna")
        app.swipeDown()
        let theme = app.buttons["cuadrao.profile.avatar.bloom"]
        reveal(app, theme); theme.tap()
        XCTAssertTrue(app.buttons["cuadrao.profile.save"].isEnabled)
        app.buttons["cuadrao.profile.save"].tap()
        app.buttons["cuadrao-tab-0"].tap()
        XCTAssertEqual(app.staticTexts["home-greeting"].label, "Hola, Luna")
        app.buttons["cuadrao-tab-4"].tap()
        app.buttons["cuadrao.profile.identity"].tap()
        XCTAssertTrue(theme.isSelected)
        let name = app.textFields["cuadrao.profile.name"]
        reveal(app, name); replace(name, with: "")
        XCTAssertFalse(app.buttons["cuadrao.profile.save"].isEnabled)
        shot(app, "profile-validation-es")
        app.buttons["cuadrao.profile.cancel"].tap()
        XCTAssertTrue(app.staticTexts["Alex Rivera"].exists)
    }

    func testSearchPlansChatReturnAndRecovery() {
        let app = launch()
        app.buttons["cuadrao-tab-3"].tap()
        let query = app.textFields["cuadrao.search.query"]
        query.tap(); query.typeText("Samaná\n")
        let plan = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH %@", "cuadrao.search.plan.")).firstMatch
        XCTAssertTrue(plan.waitForExistence(timeout: 3)); plan.tap()
        XCTAssertTrue(app.buttons["plan-detail-options"].waitForExistence(timeout: 3))
        shot(app, "search-real-plan-es")
        app.navigationBars.buttons.firstMatch.tap()
        XCTAssertEqual(query.value as? String, "Samaná")
        replace(query, with: "certificados\n")
        app.buttons.containing(NSPredicate(format: "label CONTAINS %@", "Entender los certificados")).firstMatch.tap()
        XCTAssertTrue(app.buttons["cuadrao.search.return"].waitForExistence(timeout: 3))
        shot(app, "search-chat-return-es")
        app.buttons["cuadrao.search.return"].tap()
        XCTAssertEqual(query.value as? String, "certificados")
        replace(query, with: "no-hay-este-resultado\n")
        XCTAssertTrue(app.buttons["cuadrao.search.clear"].waitForExistence(timeout: 3))
        shot(app, "search-no-results-es")
        app.buttons["cuadrao.search.clear"].tap()
        XCTAssertEqual(query.value as? String, "Buscar")
        app.buttons["cuadrao.search.kind.plans"].tap()
        XCTAssertTrue(plan.waitForExistence(timeout: 3))
        app.buttons["cuadrao.search.filters"].tap()
        app.buttons["Incluir"].tap()
        app.buttons["Hogar"].tap()
        app.buttons["Listo"].tap()
        XCTAssertFalse(app.staticTexts["Un finde en Samaná"].exists)
        XCTAssertTrue(app.staticTexts["Casa a nuestro gusto"].exists)
        query.tap(); query.typeText("Samaná\n")
        XCTAssertTrue(app.buttons["cuadrao.search.reset"].exists)
        app.buttons["cuadrao.search.reset"].tap()
        XCTAssertTrue(plan.exists)
    }

    func testUpdatesReadStateDetailBackAndPreferences() {
        let app = launch()
        let bell = app.buttons["cuadrao.updates.open"]
        let initial = bell.value as? String
        bell.tap()
        let account = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH %@", "cuadrao.updates.item.account-")).firstMatch
        XCTAssertTrue(account.waitForExistence(timeout: 3))
        let accountID = account.identifier
        account.tap()
        XCTAssertTrue(app.staticTexts["account-detail-title"].waitForExistence(timeout: 3))
        app.navigationBars.buttons.firstMatch.tap()
        XCTAssertEqual(app.buttons[accountID].value as? String, "Leída")
        app.buttons[accountID].press(forDuration: 1)
        app.buttons["Marcar como no leída"].tap()
        XCTAssertEqual(app.buttons[accountID].value as? String, "Sin leer")
        app.buttons[accountID].swipeLeft()
        app.buttons["Marcar como leída"].tap()
        XCTAssertEqual(app.buttons[accountID].value as? String, "Leída")
        let plan = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH %@", "cuadrao.updates.item.plan-")).firstMatch
        plan.tap()
        XCTAssertTrue(app.buttons["plan-detail-options"].waitForExistence(timeout: 3))
        app.navigationBars.buttons.firstMatch.tap()
        app.buttons["cuadrao.updates.done"].tap()
        XCTAssertNotEqual(bell.value as? String, initial)
        bell.tap()
        XCTAssertEqual(app.buttons[accountID].value as? String, "Leída")
        app.buttons["cuadrao.updates.read-all"].tap()
        app.segmentedControls["cuadrao.updates.filter"].buttons["Sin leer"].tap()
        XCTAssertTrue(app.staticTexts["Estás al día"].waitForExistence(timeout: 3))
        shot(app, "updates-all-read-es")
        app.buttons["cuadrao.updates.preferences"].tap()
        XCTAssertTrue(app.navigationBars["Notificaciones"].waitForExistence(timeout: 3))
        let quiet = app.switches["Horario de descanso"]
        reveal(app, quiet)
        quiet.coordinate(withNormalizedOffset: CGVector(dx: 0.9, dy: 0.5)).tap()
        let enabled = XCTNSPredicateExpectation(predicate: NSPredicate(format: "value == %@", "1"), object: quiet)
        XCTAssertEqual(XCTWaiter.wait(for: [enabled], timeout: 3), .completed)
        let start = app.descendants(matching: .any).matching(identifier: "cuadrao.quiet.start").firstMatch
        let end = app.descendants(matching: .any).matching(identifier: "cuadrao.quiet.end").firstMatch
        reveal(app, start); XCTAssertTrue(start.isHittable)
        reveal(app, end); XCTAssertTrue(end.isHittable)
        shot(app, "notification-quiet-hours-es")
        app.navigationBars.buttons.firstMatch.tap()
        app.buttons["cuadrao.updates.done"].tap()
        XCTAssertEqual(bell.value as? String, "0 sin leer")
    }

    func testEmptyUpdatesAndPlanPerspective() {
        let app = launch(extra: ["--plan-empty"])
        app.staticTexts["home-greeting"].press(forDuration: 1)
        app.buttons["Vista previa: primer uso"].tap()
        app.buttons["cuadrao.updates.open"].tap()
        XCTAssertTrue(app.staticTexts["Todo tranquilo por aquí"].waitForExistence(timeout: 3))
        XCTAssertFalse(app.buttons["cuadrao.updates.read-all"].exists)
        shot(app, "updates-empty-es")
        app.buttons["cuadrao.updates.done"].tap()
        app.buttons["cuadrao-tab-3"].tap()
        app.buttons["cuadrao.search.kind.plans"].tap()
        XCTAssertTrue(app.staticTexts["Sin planes todavía"].waitForExistence(timeout: 3))
        XCTAssertTrue(app.buttons["cuadrao.search.everything"].exists)
        shot(app, "search-empty-plans-es")
    }

    func testSupportDarkEnglishLargeText() {
        let app = launch(extra: ["--design-english", "-cuadrao.design.appearance", "dark",
                                "-UIPreferredContentSizeCategoryName", "UICTContentSizeCategoryAccessibilityM"])
        app.buttons["cuadrao.updates.open"].tap()
        XCTAssertTrue(app.segmentedControls["cuadrao.updates.filter"].exists)
        shot(app, "updates-dark-large-en")
        app.buttons["cuadrao.updates.done"].tap()
        app.buttons["cuadrao-tab-3"].tap()
        shot(app, "search-dark-large-en")
        app.buttons["cuadrao-tab-4"].tap()
        XCTAssertTrue(app.buttons["cuadrao.profile.identity"].isHittable)
        shot(app, "profile-dark-large-en")
        app.buttons["cuadrao.profile.identity"].tap()
        shot(app, "profile-avatar-dark-large-en")
        app.buttons["cuadrao.profile.cancel"].tap()
        reveal(app, app.buttons["cuadrao.profile.preferences"])
        app.buttons["cuadrao.profile.preferences"].tap()
        shot(app, "settings-dark-large-en")
    }

    private func launch(extra: [String] = []) -> XCUIApplication {
        continueAfterFailure = false
        let app = XCUIApplication()
        app.launchArguments = ["--plan-reset", "-cuadrao.design.appearance", "light"] + extra
        app.launch(); return app
    }
    private func replace(_ field: XCUIElement, with value: String) {
        field.coordinate(withNormalizedOffset: CGVector(dx: 0.98, dy: 0.5)).tap()
        field.typeText(String(repeating: XCUIKeyboardKey.delete.rawValue, count: (field.value as? String ?? "").count + 2))
        field.typeText(value)
    }
    private func reveal(_ app: XCUIApplication, _ element: XCUIElement) {
        for _ in 0..<8 {
            if element.isHittable && element.frame.maxY < app.frame.maxY - 100 { return }
            let goingDown = !element.exists || element.frame.minY > app.frame.midY
            let start = app.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: goingDown ? 0.65 : 0.35))
            let end = app.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: goingDown ? 0.4 : 0.6))
            start.press(forDuration: 0.01, thenDragTo: end)
        }
        XCTAssertTrue(element.isHittable)
    }
    private func shot(_ app: XCUIApplication, _ name: String) {
        Thread.sleep(forTimeInterval: 0.6)
        let attachment = XCTAttachment(screenshot: app.screenshot())
        attachment.name = name; attachment.lifetime = .keepAlways; add(attachment)
    }
}
