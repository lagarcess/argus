import XCTest
import UIKit
import UniformTypeIdentifiers

final class FinancialLoopUITests: XCTestCase {
    private let app = XCUIApplication()

    func testAccountEntryKeepsUnknownAndSignedBalances() throws {
        let environment = ProcessInfo.processInfo.environment
        guard let email = environment["ARGUS_TEST_EMAIL"], let password = environment["ARGUS_TEST_PASSWORD"] else {
            throw XCTSkip("Requires isolated synthetic API and registered identity.")
        }
        continueAfterFailure = false
        app.launchArguments = ["-AppleLanguages", "(en)", "-AppleLocale", "en_US"]
        app.launch()
        app.buttons["header.profile"].tap()
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
        app.buttons["tab.accounts"].tap()
        XCTAssertTrue(app.buttons["accounts.add"].waitForExistence(timeout: 10))
        app.buttons["accounts.add"].tap()
        XCTAssertTrue(app.buttons["accounts.type.checking"].waitForExistence(timeout: 5))
        capture("account-entry-types")
        app.buttons["accounts.type.checking"].tap()
        XCTAssertTrue(app.buttons["accounts.type.change"].exists)
        XCTAssertFalse(app.textFields["accounts.share"].exists)
        XCTAssertFalse(app.datePickers["accounts.date"].exists)
        app.textFields["accounts.nickname"].tap()
        app.textFields["accounts.nickname"].typeText("Unknown account " + UUID().uuidString.prefix(6))
        app.buttons["accounts.save"].tap()
        XCTAssertTrue(app.staticTexts.matching(NSPredicate(format: "label CONTAINS %@", "Balance unknown")).firstMatch.waitForExistence(timeout: 10))
        capture("unknown-balance")
        app.buttons["accounts.opening"].tap()
        let amount = app.textFields["accounts.amount"]
        XCTAssertTrue(amount.waitForExistence(timeout: 5))
        amount.tap(); amount.typeText("25.50")
        app.buttons["accounts.amount.sign"].tap()
        XCTAssertEqual(amount.value as? String, "-25.50")
        app.buttons["Done"].tap()
        capture("signed-balance-entry")
        app.buttons["accounts.save"].tap()
        XCTAssertTrue(app.staticTexts["DOP -25.50"].firstMatch.waitForExistence(timeout: 10))
        app.terminate(); app.launch()
        app.buttons["tab.accounts"].tap()
        XCTAssertTrue(app.staticTexts["DOP -25.50"].firstMatch.waitForExistence(timeout: 10))
        capture("account-preserved-after-reopen")
    }

    private func capture(_ name: String) {
        let attachment = XCTAttachment(screenshot: app.screenshot())
        attachment.name = name; attachment.lifetime = .keepAlways
        add(attachment)
    }
}
