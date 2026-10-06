import XCTest

/// A recurring expectation prepared from a recorded movement, shown in Home's
/// own 30-day Upcoming window and fulfilled once from there.
extension FinancialLoopUITests {
    func testRecurringFromMovementShowsInHomeUpcomingAndFulfilsOnce() throws {
        try signIn()
        let stamp = String(UUID().uuidString.prefix(4))
        let bank = createMoneyAccount("Recurring bank " + stamp, type: "checking", amount: "1000")
        let note = "Rent " + stamp
        recordDatedExpense(amount: "350", note: note, daysAgo: 10)
        assertText("DOP 650.00")
        inspectMoney(note)
        revealOnHome(app.buttons["activity.repeat"])
        capture("recurring-movement-detail-action")
        tapVisible(app.buttons["activity.repeat"])
        let hint = app.staticTexts["plan.expectation.fromActivity"]
        XCTAssertTrue(hint.waitForExistence(timeout: 10))
        XCTAssertEqual(app.textFields["plan.expectation.name"].value as? String, note)
        XCTAssertEqual(app.textFields["plan.expectation.amount"].value as? String, "350.00")
        XCTAssertTrue(app.buttons["plan.expectation.kind"].label.contains("Bill"))
        XCTAssertTrue(app.buttons["plan.expectation.recurrence"].label.contains("Every month"))
        XCTAssertTrue(app.buttons["plan.expectation.account"].label.contains(bank.name))
        let next = expectedNextMonthlyDate(daysAgo: 10)
        XCTAssertTrue(app.buttons["plan.expectation.monthDay"].label.contains(next.dayLabel), app.buttons["plan.expectation.monthDay"].label)
        XCTAssertTrue(datePickerShows("plan.expectation.date", next.monthDay), "the next date is \(next.monthDay)")
        capture("recurring-review-form-prefilled")
        tapVisible(app.buttons["plan.expectation.save"])
        XCTAssertTrue(app.buttons["plan.expectation.save"].waitForNonExistence(timeout: 15))
        openMoneyAccount(bank)
        assertText("DOP 650.00")
        XCTAssertEqual(movementRows(note).count, 1, "the original movement is untouched and not duplicated")
        selectPlanAccounts([bank])
        let row = homeUpcomingRow(note)
        XCTAssertTrue(row.exists, "Home Upcoming lists the planned occurrence inside the next 30 days")
        XCTAssertTrue(row.label.contains("Planned"), row.label)
        XCTAssertEqual(homeUpcomingRows(note).count, 1)
        XCTAssertFalse(app.staticTexts["home.projected.DOP"].exists, "projection details stay on Plan")
        revealOnHome(row)
        capture("home-upcoming-recurring")
        // Plan explores a longer horizon; Home's window and totals stay as they are.
        app.openPlanSurface()
        revealPlanForecastControls()
        chooseDate("plan.until", daysAhead: 60)
        assertPlanProjected("DOP -50.00")
        XCTAssertEqual(homeUpcomingRows(note).count, 1, "Home keeps its own 30-day window")
        revealOnHome(homeUpcomingRow(note))
        capture("home-upcoming-unchanged-by-plan-horizon")
        tapVisible(homeUpcomingRow(note))
        tapVisible(app.buttons["plan.record"])
        XCTAssertEqual(app.textFields["loop.amount"].value as? String, "350.00")
        confirmPlanMoney()
        XCTAssertFalse(homeUpcomingRow(note).exists, "a recorded payment leaves Upcoming and is not counted again")
        revealOnHome(app.staticTexts["home.comingUp"])
        capture("home-upcoming-after-fulfilment")
        assertPlanProjected("DOP -50.00")
        openMoneyAccount(bank)
        assertText("DOP 300.00")
        XCTAssertEqual(movementRows(note).count, 2, "one original movement plus one recorded payment")
        app.terminate(); app.launch()
        XCTAssertFalse(homeUpcomingRow(note).exists)
        openPlanOccurrence(note); assertText("Recorded")
        app.buttons["Close"].tap()
        XCTAssertFalse(homeUpcomingRow(note).exists)
        revealOnHome(app.staticTexts["home.comingUp"])
        capture("home-upcoming-preserved-after-reopen")
    }

    func testRecurringSetupResponseLossSavesOnce() throws {
        try requireResponseLossProxy()
        try signIn(fresh: true)
        retryLeftoverPendingWrite()
        let stamp = String(UUID().uuidString.prefix(4))
        let bank = createMoneyAccount("Recurring loss " + stamp, type: "checking", amount: "500")
        let note = "Gym " + stamp
        recordDatedExpense(amount: "40", note: note, daysAgo: 10)
        inspectMoney(note)
        tapVisible(app.buttons["activity.repeat"])
        XCTAssertTrue(app.staticTexts["plan.expectation.fromActivity"].waitForExistence(timeout: 10))
        let before = try faultStatus(arm: true)
        tapVisible(app.buttons["plan.expectation.save"])
        // Home's banner and the form both offer the retry; the form is what the person sees now.
        XCTAssertTrue(app.buttons.matching(identifier: "loop.pending.retry").firstMatch.waitForExistence(timeout: 30))
        XCTAssertEqual(try faultStatus(arm: false), before + 1)
        capture("recurring-save-response-lost")
        app.terminate(); app.launch()
        app.revealConnectedTabBar()
        app.buttons["tab.home"].tap()
        let retry = app.descendants(matching: .any)["screen.home"].buttons["loop.pending.retry"]
        tapVisible(retry)
        XCTAssertTrue(retry.waitForNonExistence(timeout: 20))
        XCTAssertEqual(try faultStatus(arm: false), before + 1)
        let expectations = planExpectationRows(note)
        XCTAssertTrue(expectations.firstMatch.waitForExistence(timeout: 10))
        XCTAssertEqual(expectations.count, 1, "the retried save keeps its original key")
        if app.buttons["plan.showMore"].exists { tapVisible(app.buttons["plan.showMore"]) }
        let occurrences = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'plan.occurrence.' AND label CONTAINS %@", note))
        XCTAssertTrue(occurrences.firstMatch.waitForExistence(timeout: 10))
        XCTAssertEqual(occurrences.count, 1)
        capture("recurring-saved-once-after-retry")
        openMoneyAccount(bank)
        XCTAssertEqual(movementRows(note).count, 1)
    }

    func testRecurringSetupSpanishCopy() throws {
        try signIn()
        let stamp = String(UUID().uuidString.prefix(4))
        let cash = createMoneyAccount("Recurrente " + stamp, type: "cash", amount: "100")
        let note = "Propina " + stamp
        recordMoney(kind: "income", amount: "25", note: note)
        app.terminate()
        app.launchArguments = ["-AppleLanguages", "(es-419)", "-AppleLocale", "es_DO", "-appearancePreference", "light"]
        app.launch()
        openMoneyAccount(cash)
        inspectMoney(note)
        XCTAssertEqual(app.buttons["activity.repeat"].label, "Configurar como recurrente")
        revealOnHome(app.buttons["activity.repeat"])
        capture("recurring-movement-detail-spanish")
        tapVisible(app.buttons["activity.repeat"])
        XCTAssertTrue(app.staticTexts["plan.expectation.fromActivity"].waitForExistence(timeout: 10))
        XCTAssertTrue(app.buttons["plan.expectation.kind"].label.contains("Ingreso"))
        XCTAssertTrue(app.buttons["plan.expectation.recurrence"].label.contains("Cada mes"))
        XCTAssertFalse(app.staticTexts.matching(NSPredicate(format: "label BEGINSWITH 'plan.' OR label BEGINSWITH 'loop.'")).firstMatch.exists)
        capture("recurring-review-form-spanish")
        app.buttons["Cancelar"].tap()
        XCTAssertTrue(app.buttons["Cancelar"].waitForNonExistence(timeout: 10))
        app.revealConnectedTabBar()
        app.buttons["tab.home"].tap()
        XCTAssertEqual(app.staticTexts["home.comingUp"].label, "Próximamente")
        app.terminate(); try signIn()
    }

    /// A journaled write from an interrupted earlier run blocks every new write until it is retried.
    func retryLeftoverPendingWrite() {
        app.revealConnectedTabBar()
        app.buttons["tab.home"].tap()
        let retry = app.descendants(matching: .any)["screen.home"].buttons["loop.pending.retry"]
        guard retry.waitForExistence(timeout: 3) else { return }
        tapVisible(retry)
        XCTAssertTrue(retry.waitForNonExistence(timeout: 20))
    }

    func recordDatedExpense(amount: String, note: String, daysAgo: Int) {
        tapVisible(app.buttons["accounts.record"])
        fillMoneyField("loop.amount", with: amount)
        dismissMoneyKeyboard()
        chooseDate("loop.date", daysAhead: -daysAgo, zone: .current)
        fillMoneyField("loop.note", with: note)
        dismissMoneyKeyboard()
        confirmMoney()
    }

    func movementRows(_ note: String) -> XCUIElementQuery {
        app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'activity.row.' AND label CONTAINS %@", note))
    }

    func planExpectationRows(_ title: String) -> XCUIElementQuery {
        app.revealConnectedTabBar()
        app.openPlanSurface()
        let manage = app.buttons["Manage expectations"].exists ? app.buttons["Manage expectations"] : app.staticTexts["Manage expectations"]
        tapVisible(manage)
        return app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'plan.expectation.' AND label CONTAINS %@", title))
    }

    func homeUpcomingRows(_ note: String) -> XCUIElementQuery {
        app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'home.upcoming.' AND label CONTAINS %@", note))
    }

    func homeUpcomingRow(_ note: String) -> XCUIElement {
        app.revealConnectedTabBar()
        app.buttons["tab.home"].tap()
        let row = homeUpcomingRows(note).firstMatch
        if !row.waitForExistence(timeout: 3), app.buttons["home.upcoming.more"].exists { tapVisible(app.buttons["home.upcoming.more"]) }
        _ = row.waitForExistence(timeout: 3)
        return row
    }

    func expectedNextMonthlyDate(daysAgo: Int) -> (monthDay: String, dayLabel: String) {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = .current
        let movement = calendar.date(byAdding: .day, value: -daysAgo, to: Date())!
        let anchor = calendar.component(.day, from: movement)
        let next = calendar.date(byAdding: .month, value: 1, to: movement)!
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US"); formatter.timeZone = calendar.timeZone; formatter.dateFormat = "MMM d"
        return (formatter.string(from: next), anchor == 31 ? "Last day" : String(anchor))
    }

    /// A compact date picker exposes its date through child labels, not its own value.
    func datePickerShows(_ identifier: String, _ text: String) -> Bool {
        let picker = app.datePickers[identifier]
        let shown = ([picker.value as? String ?? ""] + picker.descendants(matching: .any).allElementsBoundByIndex.map(\.label)).joined(separator: " ")
        return shown.contains(text) || picker.descendants(matching: .any).matching(NSPredicate(format: "label CONTAINS %@ OR value CONTAINS %@", text, text)).firstMatch.exists
    }

    /// Scrolls Home until the element sits inside the viewport without tapping it.
    /// Frame bounds, not `isHittable`: hidden tabs stay in the shell ZStack and their
    /// UIKit-backed views shadow XCUITest hit tests although real touches pass through.
    /// Each drag covers the remaining distance (capped) and holds before release, so there is
    /// no fling: a Home with many accounts converges instead of running out of fixed steps.
    func revealOnHome(_ element: XCUIElement) {
        XCTAssertTrue(element.waitForExistence(timeout: 10))
        let home = app.scrollViews["screen.home"]
        let top: CGFloat = 120, bottom = app.frame.height - 130
        let center = home.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5))
        for _ in 0..<40 {
            let y = element.frame.midY
            if y > top && y < bottom { return }
            let limit = home.frame.height * 0.6
            let travel = max(-limit, min(limit, (top + bottom) / 2 - y))
            center.withOffset(CGVector(dx: 0, dy: -travel / 2)).press(
                forDuration: 0.05, thenDragTo: center.withOffset(CGVector(dx: 0, dy: travel / 2)),
                withVelocity: .slow, thenHoldForDuration: 0.2)
        }
        XCTFail("\(element.identifier) stays off screen at \(element.frame)")
    }

    func chooseDate(_ identifier: String, daysAhead: Int, zone: TimeZone = TimeZone(identifier: "America/Santo_Domingo")!) {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = zone
        let target = calendar.date(byAdding: .day, value: daysAhead, to: Date())!
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US"); formatter.timeZone = zone; formatter.dateFormat = "EEEE, MMMM d"
        tapVisible(app.datePickers[identifier])
        let day = app.buttons.matching(NSPredicate(format: "label CONTAINS %@", formatter.string(from: target))).firstMatch
        // The picker opens on the selected month and animates each flip; a tap during a flip skips a month.
        for _ in 0..<3 where !day.waitForExistence(timeout: 1.5) {
            app.buttons[daysAhead < 0 ? "Previous Month" : "Next Month"].tap()
        }
        XCTAssertTrue(day.waitForExistence(timeout: 5)); day.tap()
        let dismissRegion = app.buttons["PopoverDismissRegion"]
        if dismissRegion.exists {
            dismissRegion.tap()
        } else if let bar = app.navigationBars.allElementsBoundByIndex.first(where: \.isHittable) {
            bar.coordinate(withNormalizedOffset: CGVector(dx: 0.7, dy: 0.5)).tap()
        } else {
            app.coordinate(withNormalizedOffset: CGVector(dx: 0.15, dy: 0.08)).tap()
        }
        XCTAssertTrue(day.waitForNonExistence(timeout: 5))
    }
}
