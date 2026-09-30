import XCTest

extension FinancialLoopUITests {
    func testConnectedDebtActualSplitCorrectionReturnAndRelaunch() throws {
        try signIn()
        let stamp = String(UUID().uuidString.prefix(5))
        let funding = createMoneyAccount("Debt funding " + stamp, type: "checking", amount: "2000")
        _ = createMoneyAccount("Loan " + stamp, type: "other_debt", amount: "1000")
        tapVisible(app.buttons["accounts.debt"])
        replaceMoneyField("debt.name", with: "Loan plan " + stamp)
        fillMoneyField("debt.amount", with: "500")
        dismissMoneyKeyboard(); chooseMoneyAccount("debt.source", account: funding)
        tapVisible(app.buttons["debt.save"])
        XCTAssertTrue(app.buttons["debt.save"].waitForNonExistence(timeout: 15))
        openDebt("Loan plan " + stamp)
        assertDebt("DOP -1,000.00")
        tapVisible(app.buttons["debt.record"])
        debtSplit(total: "350", principal: "300", interest: "40", fees: "10")
        reviewMoney(); tapVisible(app.buttons["loop.confirm"])
        XCTAssertTrue(app.buttons["loop.confirm"].waitForNonExistence(timeout: 15))
        assertDebt("DOP -700.00")
        capture("debt-partial-actual-payment")
        let payment = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'debt.activity.' AND identifier != 'debt.activity.back'")).firstMatch
        tapVisible(payment); tapVisible(app.buttons["activity.correct"])
        debtSplit(total: "300", principal: "250", interest: "40", fees: "10")
        fillMoneyField("loop.reason", with: "Actual receipt correction")
        dismissMoneyKeyboard(); reviewMoney(); tapVisible(app.buttons["loop.confirm"])
        XCTAssertTrue(app.buttons["loop.confirm"].waitForNonExistence(timeout: 15))
        tapVisible(app.buttons["debt.activity.back"]); assertDebt("DOP -750.00")
        tapVisible(payment); tapVisible(app.buttons["activity.return"])
        debtSplit(total: "100", principal: "80", interest: "15", fees: "5")
        reviewMoney(); tapVisible(app.buttons["loop.confirm"])
        XCTAssertTrue(app.buttons["loop.confirm"].waitForNonExistence(timeout: 15))
        tapVisible(app.buttons["debt.activity.back"]); assertDebt("DOP -830.00")
        capture("debt-return-preserves-original-payment")
        app.terminate(); app.launch()
        assertDebt("DOP -830.00")
        tapVisible(app.buttons["debt.record"])
        debtSplit(total: "300", principal: "280", interest: "15", fees: "5")
        reviewMoney(); tapVisible(app.buttons["loop.confirm"])
        XCTAssertTrue(app.buttons["loop.confirm"].waitForNonExistence(timeout: 15))
        assertDebt("DOP -550.00")
        tapVisible(app.buttons["debt.link"])
        tapVisible(app.buttons["debt.action.cancel"])
        XCTAssertTrue(app.buttons["debt.record"].isHittable)
        tapVisible(app.buttons["debt.edit"])
        replaceMoneyField("debt.name", with: "Updated loan " + stamp)
        dismissMoneyKeyboard(); tapVisible(app.buttons["debt.save"])
        XCTAssertTrue(app.buttons["debt.save"].waitForNonExistence(timeout: 15))
        tapVisible(app.buttons["debt.archive"])
        app.buttons.matching(identifier: "debt.archive.confirm").firstMatch.tap()
        XCTAssertTrue(app.buttons["debt.restore"].waitForExistence(timeout: 15))
        tapVisible(app.buttons["debt.restore"]); assertDebt("DOP -550.00")
        app.buttons["debt.close"].tap()
        verifyDebtSearch("Updated loan " + stamp, balance: "DOP -550.00")
    }

    func testCardPlanPaymentAndActualReturnKeepExistingMoneyFlow() throws {
        try signIn()
        let stamp = String(UUID().uuidString.prefix(5))
        let bank = createMoneyAccount("Card funding " + stamp, type: "checking", amount: "1000")
        _ = createMoneyAccount("Card " + stamp, type: "credit_card", amount: "400")
        tapVisible(app.buttons["accounts.debt"])
        replaceMoneyField("debt.name", with: "Card plan " + stamp)
        fillMoneyField("debt.amount", with: "100")
        dismissMoneyKeyboard(); chooseMoneyAccount("debt.source", account: bank)
        tapVisible(app.buttons["debt.save"])
        XCTAssertTrue(app.buttons["debt.save"].waitForNonExistence(timeout: 15))
        openDebt("Card plan " + stamp)
        tapVisible(app.buttons["debt.record"])
        XCTAssertFalse(app.textFields["loop.principal"].exists)
        fillMoneyField("loop.amount", with: "100"); dismissMoneyKeyboard()
        reviewMoney(); tapVisible(app.buttons["loop.confirm"])
        XCTAssertTrue(app.buttons["loop.confirm"].waitForNonExistence(timeout: 15))
        assertDebt("DOP -300.00")
        let payment = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'debt.activity.' AND identifier != 'debt.activity.back'")).firstMatch
        tapVisible(payment); tapVisible(app.buttons["activity.return"])
        XCTAssertFalse(app.textFields["loop.principal"].exists)
        fillMoneyField("loop.amount", with: "100"); dismissMoneyKeyboard()
        reviewMoney(); tapVisible(app.buttons["loop.confirm"])
        XCTAssertTrue(app.buttons["loop.confirm"].waitForNonExistence(timeout: 15))
        tapVisible(app.buttons["debt.activity.back"]); assertDebt("DOP -400.00")
        capture("card-plan-return-keeps-zero-cost-contract")
    }

    func testRetainedDebtHomeSearchSpanishAndBack() throws {
        guard let query = ProcessInfo.processInfo.environment["ARGUS_TEST_SEARCH_QUERY"] else { throw XCTSkip("Requires retained debt query") }
        try signIn()
        app.buttons["tab.home"].tap()
        let row = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'debt.row.home.' AND label CONTAINS %@", query)).firstMatch
        tapVisible(row)
        XCTAssertTrue(app.buttons["debt.close"].waitForExistence(timeout: 15))
        capture("debt-home-current-truth")
        app.buttons["debt.close"].tap()
        verifyDebtSearch(query, balance: nil)
    }

    private func debtSplit(total: String, principal: String, interest: String, fees: String) {
        for (id, amount) in [("loop.amount", total), ("loop.principal", principal), ("loop.interest", interest), ("loop.fees", fees)] { replaceMoneyField(id, with: amount) }
        dismissMoneyKeyboard()
    }
    private func openDebt(_ title: String) {
        app.buttons["tab.plan"].tap(); tapVisible(app.buttons["plan.debts"])
        let row = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'debt.row.plan.' AND label CONTAINS %@", title)).firstMatch
        tapVisible(row)
        XCTAssertTrue(app.buttons["debt.close"].waitForExistence(timeout: 15))
    }
    private func assertDebt(_ amount: String) {
        let value = app.otherElements["debt.detail"].staticTexts["debt.recorded"]
        XCTAssertTrue(value.waitForExistence(timeout: 15))
        XCTAssertEqual(XCTWaiter.wait(for: [XCTNSPredicateExpectation(predicate: NSPredicate(format: "label == %@", amount), object: value)], timeout: 15), .completed)
    }
    private func verifyDebtSearch(_ title: String, balance: String?) {
        app.buttons["tab.search"].tap()
        let query = app.textFields["search.query"]
        XCTAssertTrue(query.waitForExistence(timeout: 10)); query.tap()
        if app.buttons["search.clear"].exists { app.buttons["search.clear"].tap(); query.tap() }
        query.typeText(title + "\n")
        tapVisible(app.buttons["search.filter.debt"])
        let hit = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'search.row.debt.' AND label CONTAINS %@", title)).firstMatch
        tapVisible(hit)
        if let balance { assertDebt(balance) }
        capture("debt-search-current-detail")
        app.terminate(); app.launch()
        XCTAssertTrue(app.buttons["debt.close"].waitForExistence(timeout: 15))
        app.buttons["debt.close"].tap()
        XCTAssertTrue(app.textFields["search.query"].waitForExistence(timeout: 10))
    }
}
