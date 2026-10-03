import XCTest

final class CuadraoHistoryDesignUITests: XCTestCase {
    func testRecentsActionsAndRecovery() {
        continueAfterFailure = false
        let app = XCUIApplication.cuadraoPreview(); app.launch()
        app.buttons["tab.argus"].tap()
        app.buttons["chat-history"].tap()
        let row = app.buttons["history-row-chat-cd"]
        XCTAssertFalse(app.buttons["history-menu-chat-cd"].exists)
        XCTAssertTrue(row.waitForExistence(timeout: 4))
        capture(app, "recents-spanish")
        XCTAssertTrue((row.value as? String ?? "").contains("Hoy"))
        XCTAssertTrue((app.buttons["history-row-chat-spending"].value as? String ?? "").contains("Ayer"))
        row.swipeRight()
        capture(app, "recents-pin-gesture")
        app.buttons["Fijar"].tap()
        XCTAssertTrue(app.staticTexts["Fijados"].exists)
        row.press(forDuration: 0.8)
        capture(app, "recents-menu")
        app.buttons["Marcar como no leído"].tap()
        XCTAssertTrue((row.value as? String ?? "").contains("No leído"))
        row.press(forDuration: 0.8); app.buttons["Cambiar nombre"].tap()
        let field = app.alerts.textFields.firstMatch
        XCTAssertTrue(field.waitForExistence(timeout: 2))
        field.tap()
        field.typeText(" revisión")
        // The native alert relocates above the keyboard; let that transition finish.
        Thread.sleep(forTimeInterval: 1)
        let editedTitle = field.value as? String ?? ""
        XCTAssertTrue(editedTitle.contains("revisión"))
        app.alerts.buttons["Guardar"].coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5)).tap()
        XCTAssertTrue(app.alerts.firstMatch.waitForNonExistence(timeout: 3))
        capture(app, "recents-renamed")
        XCTAssertEqual(row.label, editedTitle)
        row.swipeLeft()
        capture(app, "recents-archive-gesture")
        app.buttons["Archivar"].tap()
        XCTAssertFalse(row.exists)
        app.segmentedControls.buttons["Archivados"].tap()
        XCTAssertTrue(row.waitForExistence(timeout: 2))
        row.swipeLeft(); capture(app, "recents-restore-gesture"); app.buttons["Restaurar"].tap()
        XCTAssertFalse(row.exists)
        app.segmentedControls.buttons["Recientes"].tap()
        row.press(forDuration: 0.8); app.buttons["Eliminar"].tap()
        app.buttons["Eliminar chat"].tap()
        XCTAssertFalse(row.exists)
        app.segmentedControls.buttons["Eliminados"].tap()
        XCTAssertTrue(row.waitForExistence(timeout: 2))
        capture(app, "recents-deleted-recovery")
        row.tap()
        XCTAssertTrue(app.buttons["chat-history"].waitForExistence(timeout: 2))
        app.buttons["chat-history"].tap()
        XCTAssertTrue(row.waitForExistence(timeout: 2))
        XCTAssertTrue((row.value as? String ?? "").contains("Actual"))
    }

    func testScanAndEnglishParity() {
        continueAfterFailure = false
        for english in [false, true] {
            let app = XCUIApplication.cuadraoPreview()
            app.launchArguments = CuadraoPreviewLaunch.arguments + (english ? ["--design-english"] : [])
            app.launch(); app.buttons["tab.argus"].tap()
            app.buttons["chat-attach"].tap()
            let scan = app.buttons[english ? "Scan" : "Escanear"]
            XCTAssertTrue(scan.waitForExistence(timeout: 2))
            capture(app, english ? "scan-english" : "scan-spanish")
            scan.tap()
            XCTAssertTrue(app.buttons[english ? "Attach example" : "Adjuntar ejemplo"].waitForExistence(timeout: 2))
            app.buttons[english ? "Attach example" : "Adjuntar ejemplo"].tap()
            app.buttons["chat-history"].tap()
            XCTAssertTrue(app.segmentedControls.buttons[english ? "Archived" : "Archivados"].exists)
            if english {
                app.buttons["history-row-chat-cd"].press(forDuration: 0.8)
                XCTAssertTrue(app.buttons["Mark as unread"].exists)
                XCTAssertTrue(app.buttons["Rename"].exists)
                capture(app, "recents-menu-english")
            }
            app.terminate()
        }
    }

    func testSharedDatesInSearchAndLargerText() {
        continueAfterFailure = false
        let app = XCUIApplication.cuadraoPreview()
        app.launchArguments = CuadraoPreviewLaunch.arguments + ["-UIPreferredContentSizeCategoryName", "UICTContentSizeCategoryXXXL"]
        app.launch()
        app.buttons["tab.search"].tap()
        let query = app.textFields["cuadrao.search.query"]
        XCTAssertTrue(query.waitForExistence(timeout: 3))
        query.tap(); query.typeText("certificados\n")
        let result = app.buttons.matching(NSPredicate(format: "label CONTAINS %@", "Entender los certificados")).firstMatch
        XCTAssertTrue(result.waitForExistence(timeout: 3))
        XCTAssertTrue(result.label.contains("Hoy"))
        capture(app, "search-shared-date-large")
        result.tap()
        app.buttons["chat-history"].tap()
        let row = app.buttons["history-row-chat-cd"]
        XCTAssertTrue(row.waitForExistence(timeout: 3))
        XCTAssertTrue((row.value as? String ?? "").contains("Hoy"))
        XCTAssertFalse(app.buttons["history-menu-chat-cd"].exists)
        capture(app, "recents-dates-large")
    }

    private func capture(_ app: XCUIApplication, _ name: String) {
        let item = XCTAttachment(screenshot: app.screenshot())
        item.name = name; item.lifetime = .keepAlways; add(item)
    }
}
