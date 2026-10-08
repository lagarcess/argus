import XCTest

/// The release set has no assistant tab, no Updates bell and no receipt capture. The third
/// navigation slot is a + that opens a tray of real actions; scrolling Home collapses the bar
/// into the + at the right, and sliding a finger across the bar chooses a tab.
extension FinancialLoopUITests {
    func testReleaseSurfaceAddTrayCollapseAndSlide() throws {
        try signIn()
        let stamp = String(UUID().uuidString.prefix(4))
        _ = createMoneyAccount("Release add one " + stamp, type: "checking", amount: "50")
        _ = createMoneyAccount("Release add two " + stamp, type: "cash", amount: "20")
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
        XCTAssertFalse(app.staticTexts["Choose an account"].exists, "no list of accounts comes first")
        XCTAssertTrue(app.buttons["loop.kind.expense"].waitForExistence(timeout: 10), "the editor opens at once")
        app.buttons["loop.kind.expense"].tap()
        XCTAssertTrue(app.descendants(matching: .any)["loop.account"].waitForExistence(timeout: 10), "and its account row can change the account")
        cancelEditor()
        XCTAssertTrue(app.buttons["loop.kind.expense"].waitForNonExistence(timeout: 10), "the editor finishes closing")
        let rowGone = XCTNSPredicateExpectation(predicate: NSPredicate(format: "exists == false"), object: app.buttons["add.tray.account"])
        XCTAssertEqual(XCTWaiter.wait(for: [rowGone], timeout: 5), .completed, "choosing a row closes the tray")

        add.tap()
        XCTAssertTrue(app.buttons["add.tray.account"].waitForExistence(timeout: 5), "the tray reopens")
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
        let closed = XCTNSPredicateExpectation(predicate: NSPredicate(format: "exists == false"), object: app.buttons["add.tray.transaction"])
        XCTAssertEqual(XCTWaiter.wait(for: [closed], timeout: 5), .completed, "the + (now an X) closes the tray")
        for _ in 0..<4 { app.swipeDown(velocity: .fast) }
        XCTAssertTrue(app.buttons["tab.plan"].waitForExistence(timeout: 5), "scrolling up expands the bar")
        XCTAssertEqual(app.buttons["tab.home"].frame.minX, openBarLeft, accuracy: 2)

        // Sliding across the bar follows the finger and chooses the slot it lifts on.
        let search = app.buttons["tab.search"], plan = app.buttons["tab.plan"]
        search.press(forDuration: 0.3, thenDragTo: plan)
        XCTAssertTrue(plan.isSelected, "lifting over Plan from Search chooses Plan")

        // The tray does not outlive the screen it was opened on.
        app.buttons["tab.home"].tap()
        add.tap()
        XCTAssertTrue(app.buttons["add.tray.plan"].waitForExistence(timeout: 5))
        let row = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'accounts.row.'")).firstMatch
        XCTAssertTrue(row.waitForExistence(timeout: 10))
        tapVisible(row)
        app.revealConnectedTabBar()
        XCTAssertTrue(add.waitForExistence(timeout: 10))
        XCTAssertFalse(app.buttons["add.tray.plan"].exists, "a pushed detail closes the tray")
        XCTAssertEqual(add.label, "Add", "and the + is a + again")
    }
}
