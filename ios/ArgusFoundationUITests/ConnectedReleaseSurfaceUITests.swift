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
        let tray = app.descendants(matching: .any)["add.tray"]
        XCTAssertTrue(tray.exists)
        XCTAssertLessThan(tray.frame.height, 3 * 70 + 40, "the tray hugs its three rows")
        XCTAssertLessThan(app.buttons["add.tray.account"].frame.minY - tray.frame.minY, 40, "with no empty space above the first row")
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
        XCTAssertTrue(app.buttons["accounts.cancel"].isHittable, "Cancel is a plain text button")
        capture("release-surface-account-editor")
        cancelEditor()

        add.tap()
        app.buttons["add.tray.plan"].tap()
        XCTAssertTrue(app.buttons["Cancel"].waitForExistence(timeout: 10), "Plan opens the plan editor")
        cancelEditor()

        // Tapping outside the tray, or swiping down, closes it.
        add.tap()
        XCTAssertTrue(app.buttons["add.tray.plan"].waitForExistence(timeout: 5))
        app.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.12)).tap()
        let dimTapped = XCTNSPredicateExpectation(predicate: NSPredicate(format: "exists == false"), object: app.buttons["add.tray.plan"])
        XCTAssertEqual(XCTWaiter.wait(for: [dimTapped], timeout: 5), .completed, "tapping outside closes the tray")
        add.tap()
        XCTAssertTrue(app.buttons["add.tray.plan"].waitForExistence(timeout: 5))
        app.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.2)).press(forDuration: 0.05, thenDragTo: app.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5)))
        let swiped = XCTNSPredicateExpectation(predicate: NSPredicate(format: "exists == false"), object: app.buttons["add.tray.plan"])
        XCTAssertEqual(XCTWaiter.wait(for: [swiped], timeout: 5), .completed, "swiping down closes the tray")

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

        // Free tier: Search has no chats, files or memory to offer, so those filters are not shown.
        app.buttons["tab.search"].tap()
        XCTAssertTrue(app.buttons["search.filter.plans"].waitForExistence(timeout: 10))
        XCTAssertTrue(app.buttons["search.filter.all"].exists)
        for kind in ["chats", "files", "memory"] { XCTAssertFalse(app.buttons["search.filter." + kind].exists, kind) }
        capture("release-surface-search-filters")
        app.buttons["search.filter.plans"].tap()
        let copy = app.staticTexts["Create a goal, budget or debt plan with the + button."]
        let rows = app.descendants(matching: .any).matching(NSPredicate(format: "identifier BEGINSWITH 'search.row.'"))
        if rows.firstMatch.waitForExistence(timeout: 5) == false { XCTAssertTrue(copy.waitForExistence(timeout: 10), "empty Plans points to the + button") }
        app.buttons["search.filter.all"].tap()

        // The tray does not outlive the screen it was opened on.
        app.buttons["tab.home"].tap()
        add.tap()
        XCTAssertTrue(app.buttons["add.tray.plan"].waitForExistence(timeout: 5))
        app.buttons["tab.search"].tap()
        let leftBehind = XCTNSPredicateExpectation(predicate: NSPredicate(format: "exists == false"), object: app.buttons["add.tray.plan"])
        XCTAssertEqual(XCTWaiter.wait(for: [leftBehind], timeout: 5), .completed, "changing tab closes the tray")
        XCTAssertEqual(add.label, "Add", "and the + is a + again")
    }
}
