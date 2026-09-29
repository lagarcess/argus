import XCTest
import UIKit
import UniformTypeIdentifiers

final class FinancialLoopUITests: XCTestCase {
    let app = XCUIApplication()

    func testArchiveManagementRestoresSameAccount() throws {
        try signIn(fresh: true)
        let baseline = homeValue()
        app.buttons["tab.accounts"].tap()
        tapVisible(app.buttons["accounts.add"])
        app.buttons["accounts.type.checking"].tap()
        let nickname = "Archive review " + UUID().uuidString.prefix(6)
        app.textFields["accounts.nickname"].tap(); app.textFields["accounts.nickname"].typeText(nickname)
        app.textFields["accounts.amount"].tap(); app.textFields["accounts.amount"].typeText("125")
        app.buttons["Done"].tap(); app.buttons["accounts.save"].tap()
        assertText("DOP 125.00")
        tapVisible(app.buttons["accounts.back"])
        let original = app.buttons.matching(NSPredicate(format: "label CONTAINS %@", nickname)).firstMatch
        XCTAssertTrue(original.waitForExistence(timeout: 10))
        let originalID = original.identifier
        tapVisible(original)
        tapVisible(app.buttons["accounts.archive"])
        XCTAssertTrue(app.buttons["Restore account"].waitForExistence(timeout: 10))
        for _ in 0..<5 { if app.buttons["accounts.back"].isHittable { break }; app.swipeDown() }
        app.buttons["accounts.back"].tap()
        XCTAssertFalse(app.buttons[originalID].exists)
        capture("archive-active-list")
        assertHome(baseline + 125)
        app.buttons["tab.accounts"].tap()
        for _ in 0..<5 { if app.buttons["accounts.manage"].isHittable { break }; app.swipeDown() }
        app.buttons["accounts.manage"].tap()
        let archived = app.buttons[originalID]
        XCTAssertTrue(archived.waitForExistence(timeout: 10))
        for _ in 0..<5 { if archived.isHittable { break }; app.swipeUp() }
        capture("archive-management")
        archived.tap()
        assertText("DOP 125.00")
        tapVisible(app.buttons["accounts.archive"])
        XCTAssertTrue(app.buttons["Archive account"].waitForExistence(timeout: 10))
        for _ in 0..<5 { if app.buttons["accounts.back"].isHittable { break }; app.swipeDown() }
        app.buttons["accounts.back"].tap()
        for _ in 0..<5 { if app.buttons["accounts.manage.back"].isHittable { break }; app.swipeDown() }
        app.buttons["accounts.manage.back"].tap()
        XCTAssertTrue(app.buttons[originalID].waitForExistence(timeout: 10))
        assertHome(baseline + 125)
    }

    func testAccountEntryKeepsUnknownAndSignedBalances() throws {
        try signIn()
        app.buttons["tab.accounts"].tap()
        XCTAssertTrue(app.buttons["accounts.add"].waitForExistence(timeout: 10))
        app.buttons["accounts.add"].tap()
        XCTAssertTrue(app.buttons["accounts.type.checking"].waitForExistence(timeout: 5))
        capture("account-entry-types")
        app.buttons["accounts.type.checking"].tap()
        XCTAssertTrue(app.buttons["accounts.type.change"].exists)
        XCTAssertFalse(app.textFields["accounts.share"].exists)
        XCTAssertFalse(app.datePickers["accounts.date"].exists)
        let nickname = "Unknown account " + UUID().uuidString.prefix(6)
        app.textFields["accounts.nickname"].tap()
        app.textFields["accounts.nickname"].typeText(nickname)
        app.buttons["accounts.save"].tap()
        XCTAssertTrue(app.staticTexts.matching(NSPredicate(format: "label CONTAINS %@", "Balance unknown")).firstMatch.waitForExistence(timeout: 10))
        capture("unknown-balance")
        record(amount: "10", note: "Spending before a known balance")
        assertText("Balance unknown")
        tapVisible(app.buttons["accounts.opening"])
        let amount = app.textFields["accounts.amount"]
        XCTAssertTrue(amount.waitForExistence(timeout: 5))
        amount.tap(); amount.typeText("25.50")
        app.buttons["accounts.amount.sign"].tap()
        XCTAssertEqual(amount.value as? String, "-25.50")
        app.buttons["Done"].tap()
        capture("signed-balance-entry")
        app.buttons["accounts.save"].tap()
        XCTAssertTrue(app.buttons["opening.coverage.yes"].waitForExistence(timeout: 10))
        capture("unknown-to-known-coverage")
        tapVisible(app.buttons["opening.coverage.yes"])
        XCTAssertTrue(app.buttons["loop.edit"].waitForExistence(timeout: 10))
        app.buttons["accounts.save"].tap()
        XCTAssertTrue(app.staticTexts.matching(NSPredicate(format: "label CONTAINS %@", "DOP -25.50")).firstMatch.waitForExistence(timeout: 10))
        app.terminate(); app.launch()
        app.buttons["tab.accounts"].tap()
        tapVisible(app.buttons.matching(NSPredicate(format: "label CONTAINS %@", nickname)).firstMatch)
        XCTAssertTrue(app.staticTexts.matching(NSPredicate(format: "label CONTAINS %@", "DOP -25.50")).firstMatch.waitForExistence(timeout: 10))
        capture("account-preserved-after-reopen")
    }

    func testCompleteFinancialLoop() throws {
        try signIn()
        let baseline = homeValue()
        app.buttons["tab.accounts"].tap()
        if app.buttons["accounts.back"].exists { app.buttons["accounts.back"].tap() }
        tapVisible(app.buttons["accounts.add"])
        app.buttons["accounts.type.checking"].tap()
        let nickname = "Daily loop " + UUID().uuidString.prefix(6)
        app.textFields["accounts.nickname"].tap(); app.textFields["accounts.nickname"].typeText(nickname)
        app.textFields["accounts.amount"].tap(); app.textFields["accounts.amount"].typeText("10000")
        app.buttons["Done"].tap(); app.buttons["accounts.save"].tap()
        assertText("DOP 10,000.00")
        record(amount: "2000", note: "Loop groceries")
        assertText("DOP 8,000.00")
        capture("expense-updated-account")
        assertHome(baseline + 8000)
        XCUIDevice.shared.press(.home); app.activate()
        assertHome(baseline + 8000)
        assertText("Loop groceries")
        capture("connected-home-after-expense")
        app.buttons["tab.accounts"].tap()
        let row = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH %@", "activity.row.")).firstMatch
        tapVisible(row)
        app.buttons["activity.correct"].tap()
        XCTAssertTrue(app.textFields["loop.amount"].waitForExistence(timeout: 5))
        let amount = app.textFields["loop.amount"]
        amount.tap(); amount.press(forDuration: 1.2)
        if app.menuItems["Select All"].waitForExistence(timeout: 1) { app.menuItems["Select All"].tap() }
        else { amount.tap(withNumberOfTaps: 3, numberOfTouches: 1) }
        amount.typeText("2500")
        let reason = app.textFields["loop.reason"]
        reason.tap(); reason.typeText("Receipt correction")
        app.buttons["Done"].tap()
        reviewAndConfirm()
        assertText("DOP 7,500.00")
        tapVisible(app.buttons["accounts.check"])
        app.textFields["loop.amount"].tap(); app.textFields["loop.amount"].typeText("7000")
        app.buttons["Done"].tap(); app.buttons["loop.review"].tap()
        XCTAssertTrue(app.buttons["loop.confirm"].waitForExistence(timeout: 10))
        capture("checked-balance-review")
        app.buttons["loop.confirm"].tap()
        assertText("DOP 7,000.00")
        record(amount: "500", note: "Already in checked balance", included: true)
        assertText("DOP 7,000.00")
        assertText("Still unexplained DOP 0.00")
        assertText("Difference DOP -500.00")
        assertHome(baseline + 7000)
        app.buttons["tab.accounts"].tap()
        capture("late-expense-not-double-counted")
        app.terminate(); app.launch(); app.buttons["tab.accounts"].tap()
        let account = app.buttons.matching(NSPredicate(format: "label CONTAINS %@", nickname)).firstMatch
        tapVisible(account)
        assertText("DOP 7,000.00")
        assertText("Already in checked balance")
        capture("financial-loop-preserved-after-reopen")
    }

    func testSpanishConnectedCheckReview() throws {
        guard ProcessInfo.processInfo.environment["ARGUS_TEST_EMAIL"] != nil else { throw XCTSkip("Requires isolated financial stack.") }
        try signIn()
        app.terminate()
        app.launchArguments = ["-AppleLanguages", "(es-419)", "-AppleLocale", "es_DO", "-appearancePreference", "dark"]
        app.launch()
        XCTAssertTrue(app.staticTexts["home.netWorth.DOP"].waitForExistence(timeout: 15))
        capture("connected-home-spanish")
        app.buttons["tab.accounts"].tap()
        let account = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH %@", "accounts.row.")).firstMatch
        tapVisible(account)
        tapVisible(app.buttons["accounts.check"])
        app.textFields["loop.amount"].tap(); app.textFields["loop.amount"].typeText("50")
        app.buttons["Listo"].tap()
        app.buttons["loop.review"].tap()
        XCTAssertTrue(app.buttons["loop.confirm"].waitForExistence(timeout: 10))
        XCTAssertFalse(app.staticTexts.matching(NSPredicate(format: "label BEGINSWITH %@", "loop.")).firstMatch.exists)
        capture("checked-balance-review-spanish")
        app.buttons["Cancelar"].tap()
    }

    func record(amount: String, note: String, included: Bool = false) {
        tapVisible(app.buttons["accounts.record"])
        XCTAssertTrue(app.textFields["loop.amount"].waitForExistence(timeout: 5))
        app.textFields["loop.amount"].tap(); app.textFields["loop.amount"].typeText(amount)
        app.textFields["loop.note"].tap(); app.textFields["loop.note"].typeText(note)
        app.buttons["Done"].tap()
        reviewAndConfirm(included: included)
    }

    func reviewAndConfirm(included: Bool = false) {
        tapVisible(app.buttons["loop.review"])
        for _ in 0..<4 {
            if app.buttons["loop.confirm"].waitForExistence(timeout: 2) { break }
            let opening = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH %@", "loop.coverage.no.opening.")).firstMatch
            let prefix = included ? "loop.coverage.yes.balance_check." : "loop.coverage.no."
            let answer = opening.exists ? opening : app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH %@", prefix)).firstMatch
            if answer.exists { tapVisible(answer) }
        }
        XCTAssertTrue(app.buttons["loop.confirm"].waitForExistence(timeout: 5))
        capture("expense-review")
        tapVisible(app.buttons["loop.confirm"])
    }

    func assertHome(_ expected: Decimal) {
        app.buttons["tab.home"].tap()
        let value = app.staticTexts["home.netWorth.DOP"]
        let predicate = NSPredicate { _, _ in
            guard value.exists else { return false }
            let exact = value.label.replacingOccurrences(of: "DOP", with: "").replacingOccurrences(of: ",", with: "").trimmingCharacters(in: .whitespaces)
            return Decimal(string: exact, locale: Locale(identifier: "en_US_POSIX")) == expected
        }
        XCTAssertEqual(XCTWaiter.wait(for: [XCTNSPredicateExpectation(predicate: predicate, object: nil)], timeout: 12), .completed)
    }

    func homeValue() -> Decimal {
        app.buttons["tab.home"].tap()
        let value = app.staticTexts["home.netWorth.DOP"]
        XCTAssertTrue(value.waitForExistence(timeout: 10))
        let exact = value.label.replacingOccurrences(of: "DOP", with: "").replacingOccurrences(of: ",", with: "").trimmingCharacters(in: .whitespaces)
        guard let parsed = Decimal(string: exact, locale: Locale(identifier: "en_US_POSIX")) else { XCTFail("Home must expose a numeric amount"); return 0 }
        return parsed
    }

    func assertText(_ value: String) {
        XCTAssertTrue(app.staticTexts.matching(NSPredicate(format: "label CONTAINS %@", value)).firstMatch.waitForExistence(timeout: 12))
    }
    func tapVisible(_ element: XCUIElement) {
        XCTAssertTrue(element.waitForExistence(timeout: 10))
        var scrolled = false
        for _ in 0..<12 {
            if element.isHittable && element.frame.midY > 115 && element.frame.midY < app.frame.height - 130 { break }
            let before = element.frame
            if element.frame.midY < 115 { app.swipeDown() } else { app.swipeUp() }
            scrolled = true
            if element.isHittable && abs(element.frame.midY - before.midY) < 2 { break }
        }
        if scrolled {
        var previous = element.frame
        var lastMovement = Date()
        let settled = NSPredicate { _, _ in
            let frame = element.frame
            if frame != previous { previous = frame; lastMovement = Date() }
            return Date().timeIntervalSince(lastMovement) > 0.5
        }
        XCTAssertEqual(XCTWaiter.wait(for: [XCTNSPredicateExpectation(predicate: settled, object: nil)], timeout: 5), .completed)
        }
        element.tap()
    }
    func signIn(fresh: Bool = false, user: String = "A") throws {
        let environment = ProcessInfo.processInfo.environment
        let suffix = user == "B" ? "_B" : ""
        guard let email = environment["ARGUS_TEST_EMAIL" + suffix], let password = environment["ARGUS_TEST_PASSWORD" + suffix] else {
            throw XCTSkip("Requires isolated synthetic API and registered identity.")
        }
        continueAfterFailure = false
        app.launchArguments = ["-AppleLanguages", "(en)", "-AppleLocale", "en_US", "-appearancePreference", "dark"]
        app.launch()
        app.buttons["header.profile"].tap()
        if fresh, app.buttons["auth.signOut"].waitForExistence(timeout: 2) { app.buttons["auth.signOut"].tap() }
        if !app.buttons["auth.signOut"].waitForExistence(timeout: 5) {
            let emailField = app.textFields["auth.email"]
            XCTAssertTrue(emailField.waitForExistence(timeout: 10))
            emailField.tap(); emailField.typeText(email)
            let passwordField = app.secureTextFields["auth.password"]
            passwordField.tap()
            UIPasteboard.general.setItems([[UTType.utf8PlainText.identifier: password]],
                                         options: [.localOnly: true, .expirationDate: Date().addingTimeInterval(60)])
            passwordField.press(forDuration: 1.2)
            let paste = app.menuItems["Paste"]
            if paste.waitForExistence(timeout: 3) { paste.tap() }
            else { app.buttons["Paste"].tap() }
            let permission = app.alerts.buttons["Allow Paste"]
            if permission.waitForExistence(timeout: 1) { permission.tap() }
            UIPasteboard.general.items = []
            app.buttons["auth.submit"].tap()
            XCTAssertTrue(app.buttons["auth.signOut"].waitForExistence(timeout: 30))
        }
        app.buttons["sheet.close"].tap()
    }

    func capture(_ name: String) {
        let screenshot = app.screenshot()
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent("argus-personal-money", isDirectory: true)
        do {
            try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
            try screenshot.pngRepresentation.write(to: directory.appendingPathComponent(name + ".png"))
        } catch { XCTFail("Could not retain screenshot evidence") }
        let attachment = XCTAttachment(screenshot: screenshot)
        attachment.name = name; attachment.lifetime = .keepAlways
        add(attachment)
    }
}
