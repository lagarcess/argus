import XCTest

final class CuadraoReceiptUITests: XCTestCase {
    func testGroupReceiptLaterRelaunchItemsAndConfirm() {
        let app = launch()
        openGroup(app)
        tap(app, "group-add-receipt")
        tap(app, "receipt-sample")
        XCTAssertTrue(app.staticTexts["receipt-status"].waitForExistence(timeout: 5))
        shot(app, "receipt-prepared-es")
        tap(app, "receipt-later")
        XCTAssertTrue(receiptCard(app).waitForExistence(timeout: 5))
        app.terminate()
        app.launchArguments.removeAll { ["--plan-reset", "--receipt-reset"].contains($0) }
        app.launch()
        XCTAssertFalse(app.buttons["receipt-later"].exists)
        openGroup(app)
        receiptCard(app).tap()
        tap(app, "Corregir datos")
        let merchant = app.textFields["receipt-merchant"]
        merchant.tap(); merchant.typeText(" corregido")
        dismissKeyboard(app)
        tap(app, "receipt-line-0")
        let quantity = app.steppers["receipt-item-quantity"]
        XCTAssertTrue(quantity.waitForExistence(timeout: 3))
        quantity.buttons.element(boundBy: 1).tap()
        tap(app, "receipt-item-save")
        let method = app.segmentedControls["receipt-split"]
        reveal(app, method)
        method.buttons["Por consumo"].tap()
        for item in 0..<3 {
            tap(app, "receipt-assign-\(item)-0")
            tap(app, "receipt-assign-\(item)-1")
        }
        reveal(app, app.staticTexts["receipt-unassigned"])
        XCTAssertEqual(app.staticTexts["receipt-unassigned"].label, "Todos los artículos asignados")
        shot(app, "receipt-shared-items-es")
        tap(app, "receipt-confirm")
        XCTAssertEqual(app.buttons["receipt-later"].label, "Listo")
        let saved = app.staticTexts["Gasto guardado"]
        reveal(app, saved)
        XCTAssertTrue(saved.exists)
        shot(app, "receipt-confirmed-es")
        tap(app, "receipt-later")
        app.segmentedControls["group-sections"].buttons["Gastos"].tap()
        let posted = app.buttons.matching(identifier: "group-entry-recorded").element(boundBy: 0)
        reveal(app, posted); posted.tap()
        XCTAssertTrue(app.buttons["receipt-source"].waitForExistence(timeout: 5))
        XCTAssertFalse(app.buttons["receipt-confirm"].exists)
    }

    func testPersonalChatReceiptSavedAndConfirmedEnglishDark() {
        let app = launch(english: true, dark: true)
        tap(app, "cuadrao-tab-2")
        scanFromChat(app, english: true)
        tap(app, "receipt-sample")
        tap(app, "receipt-later")
        XCTAssertTrue(receiptCard(app).waitForExistence(timeout: 5))
        shot(app, "receipt-chat-card-en-dark")
        receiptCard(app).tap()
        tap(app, "receipt-account")
        app.buttons["Everyday"].tap()
        tap(app, "receipt-confirm")
        shot(app, "receipt-personal-confirmed-en-dark")
        tap(app, "receipt-later")
        app.terminate()
        app.launchArguments.removeAll { ["--plan-reset", "--receipt-reset"].contains($0) }
        app.launch()
        tap(app, "cuadrao-tab-2")
        tap(app, "chat-attach")
        tap(app, "chat-saved-receipts")
        XCTAssertTrue(receiptCard(app).waitForExistence(timeout: 5))
        receiptCard(app).tap()
        XCTAssertTrue(app.buttons["receipt-source"].waitForExistence(timeout: 5))
        XCTAssertFalse(app.buttons["receipt-confirm"].exists)
        shot(app, "receipt-personal-relaunch-en-dark")
    }

    func testGroupChatUsesSameReceiptAsPlanAndSource() {
        let app = launch(english: true)
        openGroup(app, english: true)
        tap(app, "group-open-chat")
        scanFromChat(app, english: true)
        tap(app, "receipt-sample")
        tap(app, "receipt-source")
        XCTAssertTrue(app.navigationBars["Original receipt"].waitForExistence(timeout: 3))
        shot(app, "receipt-original-source-en")
        app.buttons["Done"].tap()
        tap(app, "receipt-later")
        let id = receiptCard(app).identifier
        tap(app, "cuadrao-tab-1")
        XCTAssertTrue(app.buttons[id].waitForExistence(timeout: 5))
        app.buttons[id].tap()
        XCTAssertTrue(app.buttons["receipt-source"].waitForExistence(timeout: 3))
        shot(app, "receipt-plan-chat-same-record-en")
    }

    func testReceiptShowsYouOweWhenAnotherPersonPaid() {
        let app = launch(english: true, dark: true)
        openGroup(app, english: true)
        tap(app, "group-add-receipt")
        tap(app, "receipt-sample")
        tap(app, "receipt-payer")
        app.buttons["Ana"].tap()
        let direction = app.staticTexts["You owe"]
        reveal(app, direction)
        XCTAssertTrue(direction.exists)
        shot(app, "receipt-you-owe-en-dark")
        tap(app, "receipt-later")
    }

    func testPhotoImportKeepsOriginalWithoutInventedItems() {
        let app = launch(english: true)
        tap(app, "cuadrao-tab-2")
        scanFromChat(app, english: true)
        tap(app, "Photos")
        let photo = app.images.matching(NSPredicate(format: "label BEGINSWITH %@", "Photo,")).firstMatch
        XCTAssertTrue(photo.waitForExistence(timeout: 5), "Seed the task simulator with a fictional receipt photo before running this journey.")
        photo.tap()
        XCTAssertTrue(app.staticTexts["Total to review"].waitForExistence(timeout: 5))
        XCTAssertFalse(app.buttons["receipt-line-0"].exists)
        tap(app, "receipt-source")
        XCTAssertTrue(app.navigationBars["Original receipt"].waitForExistence(timeout: 3))
        shot(app, "receipt-import-original-en")
        app.buttons["Done"].tap()
        tap(app, "receipt-later")
        receiptCard(app).tap()
        XCTAssertTrue(app.staticTexts["Total to review"].waitForExistence(timeout: 3))
        shot(app, "receipt-import-draft-en")
    }

    private func launch(english: Bool = false, dark: Bool = false) -> XCUIApplication {
        continueAfterFailure = false
        let app = XCUIApplication()
        app.launchArguments = ["--cuadrao-design", "--home-populated", "--plan-reset", "--receipt-reset", "-cuadrao.design.appearance", dark ? "dark" : "light"] + (english ? ["--design-english"] : [])
        app.launch()
        return app
    }
    private func openGroup(_ app: XCUIApplication, english: Bool = false) {
        tap(app, "cuadrao-tab-1")
        app.segmentedControls["plan-audience"].buttons[english ? "Together" : "En grupo"].tap()
        tap(app, "group-card-trip")
    }
    private func scanFromChat(_ app: XCUIApplication, english: Bool) {
        tap(app, "chat-attach")
        app.buttons[english ? "Scan" : "Escanear"].tap()
    }
    private func receiptCard(_ app: XCUIApplication) -> XCUIElement {
        app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH %@", "receipt-card-")).firstMatch
    }
    private func tap(_ app: XCUIApplication, _ id: String) {
        let button = app.buttons[id]; reveal(app, button)
        XCTAssertTrue(button.waitForExistence(timeout: 5), id)
        XCTAssertTrue(button.isEnabled, id)
        button.tap()
    }
    private func reveal(_ app: XCUIApplication, _ element: XCUIElement) {
        for _ in 0..<12 where !element.isHittable { app.swipeUp() }
    }
    private func dismissKeyboard(_ app: XCUIApplication) {
        if app.toolbars.buttons["Listo"].exists { app.toolbars.buttons["Listo"].tap() }
        if app.toolbars.buttons["Done"].exists { app.toolbars.buttons["Done"].tap() }
    }
    private func shot(_ app: XCUIApplication, _ name: String) {
        let attachment = XCTAttachment(screenshot: app.screenshot())
        attachment.name = name; attachment.lifetime = .keepAlways; add(attachment)
    }
}
