import XCTest

/// The release set has no assistant tab, no Updates bell and no receipt capture. The third
/// navigation slot is a + that records a movement, in the open bar and in the collapsed one.
extension FinancialLoopUITests {
    func testReleaseSurfaceAddReplacesTheAssistantAndStaysCentered() throws {
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
        XCTAssertEqual(add.frame.midX, app.frame.midX, accuracy: 2)
        let openBarLeft = app.buttons["tab.home"].frame.minX
        capture("release-surface-bar-open")

        add.tap()
        XCTAssertTrue(app.staticTexts["Choose an account"].waitForExistence(timeout: 10), "several accounts ask which one")
        capture("release-surface-add-chooser")
        chooseFromDialog(second.name)
        XCTAssertTrue(app.buttons["loop.kind.expense"].waitForExistence(timeout: 10), "the editor opens for the chosen account")
        cancelEditor()

        for _ in 0..<4 { app.swipeUp(velocity: .fast) }
        XCTAssertTrue(add.waitForExistence(timeout: 5))
        XCTAssertGreaterThan(app.buttons["tab.home"].frame.minX, openBarLeft + 20, "the bar collapses on scroll")
        XCTAssertEqual(add.frame.midX, app.frame.midX, accuracy: 2, "the + stays centered when the bar collapses")
        capture("release-surface-bar-collapsed")
        add.tap()
        XCTAssertTrue(app.staticTexts["Choose an account"].waitForExistence(timeout: 10), "the collapsed + still records a movement")
        chooseFromDialog(first.name)
        XCTAssertTrue(app.buttons["loop.kind.expense"].waitForExistence(timeout: 10))
    }

    /// The chooser lists accounts as plain buttons; Home's account rows carry `accounts.row.` identifiers.
    private func chooseFromDialog(_ name: String) {
        let option = app.buttons.matching(NSPredicate(format: "label CONTAINS %@ AND NOT identifier BEGINSWITH 'accounts.row.'", name)).firstMatch
        XCTAssertTrue(option.waitForExistence(timeout: 5))
        option.tap()
    }
}
