import XCTest

/// Shared navigation for tip FoundationShell and Connected Cuadrao chrome.
extension XCUIApplication {
    var usesConnectedChrome: Bool {
        buttons["cuadrao.welcome.signin"].exists
            || buttons["cuadrao.welcome.signup"].exists
            || buttons["cuadrao.signin.emailChoice"].exists
            || buttons["cuadrao.signup.email"].exists
            // Signed-in Connected: tip Accounts tab is absent; profile is a tab, not a sheet.
            || (buttons["tab.home"].exists && buttons["header.profile"].exists && !buttons["tab.accounts"].exists)
    }

    /// Connected hides `CuadraoNavigationBar` while Home owns a pushed account detail.
    func revealConnectedTabBar() {
        for _ in 0..<6 {
            if buttons["tab.home"].exists { return }
            if buttons["accounts.back"].waitForExistence(timeout: 1) {
                buttons["accounts.back"].tap()
                continue
            }
            if buttons["activity.back"].waitForExistence(timeout: 1) {
                buttons["activity.back"].tap()
                continue
            }
            if buttons["household.back"].waitForExistence(timeout: 1) {
                buttons["household.back"].tap()
                continue
            }
            if buttons["accounts.manage.back"].waitForExistence(timeout: 1) {
                buttons["accounts.manage.back"].tap()
                continue
            }
            if buttons["sheet.close"].waitForExistence(timeout: 1) {
                buttons["sheet.close"].tap()
                continue
            }
            break
        }
    }

    /// Accounts live on Home in Connected; tip keeps a dedicated Accounts tab.
    func openAccountsList() {
        revealConnectedTabBar()
        if buttons["tab.accounts"].waitForExistence(timeout: 2) {
            buttons["tab.accounts"].tap()
        } else {
            XCTAssertTrue(buttons["tab.home"].waitForExistence(timeout: 10))
            buttons["tab.home"].tap()
        }
        if buttons["accounts.back"].waitForExistence(timeout: 1) {
            buttons["accounts.back"].tap()
        }
    }

    /// Signed-out Connected welcome → email form; tip uses header.profile sheet.
    func openSignedOutAuthEntry(createAccount: Bool = false) {
        if buttons["cuadrao.welcome.signin"].waitForExistence(timeout: 3)
            || buttons["cuadrao.welcome.signup"].exists {
            if createAccount {
                buttons["cuadrao.welcome.signup"].tap()
                XCTAssertTrue(buttons["cuadrao.signup.email"].waitForExistence(timeout: 10))
                buttons["cuadrao.signup.email"].tap()
            } else {
                buttons["cuadrao.welcome.signin"].tap()
                XCTAssertTrue(buttons["cuadrao.signin.emailChoice"].waitForExistence(timeout: 10))
                buttons["cuadrao.signin.emailChoice"].tap()
            }
            return
        }
        XCTAssertTrue(buttons["header.profile"].waitForExistence(timeout: 10))
        buttons["header.profile"].tap()
        if createAccount, buttons["auth.createAccount"].waitForExistence(timeout: 3) {
            buttons["auth.createAccount"].tap()
        }
    }

    func openProfileSurface() {
        if buttons["header.profile"].waitForExistence(timeout: 3) {
            buttons["header.profile"].tap()
            return
        }
        openSignedOutAuthEntry()
    }
}

extension FinancialLoopUITests {
    func openAccountsTab() {
        app.openAccountsList()
    }
}
