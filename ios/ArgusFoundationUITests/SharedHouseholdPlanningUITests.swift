import XCTest

extension FinancialLoopUITests {
    func testSharedPlanningThreeRegisteredIdentitiesAndSpanishRelaunch() throws {
        let environment = ProcessInfo.processInfo.environment
        guard let value = environment["ARGUS_TEST_SHARED_PLAN_HOUSEHOLD"],
              let household = UUID(uuidString: value),
              let ownerID = environment["ARGUS_TEST_SHARED_PLAN_ACCOUNT_A"].flatMap(UUID.init(uuidString:)),
              let recipientID = environment["ARGUS_TEST_SHARED_PLAN_ACCOUNT_B"].flatMap(UUID.init(uuidString:)),
              let fault = environment["ARGUS_TEST_FAULT_URL"].flatMap(URL.init(string:)),
              fault.port == 59762 else {
            throw XCTSkip("Requires the assigned three-user disposable shared-plan scene.")
        }
        let selection = "household.select." + household.uuidString
        let ownerAccount = ownerID.uuidString
        let recipientAccount = recipientID.uuidString
        for (user, suffix, own, hidden) in [
            ("A", "", ownerAccount, recipientAccount),
            ("B", "_B", recipientAccount, ownerAccount),
            ("C", "_C", "", ownerAccount),
        ] {
            try signIn(fresh: true, user: user)
            let email = try XCTUnwrap(environment["ARGUS_TEST_EMAIL" + suffix])
            app.openProfileSurface()
            let identity = app.descendants(matching: .any)["auth.identity"]
            XCTAssertTrue(identity.waitForExistence(timeout: 10))
            XCTAssertTrue(identity.label.contains(email), "Native identity must match its separate registered user")
            app.openAccountsList()
            tapVisible(app.buttons["household.personal"])
            XCTAssertTrue(app.buttons["accounts.add"].waitForExistence(timeout: 15))
            XCTAssertFalse(app.buttons["accounts.row." + hidden].exists)
            if !own.isEmpty {
                XCTAssertTrue(app.buttons["accounts.row." + own].waitForExistence(timeout: 15))
            } else {
                XCTAssertFalse(app.buttons["accounts.row." + recipientAccount].exists)
            }
            tapVisible(app.buttons["household.selector"])
            if user == "C" {
                XCTAssertFalse(app.buttons[selection].exists)
                XCUIDevice.shared.press(.home)
                app.activate()
            } else {
                XCTAssertTrue(app.buttons[selection].waitForExistence(timeout: 10))
                app.buttons[selection].tap()
                tapVisible(app.buttons["tab.plan"])
                XCTAssertTrue(app.buttons["sharedPlan.add"].waitForExistence(timeout: 15))
                app.terminate()
                app.launchArguments = ["-AppleLanguages", "(es-419)", "-AppleLocale", "es_DO", "-appearancePreference", "light"]
                app.launch()
                tapVisible(app.buttons["tab.plan"])
                XCTAssertTrue(app.buttons["sharedPlan.add"].waitForExistence(timeout: 15))
                capture("shared-plan-scope-reopened-spanish-" + user)
            }
        }
    }
}


extension FinancialLoopUITests {
    private func sharedEnvironment(_ key: String) throws -> String {
        try XCTUnwrap(ProcessInfo.processInfo.environment["ARGUS_TEST_SHARED_PLAN_" + key])
    }

    private func selectSharedPlanSpace() throws {
        app.openAccountsList()
        tapVisible(app.buttons["household.selector"])
        tapVisible(app.buttons["household.select." + (try sharedEnvironment("HOUSEHOLD"))])
        tapVisible(app.buttons["tab.plan"])
        XCTAssertTrue(app.buttons["sharedPlan.add"].waitForExistence(timeout: 20))
    }

    private func sharedPicker(_ id: String, label: String) {
        revealSharedControl(app.buttons[id]); tapVisible(app.buttons[id])
        let option = app.buttons.matching(NSPredicate(format: "label == %@ AND identifier != %@", label, id)).firstMatch
        XCTAssertTrue(option.waitForExistence(timeout: 5), "Option " + label)
        option.tap()
    }

    private func sharedToggle(_ id: String) {
        let control = app.switches[id]
        revealSharedControl(control)
        tapVisible(control)
        if control.value as? String == "0" {
            control.coordinate(withNormalizedOffset: CGVector(dx: 0.93, dy: 0.5)).tap()
        }
        XCTAssertEqual(control.value as? String, "1")
    }

    private func revealSharedControl(_ control: XCUIElement) {
        // Form creates rows lazily. Scroll the real form before asking its
        // offscreen row to exist, then let the ordinary helper settle/tap it.
        for direction in [true, false] {
            for _ in 0..<15 {
                if control.exists { return }
                if direction { app.swipeUp() } else { app.swipeDown() }
            }
        }
        XCTAssertTrue(control.exists, "Shared form control should be reachable")
    }

    private func createNativeSharedPlan(kind: String, name: String) throws -> String {
        tapVisible(app.buttons["sharedPlan.add"])
        tapVisible(app.buttons["sharedPlan.create"])
        XCTAssertTrue(app.textFields["sharedPlan.name"].waitForExistence(timeout: 15))
        if kind != "budget" { sharedPicker("sharedPlan.kind", label: kind.capitalized) }
        fillMoneyField("sharedPlan.name", with: name)
        fillMoneyField("sharedPlan.amount", with: kind == "bill" || kind == "debt" ? "50" : "100")
        dismissMoneyKeyboard()
        sharedPicker("sharedPlan.currency", label: "DOP")
        if kind == "budget" {
            sharedToggle("sharedPlan.account." + (try sharedEnvironment("ACCOUNT_A")))
        } else {
            if kind == "goal" {
                sharedToggle("sharedPlan.hasContribution")
                fillMoneyField("sharedPlan.plannedContribution", with: "10")
                dismissMoneyKeyboard()
            }
            sharedPicker("sharedPlan.source", label: try sharedEnvironment("ACCOUNT_A_NAME"))
            if kind == "goal" || kind == "debt" {
                sharedPicker("sharedPlan.destination", label: try sharedEnvironment(kind == "goal" ? "ACCOUNT_A_SAVINGS_NAME" : "ACCOUNT_A_CARD_NAME"))
            }
            sharedPicker("sharedPlan.cadence", label: "Once")
        }
        let a = try sharedEnvironment("MEMBERSHIP_A")
        let b = try sharedEnvironment("MEMBERSHIP_B")
        sharedToggle("sharedPlan.member." + b)
        XCTAssertEqual(app.switches["sharedPlan.permission." + b].value as? String, "0", "View-only is the default")
        if kind == "bill" { sharedToggle("sharedPlan.permission." + b) }
        revealSharedControl(app.textFields["sharedPlan.responsibility." + a])
        fillMoneyField("sharedPlan.responsibility." + a, with: kind == "bill" || kind == "debt" ? "35" : "70")
        dismissMoneyKeyboard()
        revealSharedControl(app.textFields["sharedPlan.responsibility." + b])
        fillMoneyField("sharedPlan.responsibility." + b, with: kind == "bill" || kind == "debt" ? "15" : "30")
        dismissMoneyKeyboard()
        capture("shared-plan-create-" + kind)
        revealSharedControl(app.buttons["sharedPlan.confirm"])
        tapVisible(app.buttons["sharedPlan.confirm"])
        XCTAssertTrue(app.buttons["sharedPlan.confirm"].waitForNonExistence(timeout: 20), "Shared definition should persist")
        let row = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH %@ AND label CONTAINS %@", "sharedPlan.row." + kind + ".", name)).firstMatch
        XCTAssertTrue(row.waitForExistence(timeout: 20))
        let id = row.identifier
        tapVisible(row)
        XCTAssertEqual(app.staticTexts["sharedPlan.detail.name"].label, name)
        return id
    }

    private func recordNativeSharedContribution(kind: String, amount: String, privateNote: String, actor: String = "A") throws {
        try prepareNativeSharedContribution(kind: kind, amount: amount, privateNote: privateNote, actor: actor)
        confirmNativeSharedContribution()
    }

    private func prepareNativeSharedContribution(kind: String, amount: String, privateNote: String, actor: String = "A") throws {
        tapVisible(app.buttons["sharedPlan.record"])
        XCTAssertTrue(app.textFields["sharedPlan.contribution.amount"].waitForExistence(timeout: 15))
        if kind == "goal" || kind == "debt" {
            sharedPicker("sharedPlan.contribution.kind", label: kind == "goal" ? "Transfer" : "Card payment")
            sharedPicker("sharedPlan.contribution.source", label: try sharedEnvironment("ACCOUNT_" + actor + "_NAME"))
            sharedPicker("sharedPlan.contribution.destination", label: try sharedEnvironment(kind == "goal" ? "ACCOUNT_A_SAVINGS_NAME" : "ACCOUNT_A_CARD_NAME"))
        } else {
            sharedPicker("sharedPlan.contribution.account", label: try sharedEnvironment("ACCOUNT_" + actor + "_NAME"))
        }
        if kind == "bill" || kind == "debt" || kind == "goal" {
            let format = DateFormatter(); format.locale = Locale(identifier: "en_US_POSIX"); format.dateFormat = "yyyy-MM-dd"
            sharedPicker("sharedPlan.contribution.occurrence", label: format.string(from: Date()))
        }
        fillMoneyField("sharedPlan.contribution.amount", with: amount)
        dismissMoneyKeyboard()
        fillMoneyField("sharedPlan.contribution.note", with: privateNote)
        dismissMoneyKeyboard()
    }

    private func reviewNativeSharedContribution() {
        tapVisible(app.buttons["sharedPlan.contribution.review"])
        for _ in 0..<12 {
            if app.buttons["sharedPlan.contribution.confirm"].waitForExistence(timeout: 1) { break }
            let answer = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'sharedPlan.coverage.no.'")).firstMatch
            if answer.exists { tapVisible(answer) }
        }
        XCTAssertTrue(app.buttons["sharedPlan.contribution.confirm"].waitForExistence(timeout: 15))
    }

    private func confirmNativeSharedContribution() {
        reviewNativeSharedContribution()
        tapVisible(app.buttons["sharedPlan.contribution.confirm"])
        XCTAssertTrue(app.buttons["sharedPlan.contribution.confirm"].waitForNonExistence(timeout: 20))
        XCTAssertTrue(app.staticTexts["sharedPlan.detail.name"].waitForExistence(timeout: 15))
    }

    private func sharedFaultStatus(arm: Bool) throws -> Int {
        let url = try XCTUnwrap(ProcessInfo.processInfo.environment["ARGUS_TEST_FAULT_URL"].flatMap(URL.init(string:)))
        guard url.host == "127.0.0.1", url.port == 59762, url.path == "/__fault" else {
            throw XCTSkip("Requires the assigned loopback response-loss helper59762.")
        }
        var request = URLRequest(url: url); request.httpMethod = arm ? "POST" : "GET"
        let done = DispatchSemaphore(value: 0)
        var result: Result<Int, Error>?
        URLSession.shared.dataTask(with: request) { data, _, error in
            defer { done.signal() }
            do {
                if let error { throw error }
                let object = try JSONSerialization.jsonObject(with: XCTUnwrap(data)) as? [String: Any]
                result = .success(try XCTUnwrap(object?["dropped"] as? Int))
            } catch { result = .failure(error) }
        }.resume()
        XCTAssertEqual(done.wait(timeout: .now() + 10), .success)
        return try XCTUnwrap(result).get()
    }

    func testSharedPlanningCommittedResponseLossKeepsOneContribution() throws {
        guard ProcessInfo.processInfo.environment["ARGUS_TEST_RESPONSE_LOSS_PROXY"] == "true" else {
            throw XCTSkip("Requires the assigned response-loss proxy and isolated app configuration.")
        }
        try signIn(fresh: true, user: "A"); try selectSharedPlanSpace()
        let name = "Native saved retry " + UUID().uuidString.prefix(6)
        let row = try createNativeSharedPlan(kind: "budget", name: String(name))
        try prepareNativeSharedContribution(kind: "budget", amount: "7", privateNote: "Private retry source")
        reviewNativeSharedContribution()
        let before = try sharedFaultStatus(arm: true)
        tapVisible(app.buttons["sharedPlan.contribution.confirm"])
        let responseLost = XCTNSPredicateExpectation(predicate: NSPredicate { _, _ in
            (try? self.sharedFaultStatus(arm: false)) == before + 1 && self.app.buttons["Cancel"].isEnabled
        }, object: nil)
        XCTAssertEqual(XCTWaiter.wait(for: [responseLost], timeout: 30), .completed)
        app.buttons["Cancel"].tap()
        let pending = app.buttons["household.pending.retry"]
        XCTAssertTrue(pending.waitForExistence(timeout: 30))
        XCTAssertEqual(try sharedFaultStatus(arm: false), before + 1, "Failure must occur after upstream commit")
        app.terminate(); app.launch()
        XCTAssertTrue(pending.waitForExistence(timeout: 20))
        capture("shared-contribution-response-lost-journal-reopened")
        tapVisible(pending)
        XCTAssertTrue(pending.waitForNonExistence(timeout: 20))
        XCTAssertEqual(try sharedFaultStatus(arm: false), before + 1)
        tapVisible(app.buttons["tab.plan"]); tapVisible(app.buttons[row])
        assertText("DOP 7.00")
        let originals = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'sharedPlan.original.'"))
        revealSharedControl(originals.firstMatch)
        XCTAssertEqual(originals.count, 1, "Retry must retain one canonical contribution")
        capture("shared-contribution-exact-retry-one-result")
    }

    func testSharedPlanningFourKindsPrivateContributionsCorrectionsAndReopen() throws {
        _ = try sharedEnvironment("HOUSEHOLD")
        try signIn(fresh: true, user: "A")
        try selectSharedPlanSpace()
        let stamp = String(UUID().uuidString.prefix(6))
        var rows = [String: String]()
        var names = [String: String]()
        for kind in ["budget", "bill", "goal", "debt"] {
            let name = "Native household " + kind + " " + stamp
            names[kind] = name
            rows[kind] = try createNativeSharedPlan(kind: kind, name: name)
            if kind == "goal" { assertText("DOP 10.00") }
            try recordNativeSharedContribution(kind: kind, amount: "20", privateNote: "Private source A " + kind + " " + stamp)
            assertText("DOP 20.00")
            capture("shared-plan-recorded-" + kind)
            if kind == "budget" {
                let correct = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'sharedPlan.correct.'")).firstMatch
                tapVisible(correct)
                replaceMoneyField("sharedPlan.contribution.amount", with: "25")
                fillMoneyField("sharedPlan.contribution.reason", with: "Receipt checked")
                dismissMoneyKeyboard(); confirmNativeSharedContribution()
                assertText("DOP 25.00")
                tapVisible(app.buttons["sharedPlan.archive"])
                XCTAssertTrue(app.buttons["sharedPlan.restore"].waitForExistence(timeout: 20))
                capture("shared-budget-archived")
                tapVisible(app.buttons["sharedPlan.restore"])
                XCTAssertTrue(app.buttons["sharedPlan.record"].waitForExistence(timeout: 20))
            }
            tapVisible(app.buttons["sharedPlan.back"])
        }
        tapVisible(app.buttons["tab.home"])
        XCTAssertTrue(app.buttons[try XCTUnwrap(rows["budget"])].waitForExistence(timeout: 20))
        capture("shared-plan-connected-home")
        app.terminate(); app.launch()
        tapVisible(app.buttons["tab.plan"])
        for row in rows.values { XCTAssertTrue(app.buttons[row].waitForExistence(timeout: 20)) }
        capture("shared-four-kinds-reopened")

        try signIn(fresh: true, user: "B")
        try selectSharedPlanSpace()
        tapVisible(app.buttons[try XCTUnwrap(rows["budget"])])
        XCTAssertFalse(app.buttons["sharedPlan.edit"].exists)
        XCTAssertFalse(app.buttons["sharedPlan.archive"].exists)
        XCTAssertFalse(app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'sharedPlan.correct.'")).firstMatch.exists)
        XCTAssertFalse(app.staticTexts.matching(NSPredicate(format: "label CONTAINS %@", "Private source A")).firstMatch.exists)
        XCTAssertFalse(app.staticTexts.matching(NSPredicate(format: "label CONTAINS %@", try sharedEnvironment("ACCOUNT_A_NAME"))).firstMatch.exists)
        try recordNativeSharedContribution(kind: "budget", amount: "10", privateNote: "Private source B " + stamp, actor: "B")
        assertText("DOP 35.00")
        let original = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'sharedPlan.original.'")).firstMatch
        tapVisible(original)
        XCTAssertTrue(app.buttons["sharedPlan.original.correct"].waitForExistence(timeout: 15))
        assertText("Private source B " + stamp)
        capture("shared-own-original-inspection")
        tapVisible(app.buttons["sharedPlan.original.correct"])
        replaceMoneyField("sharedPlan.contribution.amount", with: "15")
        fillMoneyField("sharedPlan.contribution.reason", with: "My receipt correction")
        dismissMoneyKeyboard(); confirmNativeSharedContribution()
        assertText("DOP 40.00")
        capture("shared-view-only-own-correction")
        tapVisible(app.buttons["sharedPlan.back"])
        tapVisible(app.buttons[try XCTUnwrap(rows["bill"])])
        XCTAssertTrue(app.buttons["sharedPlan.edit"].waitForExistence(timeout: 15), "Explicit plan editing does not grant private source access")
        tapVisible(app.buttons["sharedPlan.edit"])
        replaceMoneyField("sharedPlan.amount", with: "60")
        dismissMoneyKeyboard(); tapVisible(app.buttons["sharedPlan.confirm"])
        XCTAssertTrue(app.buttons["sharedPlan.confirm"].waitForNonExistence(timeout: 20))
        assertText("DOP 60.00")
        XCTAssertFalse(app.staticTexts.matching(NSPredicate(format: "label CONTAINS %@", try sharedEnvironment("ACCOUNT_A_NAME"))).firstMatch.exists)
        capture("shared-explicit-editor-safe-bill")
        tapVisible(app.buttons["sharedPlan.back"])
        tapVisible(app.buttons["tab.search"])
        let query = app.textFields["household.search.query"]
        XCTAssertTrue(query.waitForExistence(timeout: 15))
        query.tap(); query.typeText(try XCTUnwrap(names["budget"]) + "\n")
        let result = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'household.search.' AND label CONTAINS %@", try XCTUnwrap(names["budget"])) ).firstMatch
        tapVisible(result)
        XCTAssertTrue(app.staticTexts["sharedPlan.detail.name"].waitForExistence(timeout: 15))
        assertText("DOP 40.00")
        tapVisible(app.buttons["sharedPlan.back"])
        XCTAssertEqual(app.textFields["household.search.query"].value as? String, try XCTUnwrap(names["budget"]))
        capture("shared-search-return-preserved")
        app.terminate()
        app.launchArguments = ["-AppleLanguages", "(es-419)", "-AppleLocale", "es_DO", "-appearancePreference", "light"]
        app.launch(); tapVisible(app.buttons["tab.plan"])
        tapVisible(app.buttons[try XCTUnwrap(rows["budget"])])
        assertText("DOP 40.00")
        XCTAssertFalse(app.staticTexts.matching(NSPredicate(format: "label BEGINSWITH 'sharedPlan.'")).firstMatch.exists)
        capture("shared-progress-spanish-reopened")
        let summary: [String: Any] = ["stamp": stamp, "rows": rows, "names": names,
            "expected_minor": ["budget_spent": "4000", "bill_agreed": "6000", "bill_paid": "2000", "goal_backed": "2000", "debt_paid": "2000"],
            "scope": "Native four-kind recorded journey; server privacy/retry/departure proof accompanies this evidence"]
        let attachment = XCTAttachment(data: try JSONSerialization.data(withJSONObject: summary, options: [.sortedKeys, .prettyPrinted]), uniformTypeIdentifier: "public.json")
        attachment.name = "shared-plan-native-scene"; attachment.lifetime = .keepAlways; add(attachment)
    }
}
