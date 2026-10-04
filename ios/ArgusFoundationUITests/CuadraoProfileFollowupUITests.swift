import XCTest

final class CuadraoProfileFollowupUITests: XCTestCase {
    func testSettingsNavigationAndSignOutClearance() {
        verifyNavigation(extra: [])
    }

    func testSettingsNavigationAndSignOutClearanceAtLargeText() {
        verifyNavigation(extra: ["-UIPreferredContentSizeCategoryName", "UICTContentSizeCategoryAccessibilityM"])
    }

    func testFeedbackPreservesKindsAndPartialDrafts() {
        let app = launch()
        openFeedback(app)
        let general = app.textFields["cuadrao.feedback.general"]
        general.tap(); general.typeText("Me gusta la claridad")
        chooseKind(app, "Una idea")
        let feature = app.textFields["cuadrao.feedback.feature"]
        feature.tap(); feature.typeText("Compartir una meta")
        chooseKind(app, "Un problema")
        let title = app.textFields["cuadrao.feedback.title"]
        title.tap(); title.typeText("El gráfico tarda")
        app.swipeUp()
        let save = app.buttons["cuadrao.feedback.save"]
        reveal(app, save)
        XCTAssertTrue(save.isEnabled)
        save.tap()
        XCTAssertTrue(app.staticTexts["cuadrao.feedback.saved"].waitForExistence(timeout: 3))
        shot(app, "feedback-partial-bug-saved")
        app.navigationBars.buttons.firstMatch.tap()
        app.buttons["Comentarios"].tap()
        XCTAssertEqual(title.value as? String, "El gráfico tarda")
        chooseKind(app, "Una idea")
        XCTAssertEqual(feature.value as? String, "Compartir una meta")
        chooseKind(app, "Comentario")
        XCTAssertEqual(general.value as? String, "Me gusta la claridad")
        general.tap(); general.typeText(" y los colores")
        XCTAssertFalse(app.staticTexts["cuadrao.feedback.saved"].exists)
        shot(app, "feedback-general-draft")
    }

    func testPhotoPickerSaveCancelAndRemove() {
        let app = launch()
        app.buttons["header.profile"].tap()
        app.buttons["cuadrao.profile.identity"].tap()
        pickPhoto(app)
        XCTAssertTrue(app.buttons["cuadrao.profile.photo.remove"].waitForExistence(timeout: 10))
        app.buttons["cuadrao.profile.cancel"].tap()
        app.buttons["cuadrao.profile.identity"].tap()
        XCTAssertFalse(app.buttons["cuadrao.profile.photo.remove"].exists)
        XCTAssertTrue(app.buttons["cuadrao.profile.avatar.none"].isSelected)
        pickPhoto(app)
        XCTAssertTrue(app.buttons["cuadrao.profile.photo.remove"].waitForExistence(timeout: 10))
        XCTAssertTrue(app.buttons["cuadrao.profile.save"].isEnabled)
        shot(app, "profile-photo-draft")
        app.buttons["cuadrao.profile.save"].tap()
        app.buttons["cuadrao.profile.identity"].tap()
        XCTAssertTrue(app.buttons["cuadrao.profile.photo.remove"].exists)
        app.buttons["cuadrao.profile.photo.remove"].tap()
        XCTAssertTrue(app.buttons["cuadrao.profile.avatar.none"].isSelected)
        app.buttons["cuadrao.profile.cancel"].tap()
        app.buttons["cuadrao.profile.identity"].tap()
        XCTAssertTrue(app.buttons["cuadrao.profile.photo.remove"].exists)
        app.buttons["cuadrao.profile.photo.remove"].tap()
        app.buttons["cuadrao.profile.save"].tap()
        app.buttons["cuadrao.profile.identity"].tap()
        XCTAssertFalse(app.buttons["cuadrao.profile.photo.remove"].exists)
        XCTAssertTrue(app.buttons["cuadrao.profile.avatar.none"].isSelected)
    }

    func testPhotoCropCancelPanZoomAndReedit() {
        let app = launch()
        app.buttons["header.profile"].tap()
        app.buttons["cuadrao.profile.identity"].tap()
        pickPhoto(app, accept: false)
        app.buttons["cuadrao.profile.crop.cancel"].tap()
        XCTAssertFalse(app.buttons["cuadrao.profile.photo.remove"].exists)
        XCTAssertTrue(app.buttons["cuadrao.profile.avatar.none"].isSelected)
        pickPhoto(app)
        app.buttons["cuadrao.profile.save"].tap()
        app.buttons["cuadrao.profile.identity"].tap()
        app.buttons["cuadrao.profile.photo.edit"].tap()
        let viewport = app.scrollViews["cuadrao.profile.crop.viewport"]
        XCTAssertTrue(viewport.waitForExistence(timeout: 3))
        let centered = viewport.value as? String
        XCTAssertNotNil(centered)
        let zoom = app.sliders["cuadrao.profile.crop.zoom"]
        reveal(app, zoom); zoom.adjust(toNormalizedSliderPosition: 0.45)
        let right = app.buttons["cuadrao.profile.crop.right"]
        reveal(app, right); right.tap()
        reveal(app, viewport)
        viewport.pinch(withScale: 1.2, velocity: 1)
        let start = viewport.coordinate(withNormalizedOffset: CGVector(dx: 0.55, dy: 0.5))
        let end = viewport.coordinate(withNormalizedOffset: CGVector(dx: 0.35, dy: 0.65))
        start.press(forDuration: 0.05, thenDragTo: end)
        XCTAssertNotEqual(viewport.value as? String, centered)
        let moved = viewport.value as? String
        XCTAssertNotNil(moved)
        shot(app, "profile-native-crop-pan-zoom")
        app.buttons["cuadrao.profile.crop.use"].tap()
        XCTAssertTrue(app.buttons["cuadrao.profile.photo.edit"].waitForExistence(timeout: 5))
        app.buttons["cuadrao.profile.photo.edit"].tap()
        XCTAssertTrue(viewport.waitForExistence(timeout: 3))
        XCTAssertEqual(viewport.value as? String, moved)
        let reset = app.buttons["cuadrao.profile.crop.reset"]
        reveal(app, reset); reset.tap()
        XCTAssertEqual(viewport.value as? String, centered)
        shot(app, "profile-crop-reedit-full-source")
        app.buttons["cuadrao.profile.crop.cancel"].tap()
        app.buttons["cuadrao.profile.photo.edit"].tap()
        XCTAssertTrue(viewport.waitForExistence(timeout: 3))
        XCTAssertEqual(viewport.value as? String, moved)
        app.buttons["cuadrao.profile.crop.cancel"].tap()
        app.buttons["cuadrao.profile.cancel"].tap()
        app.buttons["cuadrao.profile.identity"].tap()
        app.buttons["cuadrao.profile.photo.edit"].tap()
        XCTAssertTrue(viewport.waitForExistence(timeout: 3))
        XCTAssertEqual(viewport.value as? String, centered)
    }

    func testReleaseGatesHideUnfinishedRowsAndPhotos() {
        let unfinished = ["personalization", "security", "usage"]
        let debug = launch()
        debug.buttons["header.profile"].tap()
        for route in unfinished {
            XCTAssertTrue(debug.buttons["cuadrao.profile.\(route)"].waitForExistence(timeout: 3), "DEBUG shows \(route)")
        }
        debug.buttons["cuadrao.profile.identity"].tap()
        XCTAssertTrue(debug.buttons["cuadrao.profile.photo.choose"].waitForExistence(timeout: 3))
        debug.terminate()
        let release = launch(extra: ["--cuadrao-release-gates"])
        release.buttons["header.profile"].tap()
        XCTAssertTrue(release.buttons["cuadrao.profile.preferences"].waitForExistence(timeout: 3))
        for route in unfinished {
            XCTAssertFalse(release.buttons["cuadrao.profile.\(route)"].exists, "Release gates hide \(route)")
        }
        shot(release, "profile-release-gates")
        release.buttons["cuadrao.profile.identity"].tap()
        XCTAssertTrue(release.buttons["cuadrao.profile.avatar.none"].waitForExistence(timeout: 3))
        XCTAssertFalse(release.buttons["cuadrao.profile.photo.choose"].exists)
    }

    private func verifyNavigation(extra: [String]) {
        let app = launch(extra: extra)
        app.buttons["header.profile"].tap()
        let signOut = app.buttons["cuadrao.profile.signout"]
        let home = app.buttons["tab.home"]
        for _ in 0..<7 {
            if signOut.isHittable && signOut.frame.maxY < home.frame.minY { break }
            app.swipeUp()
        }
        app.swipeUp()
        XCTAssertTrue(signOut.isHittable)
        XCTAssertLessThan(signOut.frame.maxY, home.frame.minY)
        shot(app, extra.isEmpty ? "profile-signout-clearance" : "profile-signout-large-clearance")
        signOut.tap()
        XCTAssertTrue(app.alerts.firstMatch.waitForExistence(timeout: 3))
        app.alerts.buttons["Entendido"].tap()
        let preferences = app.buttons["cuadrao.profile.preferences"]
        reveal(app, preferences); preferences.tap()
        XCTAssertTrue(app.navigationBars["Preferencias"].waitForExistence(timeout: 3))
        XCTAssertFalse(home.exists)
        app.navigationBars.buttons.firstMatch.tap()
        XCTAssertTrue(home.waitForExistence(timeout: 3))
        openFeedback(app, selectProfile: false)
        XCTAssertTrue(app.navigationBars["Comentarios"].exists)
        XCTAssertFalse(home.exists)
        shot(app, extra.isEmpty ? "feedback-without-tabs" : "feedback-large-without-tabs")
        app.navigationBars.buttons.firstMatch.tap()
        XCTAssertFalse(home.exists)
        app.navigationBars.buttons.firstMatch.tap()
        XCTAssertTrue(home.waitForExistence(timeout: 3))
    }

    private func openFeedback(_ app: XCUIApplication, selectProfile: Bool = true) {
        if selectProfile { app.buttons["header.profile"].tap() }
        let help = app.buttons["cuadrao.profile.help"]
        reveal(app, help); help.tap()
        app.buttons["Comentarios"].tap()
    }

    private func chooseKind(_ app: XCUIApplication, _ title: String) {
        let choice = app.buttons["cuadrao.feedback.kind"]
        reveal(app, choice)
        choice.coordinate(withNormalizedOffset: CGVector(dx: 0.9, dy: 0.5)).tap()
        app.buttons[title].tap()
    }

    private func pickPhoto(_ app: XCUIApplication, accept: Bool = true) {
        let choose = app.buttons["cuadrao.profile.photo.choose"]
        reveal(app, choose); choose.tap()
        let photo = app.images.matching(identifier: "PXGGridLayout-Info").firstMatch
        XCTAssertTrue(photo.waitForExistence(timeout: 5), "Seed the simulator Photos library before this journey")
        photo.tap()
        let use = app.buttons["cuadrao.profile.crop.use"]
        XCTAssertTrue(use.waitForExistence(timeout: 10))
        if accept {
            use.tap()
            XCTAssertTrue(app.buttons["cuadrao.profile.photo.remove"].waitForExistence(timeout: 5))
        }
    }

    private func launch(extra: [String] = []) -> XCUIApplication {
        continueAfterFailure = false
        let app = XCUIApplication.cuadraoPreview()
        app.launchArguments = CuadraoPreviewLaunch.arguments + ["--plan-reset", "-cuadrao.design.appearance", "light"] + extra
        app.launch(); return app
    }

    private func reveal(_ app: XCUIApplication, _ element: XCUIElement) {
        for _ in 0..<10 {
            // A drag that starts on the keyboard never scrolls the form, so stay above it.
            let keyboard = app.keyboards.firstMatch
            let floor = keyboard.exists ? keyboard.frame.minY : app.frame.maxY - 100
            if element.isHittable && element.frame.maxY < floor { return }
            let downward = !element.exists || element.frame.minY > app.frame.midY
            let top = min(0.7, floor / app.frame.height - 0.05)
            let start = app.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: downward ? top : 0.3))
            let end = app.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: downward ? top - 0.35 : 0.65))
            start.press(forDuration: 0.01, thenDragTo: end)
        }
        XCTAssertTrue(element.isHittable)
    }

    private func shot(_ app: XCUIApplication, _ name: String) {
        Thread.sleep(forTimeInterval: 0.6)
        let attachment = XCTAttachment(screenshot: app.screenshot())
        attachment.name = name; attachment.lifetime = .keepAlways; add(attachment)
    }
}
