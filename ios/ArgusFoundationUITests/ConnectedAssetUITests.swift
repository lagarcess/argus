import XCTest

extension FinancialLoopUITests {
    func testConnectedAssetEstimateShareDebtHistorySearchAndRelaunch() throws {
        try signIn()
        let stamp = String(UUID().uuidString.prefix(5))
        _ = createMoneyAccount("Asset baseline cash " + stamp, type: "checking", amount: "1000")
        let baseline = homeValue()
        let loan = createMoneyAccount("Asset loan " + stamp, type: "other_debt", amount: "1000000")
        let house = createAsset("Home " + stamp, type: "property", amount: "8000000", half: true)
        assertAssetContribution("DOP 4,000,000.00")
        XCTAssertFalse(app.staticTexts["assets.date.value"].label.isEmpty)
        XCTAssertFalse(app.buttons["accounts.record"].exists)
        capture("asset-whole-estimate-and-half-share")
        tapVisible(app.buttons["assets.details"])
        tapVisible(app.buttons["assets.debt.picker"])
        let option = app.buttons.matching(NSPredicate(format: "label CONTAINS %@ AND NOT identifier BEGINSWITH 'assets.'", loan.name)).firstMatch
        tapVisible(option)
        tapVisible(app.buttons["assets.save"])
        XCTAssertTrue(app.buttons["assets.save"].waitForNonExistence(timeout: 15))
        tapVisible(app.buttons["assets.debt.open"])
        XCTAssertTrue(app.buttons["accounts.record"].waitForExistence(timeout: 10))
        assertText("DOP -1,000,000.00")
        tapVisible(app.buttons["assets.debt.back"])
        assertAssetContribution("DOP 4,000,000.00")
        tapVisible(app.buttons["assets.update"])
        fillMoneyField("assets.amount", with: "9000000")
        fillMoneyField("assets.basis", with: "Recent manual estimate")
        dismissMoneyKeyboard()
        tapVisible(app.buttons["assets.save"])
        XCTAssertTrue(app.buttons["assets.edit"].waitForExistence(timeout: 10))
        capture("asset-estimate-review")
        tapVisible(app.buttons["assets.save"])
        XCTAssertTrue(app.buttons["assets.save"].waitForNonExistence(timeout: 15))
        assertAssetContribution("DOP 4,500,000.00")
        XCTAssertEqual(app.staticTexts["assets.basis.value"].label, "Recent manual estimate")
        tapVisible(app.buttons["assets.history"])
        let corrections = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'assets.correct.'"))
        XCTAssertEqual(corrections.count, 2)
        tapVisible(corrections.element(boundBy: 1))
        replaceMoneyField("assets.amount", with: "8100000")
        fillMoneyField("assets.basis", with: "Original estimate corrected")
        fillMoneyField("assets.reason", with: "Original amount had a typo")
        dismissMoneyKeyboard(); tapVisible(app.buttons["assets.save"])
        XCTAssertTrue(app.buttons["assets.edit"].waitForExistence(timeout: 10))
        tapVisible(app.buttons["assets.save"])
        XCTAssertTrue(app.buttons["assets.save"].waitForNonExistence(timeout: 15))
        assertAssetContribution("DOP 4,500,000.00")
        capture("asset-old-correction-preserves-latest")
        tapVisible(app.buttons["assets.details"])
        tapVisible(app.buttons["assets.share.change"]); tapVisible(app.buttons["assets.share.other"])
        replaceMoneyField("assets.share.percent", with: "25")
        dismissMoneyKeyboard(); tapVisible(app.buttons["assets.save"])
        XCTAssertTrue(app.buttons["assets.save"].waitForNonExistence(timeout: 15))
        assertAssetContribution("DOP 2,250,000.00")
        tapVisible(app.buttons["accounts.edit"])
        replaceMoneyField("accounts.nickname", with: "Updated home " + stamp)
        dismissMoneyKeyboard(); tapVisible(app.buttons["accounts.save"])
        XCTAssertTrue(app.buttons["accounts.save"].waitForNonExistence(timeout: 15))
        tapVisible(app.buttons["accounts.archive"])
        let spanish = ProcessInfo.processInfo.environment["ARGUS_TEST_LANGUAGE"] == "es-419"
        let restore = app.buttons[spanish ? "Restaurar cuenta" : "Restore account"]
        XCTAssertTrue(restore.waitForExistence(timeout: 10))
        capture("asset-archived-record-preserved")
        tapVisible(restore)
        XCTAssertTrue(app.buttons[spanish ? "Archivar cuenta" : "Archive account"].waitForExistence(timeout: 10))
        assertAssetContribution("DOP 2,250,000.00")
        XCTAssertTrue(app.buttons["assets.debt.open"].exists)
        capture("asset-restored-same-record")
        assertHome(baseline + 1250000)
        app.buttons["tab.search"].tap()
        let query = app.textFields["search.query"]
        tapVisible(query); query.typeText("Updated home " + stamp + "\n")
        tapVisible(app.buttons["search.filter.account"])
        let hit = app.buttons["search.row.account:" + house.id.lowercased()]
        let fallback = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'search.row.' AND label CONTAINS %@", "Updated home " + stamp)).firstMatch
        tapVisible(hit.exists ? hit : fallback)
        assertAssetContribution("DOP 2,250,000.00")
        tapVisible(app.buttons["assets.debt.open"])
        XCTAssertTrue(app.buttons["accounts.record"].waitForExistence(timeout: 10))
        tapVisible(app.buttons["assets.debt.back"])
        assertAssetContribution("DOP 2,250,000.00")
        scrollMoneyTop(); tapVisible(app.buttons["search.back"])
        XCTAssertEqual(query.value as? String, "Updated home " + stamp)
        capture("asset-search-origin-preserved")
        app.terminate()
        app.launchArguments = ["-AppleLanguages", "(es-419)", "-AppleLocale", "es_DO"]
        app.launch()
        app.buttons["tab.search"].tap()
        XCTAssertTrue(fallback.waitForExistence(timeout: 15))
        tapVisible(fallback); assertAssetContribution("DOP 2,250,000.00")
        XCTAssertEqual(app.buttons["assets.update"].label, "Actualizar estimado")
        XCTAssertTrue(app.staticTexts["Valor estimado del bien completo"].exists)
        XCTAssertTrue(app.buttons["Archivar cuenta"].exists)
        XCTAssertEqual(app.staticTexts["assets.basis.value"].label, "Recent manual estimate")
        tapVisible(app.buttons["assets.debt.open"])
        XCTAssertTrue(app.buttons["accounts.record"].waitForExistence(timeout: 10))
        assertText("DOP -1,000,000.00")
        tapVisible(app.buttons["assets.debt.back"])
        scrollMoneyTop(); tapVisible(app.buttons["search.back"])
        XCTAssertTrue(hit.exists)
        XCTAssertEqual(query.value as? String, "Updated home " + stamp)
        capture("asset-restored-spanish-relaunch")
    }

    func testAssetUnknownZeroVehicleAndCommittedCreateRecovery() throws {
        try signIn()
        let stamp = String(UUID().uuidString.prefix(5))
        _ = createAsset("Unknown asset " + stamp, type: "other_asset", amount: nil)
        XCTAssertTrue(app.staticTexts["assets.unknown"].exists)
        _ = createAsset("Zero vehicle " + stamp, type: "vehicle", amount: "0")
        assertAssetContribution("DOP 0.00")
        capture("asset-zero-remains-known")
        guard ProcessInfo.processInfo.environment["ARGUS_TEST_RESPONSE_LOSS_PROXY"] == "true" else { return }
        app.buttons["tab.accounts"].tap(); scrollMoneyTop(); tapVisible(app.buttons["accounts.back"])
        tapVisible(app.buttons["accounts.add"]); tapVisible(app.buttons["accounts.otherAssets"])
        tapVisible(app.buttons["accounts.type.vehicle"])
        let name = "Recovered vehicle " + stamp
        fillMoneyField("accounts.nickname", with: name); fillMoneyField("accounts.amount", with: "1000")
        dismissMoneyKeyboard()
        let before = try faultStatus(arm: true)
        tapVisible(app.buttons["accounts.save"])
        XCTAssertTrue(app.staticTexts["accounts.form.error"].waitForExistence(timeout: 30))
        XCTAssertEqual(try faultStatus(arm: false), before + 1)
        capture("asset-create-response-lost")
        app.terminate(); app.launch()
        let retry = app.buttons["loop.pending.retry"]
        XCTAssertTrue(retry.waitForExistence(timeout: 20)); tapVisible(retry)
        XCTAssertTrue(retry.waitForNonExistence(timeout: 20))
        app.buttons["tab.accounts"].tap()
        if app.buttons["accounts.back"].exists { scrollMoneyTop(); tapVisible(app.buttons["accounts.back"]) }
        let rows = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'accounts.row.' AND label CONTAINS %@", name))
        XCTAssertEqual(rows.count, 1)
        tapVisible(rows.firstMatch); assertAssetContribution("DOP 1,000.00")
        capture("asset-create-recovered-once")
    }

    func createAsset(_ name: String, type: String, amount: String?, half: Bool = false) -> MoneyAccount {
        app.buttons["tab.accounts"].tap()
        if app.buttons["accounts.back"].exists { scrollMoneyTop(); tapVisible(app.buttons["accounts.back"]) }
        tapVisible(app.buttons["accounts.add"]); tapVisible(app.buttons["accounts.otherAssets"])
        tapVisible(app.buttons["accounts.type." + type])
        fillMoneyField("accounts.nickname", with: name)
        if let amount { fillMoneyField("accounts.amount", with: amount) }
        dismissMoneyKeyboard()
        if half { tapVisible(app.buttons["assets.share.change"]); tapVisible(app.buttons["assets.share.half"]) }
        tapVisible(app.buttons["accounts.save"])
        XCTAssertTrue(app.buttons["assets.update"].waitForExistence(timeout: 15))
        scrollMoneyTop(); tapVisible(app.buttons["accounts.back"])
        let row = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'accounts.row.' AND label CONTAINS %@", name)).firstMatch
        XCTAssertTrue(row.waitForExistence(timeout: 10))
        let result = MoneyAccount(name: name, id: String(row.identifier.dropFirst("accounts.row.".count)))
        tapVisible(row)
        return result
    }

    func assertAssetContribution(_ value: String) {
        let label = app.staticTexts["assets.personal.value"]
        XCTAssertTrue(label.waitForExistence(timeout: 15))
        XCTAssertEqual(label.label, value)
    }
}
