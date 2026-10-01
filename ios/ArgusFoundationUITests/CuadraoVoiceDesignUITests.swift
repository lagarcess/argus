import XCTest

final class CuadraoVoiceDesignUITests: XCTestCase {
    func testVoiceStaysAvailableAcrossSheetsAndSurfaces() {
        continueAfterFailure = false
        let app = XCUIApplication()
        app.launch()
        XCTAssertTrue(app.buttons["cuadrao-tab-2"].waitForExistence(timeout: 8))
        app.buttons["cuadrao-tab-2"].tap()
        XCTAssertTrue(app.buttons["chat-send"].waitForExistence(timeout: 5))
        app.buttons["chat-send"].tap()
        XCTAssertTrue(app.buttons["voice-expand"].waitForExistence(timeout: 3))
        app.buttons["voice-expand"].tap()
        XCTAssertTrue(app.buttons["voice-minimize"].waitForExistence(timeout: 3))
        app.buttons["Sheet Grabber"].swipeDown()
        XCTAssertTrue(app.buttons["voice-expand"].waitForExistence(timeout: 3))
        app.buttons["cuadrao-tab-4"].tap()
        XCTAssertTrue(app.buttons["cuadrao.profile.identity"].waitForExistence(timeout: 3))
        XCTAssertTrue(app.buttons["voice-expand"].exists)
        app.buttons["voice-end-compact"].tap()
        XCTAssertFalse(app.buttons["voice-expand"].exists)
        let capture = XCTAttachment(screenshot: app.screenshot())
        capture.name = "profile-after-voice"; capture.lifetime = .keepAlways; add(capture)
    }
    func testVoiceChoiceAndProposalHandoff() {
        continueAfterFailure = false
        let app = XCUIApplication()
        app.launch()
        app.buttons["cuadrao-tab-2"].tap()
        app.buttons["chat-send"].tap()
        app.buttons["voice-expand"].tap()
        app.buttons["voice-choose"].tap()
        XCTAssertTrue(app.buttons["voice-option-sal"].waitForExistence(timeout: 3))
        // Opening preferences stays quiet; paging both selects and previews a voice.
        XCTAssertTrue(app.buttons["voice-sample"].label.hasPrefix("Escuchar"))
        app.buttons["voice-option-ara"].tap()
        swipeVoice(app.staticTexts["Ara"])
        XCTAssertEqual(app.buttons["voice-sample"].label, "Detener Eve")
        swipeVoice(app.staticTexts["Eve"])
        XCTAssertEqual(app.buttons["voice-sample"].label, "Detener Sal")
        app.buttons["voice-sample"].tap()
        XCTAssertEqual(app.buttons["voice-sample"].label, "Escuchar Sal")
        capture(app, "voice-carousel")
        app.buttons["voice-picker-done"].tap()
        app.buttons["voice-minimize"].tap()
        app.buttons["cuadrao-tab-4"].tap()
        app.buttons["Preferencias"].tap()
        app.collectionViews.firstMatch.swipeUp()
        capture(app, "preferences-before-voice")
        app.buttons["Voz"].tap()
        XCTAssertTrue(app.buttons["voice-preference"].waitForExistence(timeout: 3))
        XCTAssertEqual(app.buttons["voice-preference"].value as? String, "Sal")
        capture(app, "shared-voice-preference")
        app.buttons["voice-expand"].tap()
        app.buttons["Estados de la vista previa"].tap()
        app.buttons["Ver propuesta de ejemplo"].tap()
        XCTAssertTrue(app.buttons["Revisar propuesta"].waitForExistence(timeout: 3))
        XCTAssertTrue(app.buttons["voice-expand"].exists)
        capture(app, "proposal-in-plan")
        app.buttons["Revisar propuesta"].tap()
        app.buttons["Marcar como revisada"].tap()
        XCTAssertTrue(app.staticTexts["Revisada en la vista previa"].waitForExistence(timeout: 3))
        app.buttons["voice-end-compact"].tap()
        XCTAssertTrue(app.staticTexts["Revisada en la vista previa"].exists)
        app.terminate(); app.launch()
        app.buttons["cuadrao-tab-4"].tap()
        app.buttons["Preferencias"].tap(); app.collectionViews.firstMatch.swipeUp(); app.buttons["Voz"].tap()
        XCTAssertEqual(app.buttons["voice-preference"].value as? String, "Sal")
    }
    private func swipeVoice(_ title: XCUIElement) {
        let center = title.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5))
        center.withOffset(CGVector(dx: 120, dy: 0)).press(forDuration: 0.05,
            thenDragTo: center.withOffset(CGVector(dx: -120, dy: 0)))
    }
    private func capture(_ app: XCUIApplication, _ name: String) {
        let item = XCTAttachment(screenshot: app.screenshot())
        item.name = name; item.lifetime = .keepAlways; add(item)
    }

}
