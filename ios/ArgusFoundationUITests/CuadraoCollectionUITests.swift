import XCTest

final class CuadraoCollectionUITests: XCTestCase {
    func testGroupPeopleOwnerAndRemovalReview() {
        continueAfterFailure = false
        let app = launch()
        app.buttons["cuadrao-tab-1"].tap()
        app.segmentedControls.buttons["En grupo"].tap()
        app.buttons["group-card-trip"].tap()
        app.buttons["group-people-open"].tap()
        XCTAssertTrue(app.buttons["group-invite"].waitForExistence(timeout: 3))
        app.buttons["group-remove-Ana"].tap()
        XCTAssertFalse(app.buttons["group-remove-confirm"].isEnabled)
        shot(app, "group-outstanding-removal-review")
        app.buttons["Cancelar"].tap()
        app.buttons["group-invite"].tap()
        reveal(app, app.buttons["group-invite-preview"])
        app.buttons["group-invite-preview"].tap()
        reveal(app, app.buttons["group-invite-accept"])
        app.buttons["group-invite-accept"].tap()
        app.buttons["Cerrar"].tap()
        reveal(app, app.buttons["group-remove-Mar"])
        shot(app, "group-people-owner")
        app.buttons["group-remove-Mar"].tap()
        XCTAssertTrue(app.buttons["group-remove-confirm"].isEnabled)
        app.buttons["group-remove-confirm"].tap()
        XCTAssertFalse(app.buttons["group-remove-Mar"].exists)
        XCTAssertTrue(app.buttons["Participaron antes"].exists)
    }
    func testMemberRoleAndLegacyControls() {
        continueAfterFailure = false
        let app = launch(extra: ["--group-member", "--legacy-collection", "--design-english"])
        app.buttons["cuadrao-tab-1"].tap()
        app.segmentedControls.buttons["Together"].tap()
        XCTAssertFalse(app.buttons["Edit"].exists)
        app.buttons["group-card-trip"].tap()
        app.buttons["group-people-open"].tap()
        XCTAssertFalse(app.buttons["group-invite"].exists)
        XCTAssertFalse(app.buttons["group-remove-Ana"].exists)
        shot(app, "group-people-member-en")
    }
    func testPersonalPlanSwipeEditArchiveRestore() {
        continueAfterFailure = false
        let app = launch()
        app.buttons["cuadrao-tab-1"].tap()
        let card = app.buttons["plan-row-goal-personal"]
        reveal(app, card)
        card.swipeRight()
        app.buttons["Editar"].tap()
        XCTAssertTrue(app.textFields["plan-name"].waitForExistence(timeout: 3))
        app.buttons["Cancelar"].tap()
        card.swipeLeft()
        shot(app, "plan-swipe-archive")
        app.buttons["Archivar"].tap()
        XCTAssertFalse(card.exists)
        reveal(app, app.buttons["plan-archives"])
        app.buttons["plan-archives"].tap()
        shot(app, "plan-archive-recovery")
        XCTAssertTrue(app.buttons["Retomar"].waitForExistence(timeout: 3))
        app.buttons["Retomar"].tap()
    }
    func testGroupNativeReorderPersistenceAndRecovery() {
        continueAfterFailure = false
        let app = launch()
        app.buttons["cuadrao-tab-1"].tap(); app.segmentedControls.buttons["En grupo"].tap()
        let trip = app.buttons["group-card-trip"], saving = app.buttons["group-card-saving"]
        reveal(app, saving)
        let source = trip.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.75))
        source.press(forDuration: 0.7, thenDragTo: saving.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.8)))
        app.swipeDown()
        XCTAssertLessThan(saving.frame.minY, trip.frame.minY)
        shot(app, "groups-reordered")
        app.terminate(); app.launchArguments = ["-cuadrao.design.appearance", "light"]; app.launch()
        app.buttons["cuadrao-tab-1"].tap(); app.segmentedControls.buttons["En grupo"].tap()
        XCTAssertLessThan(saving.frame.minY, trip.frame.minY)
        saving.swipeLeft(); app.buttons["Archivar"].tap()
        reveal(app, app.buttons["group-archives"]); app.buttons["group-archives"].tap()
        XCTAssertTrue(app.buttons["Retomar"].waitForExistence(timeout: 3)); app.buttons["Retomar"].tap()
    }
    private func launch(extra: [String] = []) -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments = ["--plan-reset", "-cuadrao.design.appearance", "light"] + extra
        app.launch(); return app
    }
    private func reveal(_ app: XCUIApplication, _ element: XCUIElement) {
        for _ in 0..<10 {
            if element.isHittable && element.frame.minY > 80 && element.frame.maxY < app.frame.maxY - 110 { return }
            let down = !element.exists || element.frame.minY > app.frame.midY
            app.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: down ? 0.65 : 0.35)).press(forDuration: 0.01,
                thenDragTo: app.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: down ? 0.4 : 0.6)))
        }
        XCTAssertTrue(element.isHittable)
    }
    private func shot(_ app: XCUIApplication, _ name: String) {
        let attachment = XCTAttachment(screenshot: app.screenshot()); attachment.name = name; attachment.lifetime = .keepAlways; add(attachment)
    }
}
