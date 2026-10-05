import XCTest

/// Home movement taps open the authorized detail and return to the same scroll
/// position; account and movement rows expose swipe shortcuts on iOS 27 and keep
/// the context menu and detail actions as the fallback before it.
extension FinancialLoopUITests {
    var homeSwipesAvailable: Bool { ProcessInfo.processInfo.operatingSystemVersion.majorVersion >= 27 }

    func testHomeMovementOpensDetailAndBackKeepsPosition() throws {
        try signIn()
        let stamp = String(UUID().uuidString.prefix(4))
        let account = createMoneyAccount("Tap home " + stamp, type: "cash", amount: "300")
        recordMoney(kind: "expense", amount: "12", note: "Bus " + stamp)
        recordMoney(kind: "income", amount: "40", note: "Tips " + stamp)
        let row = homeMovementRow("Bus " + stamp)
        revealOnHome(row)
        let before = row.frame
        capture("home-movement-row-before-open")
        openMovement(row)
        assertText("Bus " + stamp)
        assertText("DOP 12.00")
        capture("home-movement-detail")
        tapVisible(app.buttons["activity-detail-account." + account.id])
        XCTAssertTrue(app.buttons["accounts.record"].waitForExistence(timeout: 10))
        tapVisible(app.buttons["accounts.back"])
        XCTAssertTrue(app.buttons["activity.back"].waitForExistence(timeout: 10))
        assertText("Bus " + stamp)
        tapVisible(app.buttons["activity.back"])
        XCTAssertTrue(row.waitForExistence(timeout: 10))
        XCTAssertEqual(row.frame.minY, before.minY, accuracy: 2, "Home returns to the same scroll position")
        XCTAssertEqual(row.frame.height, before.height, accuracy: 2)
        capture("home-movement-back-same-position")
        // The row at that same frame still opens its detail: the real meaning of "still hittable".
        openMovement(row)
        tapVisible(app.buttons["activity.back"])
        XCTAssertTrue(app.descendants(matching: .any)["screen.activity"].waitForNonExistence(timeout: 10))
    }

    func testAccountRowSwipesAddEditAndMoreArchive() throws {
        try signIn()
        let stamp = String(UUID().uuidString.prefix(4))
        let bank = createMoneyAccount("Swipe bank " + stamp, type: "checking", amount: "50")
        app.openAccountsList()
        let row = app.buttons["accounts.row." + bank.id]
        revealOnHome(row)
        if homeSwipesAvailable {
            row.swipeRight()
            capture("account-swipe-add-movement")
            tapVisible(app.buttons["accounts.swipe.record"])
        } else {
            row.press(forDuration: 1.0)
            tapVisible(app.buttons["Add transaction"])
        }
        XCTAssertTrue(app.textFields["loop.amount"].waitForExistence(timeout: 10))
        XCTAssertTrue(app.staticTexts[bank.name].waitForExistence(timeout: 5), "the editor records into the swiped account")
        cancelEditor()
        XCTAssertTrue(app.textFields["loop.amount"].waitForNonExistence(timeout: 10))
        revealOnHome(row)
        if homeSwipesAvailable {
            row.swipeLeft()
            capture("account-swipe-edit-more")
            tapVisible(app.buttons["accounts.swipe.edit"])
        } else {
            row.press(forDuration: 1.0)
            tapVisible(app.buttons["Rename account"])
        }
        let nickname = app.textFields["accounts.nickname"]
        XCTAssertTrue(nickname.waitForExistence(timeout: 10))
        XCTAssertEqual(nickname.value as? String, bank.name)
        cancelEditor()
        XCTAssertTrue(nickname.waitForNonExistence(timeout: 10))
        revealOnHome(row)
        if homeSwipesAvailable {
            row.swipeLeft()
            tapVisible(app.buttons["accounts.swipe.more"])
            // The dialog exposes each action twice to XCUITest; either copy is the same button.
            let archive = app.buttons.matching(identifier: "accounts.more.archive").firstMatch
            XCTAssertTrue(archive.waitForExistence(timeout: 5))
            XCTAssertTrue(app.buttons.matching(identifier: "accounts.more.check").firstMatch.exists)
            capture("account-more-menu")
            archive.tap()
        } else {
            row.press(forDuration: 1.0)
            tapVisible(app.buttons["Archive"])
        }
        XCTAssertTrue(row.waitForNonExistence(timeout: 10))
        capture("account-archived-from-more")
        openArchivedAccounts()
        let archived = app.buttons["accounts.row." + bank.id]
        XCTAssertTrue(archived.waitForExistence(timeout: 10))
        tapVisible(archived)
        tapVisible(app.buttons["accounts.archive"])
        XCTAssertTrue(app.buttons["Archive account"].waitForExistence(timeout: 10))
        app.openAccountsList()
        XCTAssertTrue(row.waitForExistence(timeout: 10), "the account is active again on Home")
        capture("account-restored-after-more-archive")
    }

    func testMovementRowSwipesOpenCorrectionAndCategory() throws {
        try signIn()
        let stamp = String(UUID().uuidString.prefix(4))
        _ = createMoneyAccount("Swipe cash " + stamp, type: "cash", amount: "90")
        recordMoney(kind: "expense", amount: "15", note: "Taxi " + stamp)
        let row = homeMovementRow("Taxi " + stamp)
        revealOnHome(row)
        if homeSwipesAvailable {
            row.swipeRight()
            capture("movement-swipe-edit")
            tapVisible(app.buttons["home.activity.swipe.edit"])
        } else {
            row.tap()
            tapVisible(app.buttons["activity.correct"])
        }
        XCTAssertTrue(app.textFields["loop.reason"].waitForExistence(timeout: 10), "a correction still requires its reason")
        XCTAssertEqual(app.textFields["loop.amount"].value as? String, "15.00")
        cancelEditor()
        XCTAssertTrue(app.textFields["loop.reason"].waitForNonExistence(timeout: 10))
        if homeSwipesAvailable {
            revealOnHome(row)
            row.swipeLeft()
            capture("movement-swipe-category")
            tapVisible(app.buttons["home.activity.swipe.category"])
        } else {
            if app.buttons["activity.back"].exists { app.buttons["activity.back"].tap() }
            revealOnHome(row); row.tap()
            tapVisible(app.buttons["activity.correct"])
        }
        XCTAssertTrue(app.textFields["loop.reason"].waitForExistence(timeout: 10))
        let category = app.buttons["loop.category"]
        XCTAssertTrue(category.waitForExistence(timeout: 10))
        XCTAssertTrue(category.isHittable, "the category control is in view")
        capture("movement-category-shortcut")
        cancelEditor()
        XCTAssertTrue(app.textFields["loop.reason"].waitForNonExistence(timeout: 10))
        if app.buttons["activity.back"].exists { app.buttons["activity.back"].tap() }
    }

    /// The Archived accounts entry sits in the Accounts header; scroll Home itself back up to it.
    func openArchivedAccounts() {
        let manage = app.buttons["accounts.manage"]
        revealOnHome(manage)
        manage.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5)).tap()
        XCTAssertTrue(app.buttons["accounts.manage.back"].waitForExistence(timeout: 10), "Archived accounts opens")
    }

    func openMovement(_ row: XCUIElement) {
        row.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5)).tap()
        XCTAssertTrue(app.descendants(matching: .any)["screen.activity"].waitForExistence(timeout: 10))
        XCTAssertTrue(app.buttons["activity.correct"].waitForExistence(timeout: 10))
        XCTAssertTrue(app.buttons["activity.repeat"].exists)
    }

    /// The account form carries an identifier; the activity editor's cancel is its label.
    func cancelEditor() {
        tapVisible(app.buttons.matching(NSPredicate(format: "identifier == 'accounts.cancel' OR label == 'Cancel'")).firstMatch)
    }

    func homeMovementRow(_ note: String) -> XCUIElement {
        app.revealConnectedTabBar()
        app.buttons["tab.home"].tap()
        let row = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'home.activity.' AND label CONTAINS %@", note)).firstMatch
        XCTAssertTrue(row.waitForExistence(timeout: 10))
        return row
    }
}
