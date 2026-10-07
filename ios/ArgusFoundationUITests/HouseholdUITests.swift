import XCTest

extension FinancialLoopUITests {
    func testHouseholdDefaultOffKeepsPersonalHomeAccountsAndSearchAfterReopen() throws {
        guard ProcessInfo.processInfo.environment["ARGUS_TEST_HOUSEHOLD_SURFACE_OFF"] == "true" else {
            throw XCTSkip("Requires the runtime owner's verified default-off local API and normal synthetic sign-in.")
        }
        try signIn(fresh: true)
        for language in ["en", "es-419"] {
            app.terminate()
            app.launchArguments = ["-AppleLanguages", "(" + language + ")", "-AppleLocale", language == "en" ? "en_US" : "es_DO", "-appearancePreference", "dark"]
            app.launch()
            app.openAccountsList()
            XCTAssertTrue(app.buttons["accounts.add"].waitForExistence(timeout: 15))
            for identifier in ["household.selector", "household.add", "household.people", "household.pending.retry", "household.availability.retry", "household.management.done", "household.activity.review"] {
                XCTAssertFalse(app.buttons[identifier].exists, identifier)
            }
            XCTAssertFalse(app.staticTexts["household.accessEnded"].exists)
            capture("household-default-off-personal-home-" + language)
            tapVisible(app.buttons["tab.search"])
            XCTAssertTrue(app.textFields["search.query"].waitForExistence(timeout: 10))
            XCTAssertFalse(app.textFields["household.search.query"].exists)
            XCTAssertFalse(app.staticTexts["household.accessEnded"].exists)
            capture("household-default-off-personal-search-" + language)
        }
    }

    /// The Home "+" opens Spaces; Hogar leads to the household introduction.
    private func openHouseholdFromSpaces() {
        tapVisible(app.buttons["household.add"])
        tapVisible(app.buttons["spaces.choice.household"])
    }

    func testSpacesSheetLeadsHogarAndKeepsBusinessAndCustomDisabled() throws {
        try signIn(fresh: true, user: "A")
        completePriorHouseholdCommand()
        tapVisible(app.buttons["household.add"])
        for kind in ["household", "business", "custom"] {
            XCTAssertTrue(app.descendants(matching: .any)["spaces.choice." + kind].waitForExistence(timeout: 10), kind)
        }
        XCTAssertTrue(app.buttons["spaces.manage"].exists)
        capture("spaces-sheet-connected")
        let business = app.descendants(matching: .any)["spaces.choice.business"]
        XCTAssertTrue(business.label.contains("Coming soon") || business.label.contains("Próximamente"), business.label)
        XCTAssertFalse(app.buttons["spaces.choice.business"].exists, "Business has no backend and is not a button")
        XCTAssertFalse(app.textFields["space-name"].exists, "Business has no backend and must not open a form")
        tapVisible(app.buttons["spaces.choice.household"])
        XCTAssertTrue(app.buttons["household.intro.create"].waitForExistence(timeout: 10))
    }

    private func openHouseholdPeople() {
        openAccountsTab()
        tapVisible(app.scrollViews["screen.home"].buttons["household.people"])
        XCTAssertTrue(app.buttons["household.management.done"].waitForExistence(timeout: 10))
    }

    private func completePriorHouseholdCommand() {
        let pending = app.buttons.matching(identifier: "household.pending.retry")
        XCTAssertLessThanOrEqual(pending.count, 1, "Setup should expose only the header retry")
        guard pending.count == 1 else { return }
        let retry = pending.element(boundBy: 0)
        tapVisible(retry)
        XCTAssertTrue(retry.waitForNonExistence(timeout: 20), "Complete the previous saved command before starting this journey")
    }

    private func assertHouseholdPendingCommand(droppedBefore: Int) throws {
        let pending = app.buttons.matching(identifier: "household.pending.retry")
        let deadline = Date().addingTimeInterval(30)
        var dropped = try faultStatus(arm: false)
        while (pending.count == 0 || dropped != droppedBefore + 1) && Date() < deadline {
            if dropped > droppedBefore + 1 { break }
            Thread.sleep(forTimeInterval: 0.25)
            dropped = try faultStatus(arm: false)
        }
        XCTAssertGreaterThan(pending.count, 0)
        XCTAssertEqual(dropped, droppedBefore + 1)
    }

    private func reviewHouseholdActivity() {
        tapVisible(app.buttons["household.activity.review"])
        let confirm = app.buttons["household.activity.confirm"]
        let notIncluded = app.buttons["Not included in this balance"]
        let reviewed = XCTNSPredicateExpectation(predicate: NSPredicate { _, _ in
            confirm.exists || notIncluded.exists
        }, object: nil)
        XCTAssertEqual(XCTWaiter.wait(for: [reviewed], timeout: 15), .completed)
        if !confirm.exists && notIncluded.exists {
            tapVisible(notIncluded)
            tapVisible(app.buttons["household.activity.review"])
        }
        XCTAssertTrue(confirm.waitForExistence(timeout: 15))
    }

    private func enableHouseholdSwitch(_ control: XCUIElement) {
        XCTAssertTrue(control.waitForExistence(timeout: 10))
        XCTAssertEqual(control.value as? String, "0")
        control.coordinate(withNormalizedOffset: CGVector(dx: 0.93, dy: 0.5)).tap()
        let selected = XCTNSPredicateExpectation(predicate: NSPredicate { _, _ in control.value as? String == "1" }, object: nil)
        XCTAssertEqual(XCTWaiter.wait(for: [selected], timeout: 5), .completed)
    }

    private func openHouseholdShare(_ account: MoneyAccount) {
        let forms = app.collectionViews
        XCTAssertEqual(forms.count, 1, "People should present one account list")
        let form = forms.element(boundBy: 0)
        let row = form.buttons["household.share.account." + account.id]
        for _ in 0..<12 {
            if row.exists && row.isHittable {
                row.tap()
                XCTAssertTrue(app.buttons["household.share.confirm"].waitForExistence(timeout: 10))
                return
            }
            form.swipeUp()
        }
        XCTFail("The owner's recorded account should be reachable in People")
    }

    func testHouseholdConfirmedResponseLossCreateAndAcceptRecoverAfterRelaunch() throws {
        guard ProcessInfo.processInfo.environment["ARGUS_TEST_RESPONSE_LOSS_PROXY"] == "true",
              let endpoint = ProcessInfo.processInfo.environment["ARGUS_TEST_FAULT_URL"],
              URL(string: endpoint)?.port == 59532 else {
            throw XCTSkip("Requires the explicitly assigned Household response-loss proxy on 59532.")
        }
        try signIn(fresh: true, user: "A")
        completePriorHouseholdCommand()
        let title = "HH recovery " + String(UUID().uuidString.prefix(6))
        openHouseholdFromSpaces()
        tapVisible(app.buttons["household.intro.create"])
        fillMoneyField("household.name", with: title)
        replaceMoneyField("household.displayName", with: "Household Retry Alice")
        dismissMoneyKeyboard()
        let beforeCreate = try faultStatus(arm: true)
        tapVisible(app.buttons["household.create"])
        try assertHouseholdPendingCommand(droppedBefore: beforeCreate)
        tapVisible(app.buttons["household.management.done"])
        XCTAssertEqual(app.buttons.matching(identifier: "household.pending.retry").count, 1)
        app.terminate(); app.launch()
        let pending = app.buttons["household.pending.retry"]
        XCTAssertTrue(pending.waitForExistence(timeout: 20))
        capture("household-create-response-lost-pending-after-relaunch")
        tapVisible(pending)
        XCTAssertTrue(pending.waitForNonExistence(timeout: 20))
        XCTAssertEqual(try faultStatus(arm: false), beforeCreate + 1)
        tapVisible(app.buttons["household.selector"])
        let created = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'household.select.' AND label == %@", title))
        XCTAssertEqual(created.count, 1)
        let householdSelector = created.element(boundBy: 0).identifier
        created.element(boundBy: 0).tap()
        openHouseholdPeople()
        tapVisible(app.buttons["household.invite"])
        let link = app.staticTexts["household.invite.link"]
        XCTAssertTrue(link.waitForExistence(timeout: 15))
        let invitation = link.label
        XCTAssertTrue(invitation.hasPrefix("https://cuadrao.ai/invite#") || invitation.hasPrefix("argus-household://invite#"))
        tapVisible(app.buttons["household.management.done"])

        try signIn(fresh: true, user: "B")
        completePriorHouseholdCommand()
        openHouseholdFromSpaces()
        tapVisible(app.buttons["household.intro.join"])
        fillMoneyField("household.invite.input", with: invitation)
        dismissMoneyKeyboard(); tapVisible(app.buttons["household.invite.preview"])
        XCTAssertTrue(app.buttons["household.accept"].waitForExistence(timeout: 15))
        replaceMoneyField("household.join.displayName", with: "Household Retry Bob")
        dismissMoneyKeyboard()
        let beforeAccept = try faultStatus(arm: true)
        tapVisible(app.buttons["household.accept"])
        try assertHouseholdPendingCommand(droppedBefore: beforeAccept)
        tapVisible(app.buttons["household.management.done"])
        XCTAssertEqual(app.buttons.matching(identifier: "household.pending.retry").count, 1)
        app.terminate(); app.launch()
        XCTAssertTrue(pending.waitForExistence(timeout: 20))
        tapVisible(pending)
        XCTAssertTrue(pending.waitForNonExistence(timeout: 20))
        XCTAssertEqual(try faultStatus(arm: false), beforeAccept + 1)
        tapVisible(app.buttons["household.selector"])
        XCTAssertEqual(app.buttons.matching(identifier: householdSelector).count, 1)
        app.buttons[householdSelector].tap()
        openHouseholdPeople()
        let bob = app.staticTexts.matching(NSPredicate(format: "identifier BEGINSWITH 'household.member.' AND label == %@", "Household Retry Bob"))
        XCTAssertEqual(bob.count, 1)
        let membershipSelector = bob.element(boundBy: 0).identifier
        let memberships = app.staticTexts.matching(NSPredicate(format: "identifier BEGINSWITH 'household.member.'")).allElementsBoundByIndex
        XCTAssertEqual(Set(memberships.map(\.identifier)).count, 2)
        capture("household-accept-response-lost-recovered-once")
        tapVisible(app.buttons["household.management.done"])
        app.terminate(); app.launch(); openHouseholdPeople()
        XCTAssertTrue(app.staticTexts[membershipSelector].waitForExistence(timeout: 15))
        XCTAssertEqual(bob.count, 1)
        XCTAssertEqual(try faultStatus(arm: false), beforeAccept + 1)
        tapVisible(app.buttons["household.management.done"])
    }

    func testHouseholdTwoUsersConsentEditingRevocationAndSpanishRelaunch() throws {
        let home = app.scrollViews["screen.home"]
        let accounts = app.scrollViews["screen.home"]
        let detail = app.scrollViews["household.detail"]
        try signIn(fresh: true, user: "A")
        completePriorHouseholdCommand()
        tapVisible(app.buttons["household.personal"])
        let stamp = String(UUID().uuidString.prefix(6))
        let shared = createMoneyAccount("HH shared " + stamp, type: "checking", amount: "1000")
        let privateAccount = createMoneyAccount("HH private " + stamp, type: "checking", amount: "9000")
        openAccountsTab()
        openHouseholdFromSpaces()
        tapVisible(app.buttons["household.intro.create"])
        fillMoneyField("household.name", with: "HH native " + stamp)
        replaceMoneyField("household.displayName", with: "Household Alice")
        dismissMoneyKeyboard(); tapVisible(app.buttons["household.create"])
        XCTAssertTrue(app.buttons["household.invite"].waitForExistence(timeout: 15))
        tapVisible(app.buttons["household.invite"])
        let link = app.staticTexts["household.invite.link"]
        XCTAssertTrue(link.waitForExistence(timeout: 15))
        let invitation = link.label
        XCTAssertTrue(invitation.hasPrefix("https://cuadrao.ai/invite#") || invitation.hasPrefix("argus-household://invite#"))
        tapVisible(app.buttons["household.management.done"])
        XCTAssertFalse(home.buttons["household.account." + shared.id].exists)

        try signIn(fresh: true, user: "B")
        completePriorHouseholdCommand()
        openHouseholdFromSpaces()
        tapVisible(app.buttons["household.intro.join"])
        fillMoneyField("household.invite.input", with: invitation)
        dismissMoneyKeyboard(); tapVisible(app.buttons["household.invite.preview"])
        XCTAssertTrue(app.buttons["household.notNow"].waitForExistence(timeout: 15))
        tapVisible(app.buttons["household.notNow"])
        openHouseholdFromSpaces()
        tapVisible(app.buttons["household.intro.join"])
        fillMoneyField("household.invite.input", with: invitation)
        dismissMoneyKeyboard(); tapVisible(app.buttons["household.invite.preview"])
        replaceMoneyField("household.join.displayName", with: "Household Bob")
        dismissMoneyKeyboard(); tapVisible(app.buttons["household.accept"])
        XCTAssertTrue(app.staticTexts["Household Bob"].waitForExistence(timeout: 15))
        let leave = app.buttons["household.leave"]
        let members = app.collectionViews.element(boundBy: app.collectionViews.count - 1)
        for _ in 0..<40 where !leave.exists { members.swipeUp() }
        XCTAssertTrue(leave.waitForExistence(timeout: 5))
        tapVisible(app.buttons["household.management.done"])
        XCTAssertFalse(home.buttons["household.account." + shared.id].exists)
        capture("household-accepted-with-no-automatic-sharing")

        try signIn(fresh: true, user: "A")
        openHouseholdPeople()
        openHouseholdShare(shared)
        let memberChoices = app.switches.matching(NSPredicate(format: "identifier BEGINSWITH 'household.share.member.'"))
        XCTAssertEqual(memberChoices.count, 1, "This household has one recipient")
        let member = memberChoices.element(boundBy: 0)
        enableHouseholdSwitch(member)
        let defaultEdit = app.switches.matching(NSPredicate(format: "identifier BEGINSWITH 'household.share.edit.'"))
        XCTAssertEqual(defaultEdit.count, 1)
        XCTAssertEqual(defaultEdit.element(boundBy: 0).value as? String, "0")
        capture("household-explicit-view-only-consent")
        tapVisible(app.buttons["household.share.confirm"])
        XCTAssertTrue(app.buttons["household.share.confirm"].waitForNonExistence(timeout: 15))
        tapVisible(app.buttons["household.management.done"])

        try signIn(fresh: true, user: "B")
        openAccountsTab()
        let sharedRow = accounts.buttons["household.account." + shared.id]
        XCTAssertTrue(sharedRow.waitForExistence(timeout: 15))
        XCTAssertFalse(accounts.buttons["household.account." + privateAccount.id].exists)
        tapVisible(sharedRow)
        XCTAssertTrue(detail.staticTexts["household.detail.balance"].waitForExistence(timeout: 10))
        XCTAssertFalse(detail.buttons["household.record"].exists)
        capture("household-recipient-view-only-detail")
        app.terminate(); app.launch()
        openAccountsTab()
        XCTAssertTrue(sharedRow.waitForExistence(timeout: 15))
        capture("household-membership-and-shared-account-reopen")

        try signIn(fresh: true, user: "A")
        openHouseholdPeople()
        openHouseholdShare(shared)
        let editChoices = app.switches.matching(NSPredicate(format: "identifier BEGINSWITH 'household.share.edit.'"))
        XCTAssertEqual(editChoices.count, 1, "This household has one recipient")
        let edit = editChoices.element(boundBy: 0)
        enableHouseholdSwitch(edit)
        tapVisible(app.buttons["household.share.confirm"])
        XCTAssertTrue(app.buttons["household.share.confirm"].waitForNonExistence(timeout: 15))
        tapVisible(app.buttons["household.management.done"])

        try signIn(fresh: true, user: "B")
        try completeHouseholdEditingJourney(shared: shared, privateAccount: privateAccount, stamp: stamp)
    }

    func testHouseholdResumeEditingSearchAndWithdrawalOnPreservedFixture() throws {
        let environment = ProcessInfo.processInfo.environment
        guard let stamp = environment["ARGUS_TEST_HOUSEHOLD_RESUME_STAMP"], !stamp.isEmpty else {
            throw XCTSkip("Requires an explicitly preserved Household fixture.")
        }
        let allocation = try XCTUnwrap(environment["ARGUS_TEST_FAULT_URL"].flatMap(URL.init(string:)))
        XCTAssertEqual(allocation.host, "127.0.0.1")
        XCTAssertEqual(allocation.port, 59532)
        let householdID = try XCTUnwrap(environment["ARGUS_TEST_HOUSEHOLD_RESUME_ID"].flatMap(UUID.init(uuidString:)))
        let sharedID = try XCTUnwrap(environment["ARGUS_TEST_HOUSEHOLD_RESUME_SHARED_ID"].flatMap(UUID.init(uuidString:)))
        let privateID = try XCTUnwrap(environment["ARGUS_TEST_HOUSEHOLD_RESUME_PRIVATE_ID"].flatMap(UUID.init(uuidString:)))
        try signIn(fresh: true, user: "B")
        completePriorHouseholdCommand()
        tapVisible(app.buttons["household.selector"])
        let selected = app.buttons["household.select." + householdID.uuidString]
        XCTAssertEqual(selected.label, "HH native " + stamp)
        selected.tap()
        try completeHouseholdEditingJourney(
            shared: MoneyAccount(name: "HH shared " + stamp, id: sharedID.uuidString),
            privateAccount: MoneyAccount(name: "HH private " + stamp, id: privateID.uuidString), stamp: stamp)
    }

    private func completeHouseholdEditingJourney(shared: MoneyAccount, privateAccount: MoneyAccount, stamp: String) throws {
        let accounts = app.scrollViews["screen.home"]
        let detail = app.scrollViews["household.detail"]
        let sharedRow = accounts.buttons["household.account." + shared.id]
        openAccountsTab(); tapVisible(sharedRow)
        XCTAssertTrue(detail.staticTexts["household.detail.balance"].waitForExistence(timeout: 10))
        XCTAssertEqual(detail.staticTexts["household.detail.balance"].label, "DOP 1,000.00")
        tapVisible(detail.buttons["household.record"])
        fillMoneyField("household.activity.amount", with: "25")
        fillMoneyField("household.activity.note", with: "HH reviewed expense " + stamp)
        dismissMoneyKeyboard(); reviewHouseholdActivity()
        capture("household-shared-activity-review")
        tapVisible(app.buttons["household.activity.confirm"])
        XCTAssertTrue(app.buttons["household.activity.confirm"].waitForNonExistence(timeout: 15))
        tapVisible(sharedRow)
        XCTAssertTrue(detail.staticTexts["household.detail.balance"].waitForExistence(timeout: 10))
        XCTAssertEqual(detail.staticTexts["household.detail.balance"].label, "DOP 975.00")
        let corrections = detail.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'household.correct.'"))
        XCTAssertEqual(corrections.count, 1, "This new fixture has one correctable expense")
        let correct = corrections.element(boundBy: 0)
        let activityID = String(correct.identifier.dropFirst("household.correct.".count))
        tapVisible(correct)
        replaceMoneyField("household.activity.amount", with: "20")
        fillMoneyField("household.activity.reason", with: "Corrected receipt amount")
        dismissMoneyKeyboard(); reviewHouseholdActivity()
        tapVisible(app.buttons["household.activity.confirm"])
        XCTAssertTrue(app.buttons["household.activity.confirm"].waitForNonExistence(timeout: 15))
        tapVisible(sharedRow)
        XCTAssertTrue(detail.staticTexts["household.detail.balance"].waitForExistence(timeout: 10))
        XCTAssertEqual(detail.staticTexts["household.detail.balance"].label, "DOP 980.00")
        capture("household-editor-correction-preserves-canonical-account")
        tapVisible(detail.buttons["household.back"])
        app.revealConnectedTabBar()
        app.buttons["tab.search"].tap()
        let searchField = app.textFields["household.search.query"]
        tapVisible(searchField); searchField.typeText("HH reviewed expense " + stamp + "\n")
        let hit = app.buttons["household.search." + activityID]
        XCTAssertTrue(hit.waitForExistence(timeout: 15))
        tapVisible(hit)
        XCTAssertTrue(detail.staticTexts["Selected search result"].waitForExistence(timeout: 15))
        XCTAssertTrue(detail.descendants(matching: .any)["household.activity." + activityID].exists)
        capture("household-search-shared-activity")
        tapVisible(detail.buttons["household.back"])
        XCTAssertTrue(hit.waitForExistence(timeout: 10))
        XCTAssertEqual(searchField.value as? String, "HH reviewed expense " + stamp)
        app.terminate(); app.launchArguments = ["-AppleLanguages", "(es-419)", "-AppleLocale", "es_DO"]
        app.launch(); openAccountsTab()
        XCTAssertTrue(sharedRow.waitForExistence(timeout: 15))
        tapVisible(sharedRow)
        XCTAssertEqual(detail.buttons["household.record"].label, "Registrar movimiento")
        capture("household-spanish-shared-detail")

        try signIn(fresh: true, user: "A")
        openHouseholdPeople()
        openHouseholdShare(shared)
        tapVisible(app.buttons["household.share.withdraw"])
        XCTAssertTrue(app.buttons["household.share.withdraw"].waitForNonExistence(timeout: 15))
        tapVisible(app.buttons["household.management.done"])
        try signIn(fresh: true, user: "B")
        openAccountsTab()
        XCTAssertTrue(accounts.buttons["household.shareAccounts"].waitForExistence(timeout: 15))
        XCTAssertFalse(sharedRow.exists)
        XCTAssertFalse(accounts.buttons["household.account." + privateAccount.id].exists)
        capture("household-revoked-account-absent-after-relaunch")
    }
}
