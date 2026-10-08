import XCTest

/// The release set has no assistant tab, no Updates bell and no receipt capture. The third
/// navigation slot is a + that opens a tray of real actions; scrolling Home collapses the bar
/// into the + at the right, and sliding a finger across the bar chooses a tab.
extension FinancialLoopUITests {
    func testReleaseSurfaceAddTrayCollapseAndSlide() throws {
        try signIn()
        let stamp = String(UUID().uuidString.prefix(4))
        let first = createMoneyAccount("Release add one " + stamp, type: "checking", amount: "50")
        let second = createMoneyAccount("Release add two " + stamp, type: "cash", amount: "20")
        app.terminate()
        app.launchArguments = ["-AppleLanguages", "(en)", "-AppleLocale", "en_US", "--cuadrao-release-gates"]
        app.launch()
        app.openAccountsList()
        let add = app.buttons["nav.add"]
        XCTAssertTrue(add.waitForExistence(timeout: 15))
        XCTAssertFalse(app.buttons["tab.argus"].exists, "no assistant tab in the release set")
        XCTAssertFalse(app.buttons["cuadrao.updates.open"].exists, "no Updates bell in the release set")
        for id in ["tab.home", "tab.plan", "tab.search", "header.profile"] { XCTAssertTrue(app.buttons[id].exists, id) }
        XCTAssertEqual(add.frame.midX, app.frame.midX, accuracy: 2, "the open bar keeps the + in the middle slot")
        let openBarLeft = app.buttons["tab.home"].frame.minX

        // The tray holds only what is real in this build: households are off and receipts are not connected.
        add.tap()
        for row in ["account", "transaction", "plan"] {
            XCTAssertTrue(app.buttons["add.tray." + row].waitForExistence(timeout: 5), row)
        }
        for row in ["scan", "group", "invite"] { XCTAssertFalse(app.buttons["add.tray." + row].exists, row) }
        XCTAssertLessThan(app.buttons["add.tray.transaction"].frame.maxY, add.frame.minY, "the tray sits above the bar")
        capture("release-surface-add-tray")
        app.buttons["add.tray.transaction"].tap()
        XCTAssertTrue(app.staticTexts["Choose an account"].waitForExistence(timeout: 10), "several accounts ask which one")
        chooseFromDialog(second.id)
        XCTAssertTrue(app.buttons["loop.kind.expense"].waitForExistence(timeout: 10), "the editor opens for the chosen account")
        cancelEditor()
        XCTAssertFalse(app.buttons["add.tray.account"].exists, "choosing a row closes the tray")

        add.tap()
        app.buttons["add.tray.account"].tap()
        XCTAssertTrue(app.buttons["accounts.type.checking"].waitForExistence(timeout: 10), "Account starts a new account")
        cancelEditor()

        add.tap()
        app.buttons["add.tray.plan"].tap()
        XCTAssertTrue(app.buttons["Cancel"].waitForExistence(timeout: 10), "Plan opens the plan editor")
        cancelEditor()

        // Scrolling Home down collapses the bar into the + at the right; the tray still opens from it.
        for _ in 0..<4 { app.swipeUp(velocity: .fast) }
        XCTAssertTrue(add.waitForExistence(timeout: 5))
        XCTAssertGreaterThan(add.frame.midX, app.frame.width - 60, "the collapsed + sits at the right edge")
        XCTAssertFalse(app.buttons["tab.plan"].exists && app.buttons["tab.plan"].isHittable, "the other slots fold into the +")
        capture("release-surface-bar-collapsed")
        add.tap()
        XCTAssertTrue(app.buttons["add.tray.transaction"].waitForExistence(timeout: 5), "the collapsed + opens the tray")
        add.tap()
        XCTAssertFalse(app.buttons["add.tray.transaction"].waitForExistence(timeout: 1))
        for _ in 0..<4 { app.swipeDown(velocity: .fast) }
        XCTAssertTrue(app.buttons["tab.plan"].waitForExistence(timeout: 5), "scrolling up expands the bar")
        XCTAssertEqual(app.buttons["tab.home"].frame.minX, openBarLeft, accuracy: 2)

        // Sliding across the bar follows the finger and chooses the slot it lifts on.
        let search = app.buttons["tab.search"], plan = app.buttons["tab.plan"]
        search.press(forDuration: 0.3, thenDragTo: plan)
        XCTAssertTrue(plan.isSelected, "lifting over Plan from Search chooses Plan")
        _ = first
    }

    /// The chooser's buttons carry the account id, so Home rows with the same name cannot match.
    private func chooseFromDialog(_ accountID: String) {
        let option = app.buttons.matching(identifier: "nav.add.account." + accountID.uppercased()).firstMatch
        XCTAssertTrue(option.waitForExistence(timeout: 5))
        option.tap()
    }
}
