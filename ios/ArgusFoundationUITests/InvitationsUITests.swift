import XCTest

/// Drives the connected invitation screens and `InvitationsModel` over the DEBUG stub server,
/// which answers only in shapes the real `/api/v1/invites` routes produce. Codes name the outcome.
final class InvitationsUITests: XCTestCase {
    private let betaLink = "https://cuadrao.ai/invite#beta-link-token-000000000000000000000000001"
    private let householdLink = "argus-household://invite#household-link-token-00000000000000000000000"

    func testGateExplainsEachCodeOutcomeAndAdmitsWithAValidCode() {
        let app = launch()
        let field = app.textFields["release.inviteGate.code"]
        XCTAssertTrue(field.waitForExistence(timeout: 10))
        XCTAssertTrue(app.buttons["release.inviteGate.waitlist"].exists)
        for (code, state) in [("NADA-0000-0000", "invalid"), ("EXPD-0000-0001", "expired"), ("USED-0000-0001", "consumed"),
                              ("REVK-0000-0001", "revoked"), ("FULL-0000-0001", "full"), ("WAIT-0000-0001", "rateLimited"),
                              ("DOWN-0000-0001", "unavailable")] {
            enter(code, in: app)
            XCTAssertTrue(element(app, "release.inviteGate.status." + state).waitForExistence(timeout: 5), state)
            XCTAssertFalse(app.staticTexts["harness.app"].exists, state)
        }
        enter("BETA-0000-0001", in: app)
        XCTAssertTrue(app.staticTexts["harness.app"].waitForExistence(timeout: 5))
        XCTAssertFalse(field.exists)
        XCTAssertTrue(app.buttons["invites.profile"].exists)
    }

    func testWaitlistHandOffAppearsOnlyWithTheServersURL() {
        let app = launch(["--harness-no-waitlist"])
        XCTAssertTrue(app.textFields["release.inviteGate.code"].waitForExistence(timeout: 10))
        XCTAssertFalse(app.buttons["release.inviteGate.waitlist"].exists)
        XCTAssertFalse(app.staticTexts["harness.app"].exists)
    }

    func testLinkIntentSurvivesCancelledSignInAndAdmitsAfterSignIn() {
        let app = launch(["--harness-signed-out", "--harness-links", "--harness-open-url", betaLink])
        let pending = element(app, "invites.pending")
        XCTAssertTrue(pending.waitForExistence(timeout: 10))
        app.buttons["harness.cancelSignIn"].tap()
        XCTAssertTrue(pending.exists)
        XCTAssertTrue(app.staticTexts["harness.signedOut"].exists)
        app.buttons["harness.signIn"].tap()
        let field = app.textFields["release.inviteGate.code"]
        XCTAssertTrue(field.waitForExistence(timeout: 10))
        XCTAssertEqual(field.value as? String, "beta-link-token-000000000000000000000000001")
        XCTAssertFalse(app.staticTexts["harness.app"].exists)
        app.buttons["release.inviteGate.submit"].tap()
        XCTAssertTrue(app.staticTexts["harness.app"].waitForExistence(timeout: 10))
        XCTAssertFalse(field.exists)
    }

    func testALinkIsForgottenWhenThePersonSignsOut() {
        let app = launch(["--harness-links", "--harness-access-down", "1000", "--harness-open-url", betaLink])
        XCTAssertTrue(element(app, "invites.access.unanswered").waitForExistence(timeout: 10))
        app.buttons["invites.gate.signOut"].tap()
        XCTAssertTrue(app.staticTexts["harness.signedOut"].waitForExistence(timeout: 5))
        XCTAssertFalse(element(app, "invites.pending").exists)
    }

    func testDiscardingASavedLinkLeavesTheGateForManualEntry() {
        let app = launch(["--harness-signed-out", "--harness-links", "--harness-open-url", betaLink])
        XCTAssertTrue(element(app, "invites.pending").waitForExistence(timeout: 10))
        app.buttons["invites.pending.discard"].tap()
        XCTAssertFalse(element(app, "invites.pending").exists)
        app.buttons["harness.signIn"].tap()
        XCTAssertTrue(app.textFields["release.inviteGate.code"].waitForExistence(timeout: 10))
    }

    func testNoLinkOfEitherShapeIsHandledWhileTheLinkFlagIsOff() {
        for link in [betaLink, householdLink] {
            let signedOut = launch(["--harness-signed-out", "--harness-open-url", link])
            XCTAssertTrue(signedOut.staticTexts["harness.signedOut"].waitForExistence(timeout: 10))
            XCTAssertFalse(element(signedOut, "invites.pending").exists)
            signedOut.terminate()
            let gated = launch(["--harness-open-url", link])
            let field = gated.textFields["release.inviteGate.code"]
            XCTAssertTrue(field.waitForExistence(timeout: 10))
            XCTAssertNotEqual(field.value as? String, String(link.split(separator: "#")[1]))
            XCTAssertFalse(gated.staticTexts["harness.household.opened"].exists)
            XCTAssertFalse(gated.staticTexts["harness.app"].exists)
            gated.terminate()
        }
    }

    func testAnAccessCheckWithoutAnAnswerKeepsTheAppClosed() {
        let app = launch(["--harness-access-down", "1000"])
        XCTAssertTrue(element(app, "invites.access.unanswered").waitForExistence(timeout: 10))
        XCTAssertFalse(app.staticTexts["harness.app"].exists)
        capture(app, "access-unanswered-es-light")
        app.buttons["invites.access.retry"].tap()
        XCTAssertTrue(element(app, "invites.access.unanswered").waitForExistence(timeout: 5))
        XCTAssertFalse(app.staticTexts["harness.app"].exists)
        XCTAssertFalse(app.textFields["release.inviteGate.code"].exists)
    }

    func testWithTheClientFlagOffTheAppOpensAtOnceWithoutInvitations() {
        let app = launch(["--harness-client-off", "--harness-access-down", "1000"])
        XCTAssertTrue(app.staticTexts["harness.app"].waitForExistence(timeout: 10))
        XCTAssertFalse(app.buttons["invites.profile"].exists)
        XCTAssertFalse(element(app, "invites.access.unanswered").exists)
    }

    func testAFailedLinkShowsWhyAndKeepsManualCodeRecovery() {
        let app = launch(["--harness-links", "--harness-open-url", "https://cuadrao.ai/invite#expd-link-token-00000000000000000000000000"])
        let field = app.textFields["release.inviteGate.code"]
        XCTAssertTrue(field.waitForExistence(timeout: 10))
        XCTAssertEqual(field.value as? String, "expd-link-token-00000000000000000000000000")
        XCTAssertFalse(element(app, "release.inviteGate.status.expired").exists)
        app.buttons["release.inviteGate.submit"].tap()
        XCTAssertTrue(element(app, "release.inviteGate.status.expired").waitForExistence(timeout: 10))
        enter("BETA-0000-0001", in: app)
        XCTAssertTrue(app.staticTexts["harness.app"].waitForExistence(timeout: 5))
    }

    func testAnAdmittedPersonReturnsToTheAppFromABetaLink() {
        let app = launch(["--harness-admitted", "--harness-links", "--harness-open-url", betaLink])
        let alert = app.alerts.firstMatch
        XCTAssertTrue(alert.waitForExistence(timeout: 10))
        XCTAssertEqual(alert.label, "Ya tienes acceso")
        capture(app, "admitted-link-return-es-light")
        alert.buttons["OK"].tap()
        XCTAssertTrue(app.staticTexts["harness.app"].waitForExistence(timeout: 5))
        XCTAssertFalse(app.textFields["release.inviteGate.code"].exists)
    }

    func testHouseholdCodesAndLinksGoToTheHouseholdJoinStep() {
        let gated = launch()
        XCTAssertTrue(gated.textFields["release.inviteGate.code"].waitForExistence(timeout: 10))
        enter("HOME-0000-0001", in: gated)
        XCTAssertTrue(gated.staticTexts["harness.household.opened"].waitForExistence(timeout: 5))
        gated.terminate()
        let legacy = launch(["--harness-admitted", "--harness-links", "--harness-open-url", householdLink])
        XCTAssertTrue(legacy.staticTexts["harness.household.opened"].waitForExistence(timeout: 10))
    }

    func testABetaInvitationWithoutAServerLinkSharesTheCodeAlone() {
        let app = launch(["--harness-admitted"])
        openHub(app)
        app.buttons["invites.personal"].tap()
        XCTAssertTrue(app.buttons["release.personalInvites.create"].waitForExistence(timeout: 5))
        app.buttons["release.personalInvites.create"].tap()
        let code = app.staticTexts["release.personalInvites.code"]
        XCTAssertTrue(code.waitForExistence(timeout: 5))
        XCTAssertEqual(code.label, "DEMO-ONLY-0007")
        XCTAssertEqual(app.staticTexts["release.personalInvites.remaining"].label, "Te quedan 6 de 10 invitaciones")
        XCTAssertFalse(app.staticTexts["release.personalInvites.link"].exists)
        XCTAssertFalse(element(app, "release.personalInvites.qr").exists)
        capture(app, "personal-invitation-code-only-es-light")
    }

    func testPersonalInvitationsShowTheServersQuotaAndOneTimeSecrets() {
        let app = launch(["--harness-admitted", "--harness-server-links"])
        openHub(app)
        XCTAssertTrue(element(app, "invites.sent.accepted").waitForExistence(timeout: 5))
        XCTAssertTrue(element(app, "invites.sent.pending").exists)
        XCTAssertFalse(app.buttons["invites.group.new"].exists)
        app.buttons["invites.personal"].tap()
        let remaining = app.staticTexts["release.personalInvites.remaining"]
        XCTAssertTrue(remaining.waitForExistence(timeout: 5))
        XCTAssertEqual(remaining.label, "Te quedan 7 de 10 invitaciones")
        XCTAssertFalse(app.staticTexts["release.personalInvites.code"].exists)
        app.buttons["release.personalInvites.create"].tap()
        let code = app.staticTexts["release.personalInvites.code"]
        XCTAssertTrue(code.waitForExistence(timeout: 5))
        XCTAssertEqual(code.label, "DEMO-ONLY-0007")
        XCTAssertEqual(remaining.label, "Te quedan 6 de 10 invitaciones")
        XCTAssertTrue(app.staticTexts["release.personalInvites.link"].label.hasPrefix("https://cuadrao.ai/invite#"))
        XCTAssertTrue(element(app, "release.personalInvites.qr").exists)
        XCTAssertTrue(app.staticTexts["Compartir el enlace no significa que la persona ya aceptó."].exists)
    }

    func testASpentQuotaCannotCreateAnother() {
        let app = launch(["--harness-admitted", "--harness-quota-used", "10"])
        openHub(app)
        app.buttons["invites.personal"].tap()
        let remaining = app.staticTexts["release.personalInvites.remaining"]
        XCTAssertTrue(remaining.waitForExistence(timeout: 5))
        XCTAssertEqual(remaining.label, "Te quedan 0 de 10 invitaciones")
        XCTAssertFalse(app.buttons["release.personalInvites.create"].isEnabled)
    }

    func testFounderSeesGroupLinkUsageFullAndExpiredAndCreatesOne() {
        let app = launch(["--harness-admitted", "--harness-founder"])
        openHub(app)
        XCTAssertTrue(element(app, "invites.group.full").waitForExistence(timeout: 5))
        XCTAssertTrue(element(app, "invites.group.expired").exists)
        app.buttons["invites.group.new"].tap()
        let label = app.textFields["release.groupInvite.label"]
        XCTAssertTrue(label.waitForExistence(timeout: 5))
        XCTAssertFalse(app.buttons["release.groupInvite.create"].isEnabled)
        label.tap(); label.typeText("Cena de prueba")
        let cap = app.textFields["release.groupInvite.cap"]
        cap.tap(); cap.typeText("25")
        app.buttons["release.groupInvite.create"].tap()
        let usage = app.staticTexts["release.groupInvite.usage"]
        XCTAssertTrue(usage.waitForExistence(timeout: 5))
        XCTAssertEqual(usage.label, "0 de 25 lugares usados")
        XCTAssertEqual(app.staticTexts["release.groupInvite.code"].label, "DEMO-ONLY-GRP1")
        XCTAssertFalse(app.staticTexts["release.groupInvite.link"].exists)
        app.navigationBars.buttons.element(boundBy: 0).tap()
        let open = element(app, "invites.group.open")
        XCTAssertTrue(open.waitForExistence(timeout: 5))
        open.swipeLeft()
        app.buttons["Revocar"].tap()
        XCTAssertTrue(element(app, "invites.group.revoked").waitForExistence(timeout: 5))
        XCTAssertFalse(open.exists)
    }

    func testOffSurfaceKeepsTodaysAppWithoutInvitations() {
        let app = launch(["--harness-surface-off"])
        XCTAssertTrue(app.staticTexts["harness.app"].waitForExistence(timeout: 10))
        XCTAssertFalse(app.buttons["invites.profile"].exists)
        XCTAssertFalse(app.textFields["release.inviteGate.code"].exists)
    }

    func testGateOffAdmitsWithoutAGateAndOffersInvitations() {
        let app = launch(["--harness-gate-off"])
        XCTAssertTrue(app.staticTexts["harness.app"].waitForExistence(timeout: 10))
        XCTAssertTrue(app.buttons["invites.profile"].exists)
    }

    func testMainStatesInBothLanguagesAndAppearances() {
        for spanish in [true, false] {
            for dark in [false, true] {
                let suffix = (spanish ? "es" : "en") + (dark ? "-dark" : "-light")
                let gated = launch(spanish: spanish, dark: dark)
                XCTAssertTrue(gated.textFields["release.inviteGate.code"].waitForExistence(timeout: 10))
                capture(gated, "gate-ready-" + suffix)
                enter("NADA-0000-0000", in: gated)
                XCTAssertTrue(element(gated, "release.inviteGate.status.invalid").waitForExistence(timeout: 5))
                dismissKeyboard(gated)
                capture(gated, "gate-invalid-" + suffix)
                enter("WAIT-0000-0001", in: gated)
                XCTAssertTrue(element(gated, "release.inviteGate.status.rateLimited").waitForExistence(timeout: 5))
                dismissKeyboard(gated)
                capture(gated, "gate-rate-limited-" + suffix)
                gated.terminate()

                let pending = launch(["--harness-signed-out", "--harness-links", "--harness-open-url", betaLink], spanish: spanish, dark: dark)
                XCTAssertTrue(element(pending, "invites.pending").waitForExistence(timeout: 10))
                capture(pending, "link-saved-signed-out-" + suffix)
                pending.terminate()

                let founder = launch(["--harness-admitted", "--harness-founder", "--harness-server-links"], spanish: spanish, dark: dark)
                openHub(founder)
                XCTAssertTrue(element(founder, "invites.group.full").waitForExistence(timeout: 5))
                capture(founder, "invitations-hub-" + suffix)
                founder.buttons["invites.personal"].tap()
                founder.buttons["release.personalInvites.create"].tap()
                XCTAssertTrue(founder.staticTexts["release.personalInvites.code"].waitForExistence(timeout: 5))
                capture(founder, "personal-invitation-created-" + suffix)
                founder.terminate()
            }
        }
    }

    private func launch(_ extra: [String] = [], spanish: Bool = true, dark: Bool = false) -> XCUIApplication {
        continueAfterFailure = false
        let app = XCUIApplication()
        app.launchArguments = ["--invitations-harness", "-AppleLanguages", spanish ? "(es-419)" : "(en)", "-AppleLocale", spanish ? "es_DO" : "en_US"] + extra
        if dark { app.launchArguments += ["--harness-dark"] }
        app.launch()
        return app
    }

    private func openHub(_ app: XCUIApplication) {
        let row = app.buttons["invites.profile"]
        XCTAssertTrue(row.waitForExistence(timeout: 10))
        row.tap()
        XCTAssertTrue(app.buttons["invites.personal"].waitForExistence(timeout: 5))
    }

    private func enter(_ code: String, in app: XCUIApplication) {
        let field = app.textFields["release.inviteGate.code"]
        XCTAssertTrue(field.waitForExistence(timeout: 5))
        let predicate = NSPredicate(format: "isEnabled == true")
        XCTAssertEqual(XCTWaiter.wait(for: [XCTNSPredicateExpectation(predicate: predicate, object: field)], timeout: 5), .completed)
        field.tap()
        let existing = (field.value as? String) ?? ""
        field.typeText(String(repeating: XCUIKeyboardKey.delete.rawValue, count: existing.count) + code + "\n")
    }

    private func dismissKeyboard(_ app: XCUIApplication) {
        if app.keyboards.count > 0 { app.swipeDown() }
    }

    private func element(_ app: XCUIApplication, _ identifier: String) -> XCUIElement {
        app.descendants(matching: .any).matching(identifier: identifier).firstMatch
    }

    private func capture(_ app: XCUIApplication, _ name: String) {
        let attachment = XCTAttachment(screenshot: app.screenshot())
        attachment.name = name; attachment.lifetime = .keepAlways; add(attachment)
    }
}
