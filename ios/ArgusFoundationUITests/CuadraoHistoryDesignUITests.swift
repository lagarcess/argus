import XCTest

final class CuadraoHistoryDesignUITests: XCTestCase {
    func testRecentsActionsAndRecovery() {
        continueAfterFailure = false
        let app = XCUIApplication(); app.launch()
        app.buttons["cuadrao-tab-2"].tap()
        app.buttons["chat-history"].tap()
        let row = app.buttons["history-row-chat-cd"]
        let menu = app.buttons["history-menu-chat-cd"]
        XCTAssertTrue(row.waitForExistence(timeout: 4))
        capture(app, "recents-spanish")
        row.swipeRight()
        app.buttons["Fijar"].tap()
        XCTAssertTrue(app.staticTexts["Fijados"].exists)
        menu.tap()
        capture(app, "recents-menu")
        app.buttons["Marcar como no leído"].tap()
        XCTAssertEqual(row.value as? String, "No leído")
        menu.tap(); app.buttons["Cambiar nombre"].tap()
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
        row.swipeLeft(); app.buttons["Restaurar"].tap()
        XCTAssertFalse(row.exists)
        app.segmentedControls.buttons["Recientes"].tap()
        menu.tap(); app.buttons["Eliminar"].tap()
        app.buttons["Eliminar chat"].tap()
        XCTAssertFalse(row.exists)
        app.segmentedControls.buttons["Eliminados"].tap()
        XCTAssertTrue(row.waitForExistence(timeout: 2))
        capture(app, "recents-deleted-recovery")
        row.tap()
        XCTAssertTrue(app.buttons["chat-history"].waitForExistence(timeout: 2))
        app.buttons["chat-history"].tap()
        XCTAssertTrue(row.waitForExistence(timeout: 2))
        XCTAssertEqual(row.value as? String, "Actual")
    }

    func testScanAndEnglishParity() {
        continueAfterFailure = false
        for english in [false, true] {
            let app = XCUIApplication()
            app.launchArguments = english ? ["--design-english"] : []
            app.launch(); app.buttons["cuadrao-tab-2"].tap()
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
                app.buttons["history-menu-chat-cd"].tap()
                XCTAssertTrue(app.buttons["Mark as unread"].exists)
                XCTAssertTrue(app.buttons["Rename"].exists)
                capture(app, "recents-menu-english")
            }
            app.terminate()
        }
    }

    private func capture(_ app: XCUIApplication, _ name: String) {
        let item = XCTAttachment(screenshot: app.screenshot())
        item.name = name; item.lifetime = .keepAlways; add(item)
    }
}
