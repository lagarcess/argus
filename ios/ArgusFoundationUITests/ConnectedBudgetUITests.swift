import XCTest

extension FinancialLoopUITests {
    func testConnectedBudgetSpendingCorrectionRefundSearchAndReopen() throws {
        try signIn()
        let stamp = String(UUID().uuidString.prefix(5))
        let checking = createMoneyAccount("Budget bank " + stamp, type: "checking", amount: "1000")
        budgetExpense(amount: "120", note: "Budget groceries " + stamp)
        let card = createMoneyAccount("Budget card " + stamp, type: "credit_card", amount: "0")
        let cash = createMoneyAccount("Budget refund cash " + stamp, type: "cash")
        let title = "Food " + stamp
        createBudget(title, accounts: [checking, card])
        openBudget(title)
        assertBudget(spent: "120.00", status: "30.00")
        capture("budget-initial-limit-and-scope")
        app.buttons["budget.close"].tap()
        openMoneyAccount(card)
        budgetExpense(amount: "80", note: "Card groceries " + stamp)
        openBudget(title)
        assertBudget(spent: "200.00", status: "50.00", over: true)
        capture("budget-over-limit-after-card-purchase")
        let contributor = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'budget.activity.' AND label CONTAINS %@", "Card groceries " + stamp)).firstMatch
        tapVisible(contributor)
        tapVisible(app.buttons["activity.correct"])
        replaceMoneyField("loop.amount", with: "60")
        fillMoneyField("loop.reason", with: "Correct the grocery receipt")
        dismissMoneyKeyboard(); reviewMoney(); tapVisible(app.buttons["loop.confirm"])
        XCTAssertTrue(app.buttons["loop.confirm"].waitForNonExistence(timeout: 15))
        app.buttons["budget.activity.back"].tap()
        assertBudget(spent: "180.00", status: "30.00", over: true)
        capture("budget-contributor-correction-propagated")
        app.buttons["budget.close"].tap()
        openMoneyAccount(cash)
        recordMoney(kind: "refund", amount: "25", note: "Budget refund " + stamp, purchase: "Card groceries " + stamp)
        assertText("Balance unknown")
        openBudget(title)
        assertBudget(spent: "155.00", status: "5.00", over: true)
        XCTAssertEqual(app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'budget.activity.'")).count, 3)
        capture("budget-cross-account-refund")
        let oldest = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'budget.activity.' AND label CONTAINS %@", "Budget groceries " + stamp)).firstMatch
        tapVisible(oldest)
        app.buttons["budget.activity.back"].tap()
        XCTAssertTrue(oldest.waitForExistence(timeout: 15))
        let savedY = oldest.frame.minY
        app.terminate(); app.launch()
        XCTAssertTrue(oldest.waitForExistence(timeout: 15))
        let restoredPosition = NSPredicate { _, _ in oldest.isHittable && abs(oldest.frame.minY - savedY) < 12 }
        XCTAssertEqual(XCTWaiter.wait(for: [XCTNSPredicateExpectation(predicate: restoredPosition, object: nil)], timeout: 15), .completed)
        capture("budget-contributor-position-restored")
        tapVisible(app.buttons["budget.edit"])
        replaceMoneyField("budget.limit", with: "160")
        dismissMoneyKeyboard(); tapVisible(app.buttons["budget.save"])
        assertBudget(spent: "155.00", status: "5.00")
        tapVisible(app.buttons["budget.remove"])
        app.buttons["budget.remove.confirm"].tap()
        XCTAssertTrue(app.buttons["budget.restore"].waitForExistence(timeout: 15))
        capture("budget-reversible-removal")
        tapVisible(app.buttons["budget.restore"])
        XCTAssertTrue(app.buttons["budget.edit"].waitForExistence(timeout: 15))
        app.buttons["budget.close"].tap()
        app.buttons["tab.search"].tap()
        let query = app.textFields["search.query"]
        XCTAssertTrue(query.waitForExistence(timeout: 10))
        query.tap(); query.typeText(title + "\n")
        let hit = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'search.row.budget.' AND label CONTAINS %@", title)).firstMatch
        tapVisible(hit)
        assertBudget(spent: "155.00", status: "5.00")
        app.terminate(); app.launch()
        assertBudget(spent: "155.00", status: "5.00")
        capture("budget-detail-restored-after-relaunch")
        app.buttons["budget.close"].tap()
        XCTAssertEqual(app.textFields["search.query"].value as? String, title)
        XCTAssertTrue(hit.waitForExistence(timeout: 15))
        capture("budget-search-origin-restored")
        tapVisible(hit)
        app.terminate()
        app.launchArguments = ["-AppleLanguages", "(es-419)", "-AppleLocale", "es_DO", "-appearancePreference", "light"]
        app.launch()
        XCTAssertTrue(app.staticTexts["budget.spent"].waitForExistence(timeout: 15))
        XCTAssertFalse(app.staticTexts.matching(NSPredicate(format: "label BEGINSWITH 'budget.'")).firstMatch.exists)
        capture("budget-spanish-detail")
        app.buttons["budget.close"].tap()
    }

    func testBudgetResponseLossRecoversExactCommandAfterRelaunch() throws {
        try requireResponseLossProxy()
        try signIn()
        let stamp = String(UUID().uuidString.prefix(5))
        let checking = createMoneyAccount("Budget retry " + stamp, type: "checking", amount: "100")
        let title = "Retry budget " + stamp
        prepareBudget(title, accounts: [checking])
        let before = try faultStatus(arm: true)
        tapVisible(app.buttons["budget.save"])
        XCTAssertTrue(app.buttons["loop.pending.retry"].waitForExistence(timeout: 30))
        XCTAssertEqual(try faultStatus(arm: false), before + 1)
        app.terminate(); app.launch()
        tapVisible(app.buttons["loop.pending.retry"])
        XCTAssertTrue(app.buttons["loop.pending.retry"].waitForNonExistence(timeout: 20))
        openBudget(title)
        assertBudget(spent: "0.00", status: "150.00")
        XCTAssertEqual(try faultStatus(arm: false), before + 1)
        capture("budget-exact-command-recovered-once")
        app.buttons["budget.close"].tap()
        XCTAssertEqual(app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'budget.row.plan.' AND label CONTAINS %@", title)).count, 1)
    }

    func budgetExpense(amount: String, note: String) {
        tapVisible(app.buttons["accounts.record"])
        tapVisible(app.buttons["loop.kind.expense"])
        fillMoneyField("loop.amount", with: amount)
        dismissMoneyKeyboard()
        tapVisible(app.buttons["loop.category"])
        app.buttons["Groceries"].tap()
        fillMoneyField("loop.note", with: note)
        dismissMoneyKeyboard(); confirmMoney()
    }

    func prepareBudget(_ title: String, accounts: [MoneyAccount]) {
        app.buttons["tab.plan"].tap()
        tapVisible(app.buttons["plan.budgets"])
        tapVisible(app.buttons["budget.add"])
        fillMoneyField("budget.name", with: title)
        fillMoneyField("budget.limit", with: "150")
        dismissMoneyKeyboard()
        tapVisible(app.buttons["budget.currency"])
        app.buttons["DOP"].tap()
        for account in accounts { tapVisible(app.switches["budget.account." + account.id]) }
        tapVisible(app.switches["budget.category.groceries"])
    }

    func createBudget(_ title: String, accounts: [MoneyAccount]) {
        prepareBudget(title, accounts: accounts)
        tapVisible(app.buttons["budget.save"])
        XCTAssertTrue(app.buttons["budget.save"].waitForNonExistence(timeout: 15))
    }

    func openBudget(_ title: String) {
        app.buttons["tab.plan"].tap()
        tapVisible(app.buttons["plan.budgets"])
        let row = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'budget.row.plan.' AND label CONTAINS %@", title)).firstMatch
        tapVisible(row)
        XCTAssertTrue(app.staticTexts["budget.spent"].waitForExistence(timeout: 15))
    }

    func assertBudget(spent: String, status: String, over: Bool = false) {
        let detail = app.otherElements["budget.detail"]
        let amount = detail.staticTexts["budget.spent"]
        let expected = NSPredicate(format: "label == %@", "DOP " + spent)
        XCTAssertEqual(XCTWaiter.wait(for: [XCTNSPredicateExpectation(predicate: expected, object: amount)], timeout: 15), .completed)
        let remaining = detail.descendants(matching: .any)["budget.remaining"]
        XCTAssertTrue(remaining.waitForExistence(timeout: 15))
        XCTAssertTrue(remaining.label.contains(status))
        XCTAssertTrue(remaining.label.contains(over ? "over budget" : "remaining"))
    }
}
