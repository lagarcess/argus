import XCTest

extension FinancialLoopUITests {
    func testConnectedPlanRecordsLinksCorrectsAndReopens() throws {
        try signIn()
        let baseline = homeValue()
        let stamp = String(UUID().uuidString.prefix(4))
        let bank = createMoneyAccount("Plan bank " + stamp, type: "checking", amount: "100")
        let bill = "Electricity " + stamp
        let income = "Commission " + stamp
        addPlanExpectation(bill, kind: "Bill", amount: "200", account: bank)
        addPlanExpectation(income, kind: "Income", amount: "500", account: bank, daysAhead: 5)
        selectPlanAccounts([bank])
        assertPlanProjected("DOP 400.00")
        XCTAssertTrue(app.staticTexts["plan.shortfall.DOP"].exists)
        capture("plan-shortfall-before-later-income")
        assertHome(baseline + 100)
        for _ in 0..<8 {
            if app.buttons["home.viewPlan"].exists { break }
            app.scrollViews["screen.home"].swipeUp()
        }
        tapVisible(app.buttons["home.viewPlan"])
        openPlanOccurrence(bill)
        tapVisible(app.buttons["plan.record"])
        XCTAssertTrue(app.textFields["loop.amount"].waitForExistence(timeout: 10))
        XCTAssertEqual(app.textFields["loop.amount"].value as? String, "200.00")
        confirmPlanMoney()
        assertPlanProjected("DOP 400.00")
        openPlanOccurrence(bill)
        assertText("Recorded")
        capture("plan-payment-linked-to-original-activity")
        tapVisible(app.buttons["plan.viewActivity"])
        replaceMoneyField("loop.amount", with: "180")
        fillMoneyField("loop.reason", with: "Correct electricity receipt")
        dismissMoneyKeyboard(); confirmPlanMoney()
        assertPlanProjected("DOP 420.00")
        openMoneyAccount(bank)
        assertText("DOP -80.00")
        recordMoney(kind: "income", amount: "450", note: income)
        assertText("DOP 370.00")
        openPlanOccurrence(income)
        tapVisible(app.buttons["plan.link"])
        let candidate = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'plan.candidate.' AND label CONTAINS %@", income)).firstMatch
        tapVisible(candidate)
        capture("plan-link-existing-income-review")
        tapVisible(app.buttons["plan.link.confirm"])
        assertPlanProjected("DOP 370.00")
        openPlanOccurrence(income)
        assertText("Recorded")
        tapVisible(app.buttons["plan.editExpectation"])
        replaceMoneyField("plan.expectation.amount", with: "600")
        dismissMoneyKeyboard(); tapVisible(app.buttons["plan.expectation.save"])
        assertPlanProjected("DOP 370.00")
        assertHome(baseline + 370)
        capture("plan-home-after-recording-and-linking")
        app.terminate(); app.launch()
        assertHome(baseline + 370)
        assertPlanProjected("DOP 370.00")
        openPlanOccurrence(bill); assertText("Recorded")
        assertText("DOP 180.00")
        capture("plan-correction-preserved-after-reopen")
        app.buttons["Close"].tap()
        openMoneyAccount(bank); assertText("DOP 370.00")
        addPlanExpectation("Weekly transport " + stamp, kind: "Bill", amount: "10", account: bank,
                           daysAhead: 7, cadence: "Every week")
        capture("plan-recurring-expectations")
        assertHome(baseline + 370)
    }

    func testPlanResponseLossRecoversOnceAfterRelaunch() throws {
        try requireResponseLossProxy()
        let stamp = String(UUID().uuidString.prefix(4))
        try signIn(fresh: true, user: "B")
        let isolated = createMoneyAccount("Plan identity B " + stamp, type: "checking", amount: "111")
        try signIn(fresh: true)
        let bank = createMoneyAccount("Recovery plan " + stamp, type: "checking", amount: "100")
        let title = "Interrupted bill " + stamp
        addPlanExpectation(title, kind: "Bill", amount: "20", account: bank)
        selectPlanAccounts([bank])
        openPlanOccurrence(title)
        tapVisible(app.buttons["plan.record"])
        reviewMoney()
        let before = try faultStatus(arm: true)
        tapVisible(app.buttons["loop.confirm"])
        XCTAssertTrue(app.staticTexts["loop.error"].waitForExistence(timeout: 30))
        XCTAssertEqual(try faultStatus(arm: false), before + 1)
        capture("plan-committed-payment-response-lost")
        app.terminate(); app.launch()
        try signIn(fresh: true, user: "B")
        openMoneyAccount(isolated); assertText("DOP 111.00")
        app.buttons["tab.plan"].tap()
        XCTAssertFalse(app.buttons["loop.pending.retry"].exists)
        XCTAssertFalse(app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'plan.occurrence.' AND label CONTAINS %@", title)).firstMatch.exists)
        capture("plan-pending-command-isolated-from-user-b")
        try signIn(fresh: true)
        app.buttons["tab.plan"].tap()
        tapVisible(app.buttons["loop.pending.retry"])
        XCTAssertTrue(app.buttons["loop.pending.retry"].waitForNonExistence(timeout: 15))
        XCTAssertEqual(try faultStatus(arm: false), before + 1)
        openPlanOccurrence(title); assertText("Recorded")
        app.buttons["Close"].tap()
        openMoneyAccount(bank); assertText("DOP 80.00")
        XCTAssertEqual(app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'activity.row.'")).count, 1)
        capture("plan-payment-recovered-once-after-reopen")
    }

    func testPlanKeepsUnknownCurrencyAndLocalizedPresentation() throws {
        try signIn()
        let stamp = String(UUID().uuidString.prefix(4))
        let unknown = createMoneyAccount("Plan dollars " + stamp, type: "checking", currency: "USD")
        addPlanExpectation("Monthly remittance " + stamp, kind: "Income", amount: "100", account: unknown,
                           cadence: "Every month", currency: "USD")
        selectPlanAccounts([unknown])
        XCTAssertFalse(app.staticTexts["plan.projected.USD"].exists)
        XCTAssertFalse(app.staticTexts["plan.projected.DOP"].exists)
        assertText("Balance unknown")
        capture("plan-unknown-dollar-balance")
        openMoneyAccount(unknown); assertText("Balance unknown")
        app.terminate()
        app.launchArguments = ["-AppleLanguages", "(es-419)", "-AppleLocale", "es_DO", "-appearancePreference", "light"]
        app.launch()
        app.buttons["tab.plan"].tap()
        XCTAssertTrue(app.buttons["plan.accounts"].waitForExistence(timeout: 15))
        XCTAssertFalse(app.staticTexts.matching(NSPredicate(format: "label BEGINSWITH 'plan.'")).firstMatch.exists)
        capture("plan-spanish-light-unknown-currency")
        app.terminate(); try signIn()
    }

    func testPlanCanRemoveArchivedAndChangedSelectedAccounts() throws {
        try signIn()
        let stamp = String(UUID().uuidString.prefix(4))
        let archived = createMoneyAccount("Archived plan " + stamp, type: "checking", amount: "100")
        selectPlanAccounts([archived])
        openMoneyAccount(archived)
        tapVisible(app.buttons["accounts.archive"])
        XCTAssertTrue(app.buttons["Restore account"].waitForExistence(timeout: 10))
        selectPlanAccounts([])
        XCTAssertFalse(app.staticTexts["plan.projected.DOP"].exists)
        let changed = createMoneyAccount("Changed plan " + stamp, type: "checking")
        selectPlanAccounts([changed])
        openMoneyAccount(changed)
        tapVisible(app.buttons["accounts.edit"])
        tapVisible(app.buttons["accounts.type"])
        app.buttons["Investments"].tap()
        tapVisible(app.buttons["accounts.save"])
        XCTAssertTrue(app.buttons["accounts.save"].waitForNonExistence(timeout: 10))
        app.buttons["tab.plan"].tap()
        tapVisible(app.buttons["plan.accounts"])
        assertText("Not a cash account. Remove it from this forecast.")
        let toggle = app.switches["plan.selection." + changed.id.uppercased()]
        tapVisible(toggle)
        capture("plan-changed-account-remains-removable")
        tapVisible(app.buttons["plan.selection.save"])
        XCTAssertTrue(app.buttons["plan.selection.save"].waitForNonExistence(timeout: 15))
        XCTAssertFalse(app.staticTexts["plan.projected.DOP"].exists)
    }

    func confirmPlanMoney() {
        reviewMoney()
        tapVisible(app.buttons["loop.confirm"])
        XCTAssertTrue(app.buttons["loop.confirm"].waitForNonExistence(timeout: 15))
    }

    func addPlanExpectation(_ title: String, kind: String, amount: String, account: MoneyAccount,
                            daysAhead: Int = 0, cadence: String = "Once", currency: String = "DOP") {
        // Connected hides the tab bar on account detail; pop before Plan.
        app.revealConnectedTabBar()
        app.buttons["tab.plan"].tap()
        tapVisible(app.buttons["plan.add"])
        tapVisible(app.buttons["plan.expectation.kind"])
        app.buttons[kind].tap()
        tapVisible(app.buttons["plan.expectation.currency"])
        app.buttons[currency].tap()
        fillMoneyField("plan.expectation.name", with: title)
        fillMoneyField("plan.expectation.amount", with: amount)
        dismissMoneyKeyboard()
        tapVisible(app.buttons["plan.expectation.account"])
        let accountOption = app.buttons[account.name]
        for _ in 0..<12 {
            if accountOption.exists && accountOption.isHittable { break }
            app.swipeUp()
        }
        XCTAssertTrue(accountOption.waitForExistence(timeout: 5))
        accountOption.tap()
        if daysAhead != 0 { choosePlanDate(daysAhead: daysAhead) }
        if cadence != "Once" {
            tapVisible(app.buttons["plan.expectation.recurrence"])
            app.buttons[cadence].tap()
        }
        capture("plan-expectation-entry")
        tapVisible(app.buttons["plan.expectation.save"])
        XCTAssertTrue(app.buttons["plan.expectation.save"].waitForNonExistence(timeout: 15))
    }

    func selectPlanAccounts(_ accounts: [MoneyAccount]) {
        app.revealConnectedTabBar()
        app.buttons["tab.plan"].tap()
        tapVisible(app.buttons["plan.accounts"])
        let ids = Set(accounts.map { "plan.selection." + $0.id.uppercased() })
        let switches = app.switches.matching(NSPredicate(format: "identifier BEGINSWITH 'plan.selection.'")).allElementsBoundByIndex
        XCTAssertFalse(switches.isEmpty)
        for item in switches {
            if (item.value as? String == "1") != ids.contains(item.identifier) { tapVisible(item) }
        }
        tapVisible(app.buttons["plan.selection.save"])
        XCTAssertTrue(app.buttons["plan.selection.save"].waitForNonExistence(timeout: 15))
    }

    func openPlanOccurrence(_ title: String) {
        app.revealConnectedTabBar()
        app.buttons["tab.plan"].tap()
        let row = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'plan.occurrence.' AND label CONTAINS %@", title)).firstMatch
        if !row.exists, app.buttons["Show more"].exists { tapVisible(app.buttons["Show more"]) }
        tapVisible(row)
    }

    func assertPlanProjected(_ value: String) {
        app.revealConnectedTabBar()
        app.buttons["tab.plan"].tap()
        let amount = app.staticTexts["plan.projected.DOP"]
        XCTAssertTrue(amount.waitForExistence(timeout: 15))
        let expected = NSPredicate(format: "label == %@", value)
        XCTAssertEqual(XCTWaiter.wait(for: [XCTNSPredicateExpectation(predicate: expected, object: amount)], timeout: 10), .completed)
    }

    func choosePlanDate(daysAhead: Int) {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(identifier: "America/Santo_Domingo")!
        let target = calendar.date(byAdding: .day, value: daysAhead, to: Date())!
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US")
        formatter.timeZone = calendar.timeZone
        formatter.dateFormat = "EEEE, MMMM d"
        tapVisible(app.datePickers["plan.expectation.date"])
        let day = app.buttons.matching(NSPredicate(format: "label CONTAINS %@", formatter.string(from: target))).firstMatch
        if !day.exists { app.buttons["Next Month"].tap() }
        XCTAssertTrue(day.waitForExistence(timeout: 5)); day.tap()
        app.navigationBars.firstMatch.coordinate(withNormalizedOffset: CGVector(dx: 0.7, dy: 0.5)).tap()
    }
}
