import XCTest

final class ReleaseUIJourneyTests: XCTestCase {
    func testAvatarSaveCancelAndDefaultIcon() {
        let app = launch(spanish: true)
        capture(app, "profile-empty-circle-es")
        app.buttons["release.profile.avatar"].tap()
        XCTAssertTrue(app.buttons["release.avatar.sun"].waitForExistence(timeout: 4))
        app.buttons["release.avatar.sun"].tap()
        app.buttons["release.avatar.cancel"].tap()
        app.buttons["release.profile.avatar"].tap()
        XCTAssertTrue(app.buttons["release.avatar.none"].isSelected)
        app.buttons["release.avatar.moon"].tap()
        app.buttons["release.avatar.save"].tap()
        capture(app, "theme-tab-unframed-es")
        app.buttons["release.profile.avatar"].tap()
        XCTAssertTrue(app.buttons["release.avatar.moon"].isSelected)
        app.buttons["release.avatar.none"].tap()
        app.buttons["release.avatar.save"].tap()
        app.buttons["release.profile.avatar"].tap()
        XCTAssertTrue(app.buttons["release.avatar.none"].isSelected)
        capture(app, "avatar-default-restored-es")
    }

    func testAvatarEnglishLargeText() {
        let app = launch(spanish: false, large: true)
        app.buttons["release.profile.avatar"].tap()
        XCTAssertTrue(app.buttons["release.avatar.photo"].waitForExistence(timeout: 4))
        XCTAssertEqual(app.buttons["release.avatar.photo"].label, "Choose photo")
        app.buttons["release.avatar.initials"].tap()
        app.buttons["release.avatar.save"].tap()
        XCTAssertTrue(app.buttons["header.profile"].waitForExistence(timeout: 3))
        capture(app, "avatar-initials-large-en")
    }

    func testDeletionConfirmationPendingAndFinish() {
        let app = launch(spanish: true)
        app.buttons["release.review.identity"].tap()
        app.buttons["identity.gallery.delete"].tap()
        XCTAssertTrue(app.staticTexts["identity.delete.sharedConsequences"].waitForExistence(timeout: 3))
        let next = app.buttons["identity.delete.continue"]
        reveal(next, in: app)
        next.tap()
        let field = app.textFields["identity.delete.verification"]
        reveal(field, in: app)
        field.tap(); field.typeText("DELETE")
        let submit = app.buttons["identity.delete.submit"]
        reveal(submit, in: app); submit.tap()
        XCTAssertFalse(app.buttons["identity.delete.complete"].exists)
        app.buttons["identity.delete.fixtureStates"].tap()
        app.buttons["Pendiente"].tap()
        XCTAssertTrue(app.buttons["identity.delete.check"].waitForExistence(timeout: 3))
        capture(app, "deletion-pending-es")
        app.buttons["identity.delete.fixtureStates"].tap()
        app.buttons["Completada"].tap()
        app.buttons["identity.delete.complete"].tap()
        XCTAssertTrue(app.staticTexts["Sesión cerrada"].waitForExistence(timeout: 3))
    }

    func testSocialCancellationAndNameRecovery() {
        let app = launch(spanish: false)
        app.buttons["release.review.identity"].tap()
        app.buttons["identity.gallery.social"].tap()
        app.buttons["identity.social.apple"].tap()
        XCTAssertTrue(app.descendants(matching: .any).matching(identifier: "identity.social.loading").firstMatch.waitForExistence(timeout: 3))
        app.buttons["identity.social.fixtureStates"].tap()
        app.buttons["Cancelled"].tap()
        XCTAssertTrue(app.staticTexts["identity.social.cancelled"].waitForExistence(timeout: 3))
        XCTAssertTrue(app.staticTexts["identity.social.pendingInvite"].exists)
        app.buttons["identity.social.fixtureStates"].tap()
        app.buttons["Missing name"].tap()
        let name = app.textFields["identity.social.name"]
        XCTAssertTrue(name.waitForExistence(timeout: 3))
        name.tap(); name.typeText("Alex")
        app.buttons["identity.social.saveName"].tap()
        XCTAssertFalse(app.buttons["identity.social.complete"].exists)
        capture(app, "social-name-en")
    }

    func testInviteFullStateAndQRSharing() {
        let app = launch(spanish: true)
        app.buttons["release.review.invites"].tap()
        app.buttons["release.invites.gallery.gate.full"].tap()
        XCTAssertTrue(app.staticTexts["release.inviteGate.status.full"].waitForExistence(timeout: 3))
        XCTAssertTrue(app.buttons["release.inviteGate.waitlist"].exists)
        capture(app, "invitation-full-es")
        app.navigationBars.buttons.element(boundBy: 0).tap()
        let personal = app.buttons["release.invites.gallery.personal"]
        reveal(personal, in: app); personal.tap()
        XCTAssertTrue(app.staticTexts["release.personalInvites.remaining"].waitForExistence(timeout: 3))
        capture(app, "personal-invitation-es")
    }

    func testUpdatesNoDataAndReadOnlyHistory() {
        let app = launch(spanish: true)
        app.buttons["release.review.updates"].tap()
        XCTAssertTrue(app.buttons["updates-row-0"].waitForExistence(timeout: 3))
        app.buttons["updates-row-0"].tap()
        capture(app, "bill-notice-es")
        app.navigationBars.buttons.element(boundBy: 0).tap()
        app.buttons["updates-gallery-truth"].tap()
        XCTAssertTrue(app.staticTexts["Sin datos"].waitForExistence(timeout: 3))
        let history = app.descendants(matching: .any).matching(identifier: "release-moved-history-note").firstMatch
        reveal(history, in: app)
        capture(app, "no-data-moved-history-es")
        XCTAssertFalse(app.buttons["Editar"].exists)
    }

    func testPhotoCropAndTabAvatarInDarkAppearance() {
        let app = launch(spanish: false, dark: true)
        app.buttons["release.profile.avatar"].tap()
        app.buttons["release.avatar.photo"].tap()
        let photo = app.images.matching(identifier: "PXGGridLayout-Info").firstMatch
        XCTAssertTrue(photo.waitForExistence(timeout: 8))
        photo.tap()
        XCTAssertTrue(app.buttons["cuadrao.profile.crop.use"].waitForExistence(timeout: 8))
        capture(app, "photo-crop-dark-en")
        app.buttons["cuadrao.profile.crop.use"].tap()
        XCTAssertTrue(app.buttons["release.avatar.save"].waitForExistence(timeout: 5))
        app.buttons["release.avatar.save"].tap()
        XCTAssertTrue(app.buttons["header.profile"].waitForExistence(timeout: 3))
        capture(app, "photo-tab-dark-en")
        app.buttons["release.profile.avatar"].tap()
        XCTAssertTrue(app.buttons["Reposition photo"].waitForExistence(timeout: 3))
    }

    func testDeletionCodeResendClearsOldCode() {
        let app = launch(spanish: false)
        app.buttons["release.review.identity"].tap()
        app.buttons["identity.gallery.delete"].tap()
        app.buttons["identity.delete.fixtureStates"].tap()
        app.buttons["Code"].tap()
        app.buttons["identity.delete.fixtureStates"].tap()
        app.buttons["Verification rejected"].tap()
        let field = app.textFields["identity.delete.verification"]
        reveal(field, in: app); field.tap(); field.typeText("123456")
        let resend = app.buttons["identity.delete.resend"]
        reveal(resend, in: app); resend.tap()
        XCTAssertFalse(app.buttons["identity.delete.submit"].exists)
        app.buttons["identity.delete.fixtureStates"].tap()
        app.buttons["Code sent"].tap()
        XCTAssertFalse(app.buttons["identity.delete.submit"].isEnabled)
        app.buttons["identity.delete.cancelVerification"].tap()
        XCTAssertFalse(app.textFields["identity.delete.verification"].exists)
        capture(app, "verification-cancelled-en")
    }

    func testAIConsentCanBeDeclined() {
        let app = launch(spanish: false)
        app.buttons["release.review.identity"].tap()
        app.buttons["identity.gallery.ai"].tap()
        XCTAssertTrue(app.buttons["identity.ai.allow"].waitForExistence(timeout: 3))
        capture(app, "ai-consent-en")
        app.buttons["identity.ai.decline"].tap()
        XCTAssertTrue(app.buttons["identity.gallery.ai"].waitForExistence(timeout: 3))
    }

    private func reveal(_ element: XCUIElement, in app: XCUIApplication) {
        for _ in 0..<8 {
            if element.exists && element.isHittable { return }
            app.swipeUp()
        }
        XCTAssertTrue(element.exists)
    }

    private func launch(spanish: Bool, large: Bool = false, dark: Bool = false) -> XCUIApplication {
        continueAfterFailure = false
        let app = XCUIApplication()
        app.launchArguments = ["--cuadrao-release-ui", "-AppleLanguages", spanish ? "(es)" : "(en)", "-AppleLocale", spanish ? "es_DO" : "en_US"]
        if dark { app.launchArguments += ["--release-dark"] }
        if large { app.launchArguments += ["-UIPreferredContentSizeCategoryName", "UICTContentSizeCategoryAccessibilityXXXL"] }
        app.launch()
        XCTAssertTrue(app.buttons["release.profile.avatar"].waitForExistence(timeout: 6))
        return app
    }

    private func capture(_ app: XCUIApplication, _ name: String) {
        let attachment = XCTAttachment(screenshot: app.screenshot())
        attachment.name = name; attachment.lifetime = .keepAlways; add(attachment)
    }
}
