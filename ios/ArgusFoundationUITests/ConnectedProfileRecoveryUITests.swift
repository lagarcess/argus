import XCTest

extension FinancialLoopUITests {
    func testConnectedProfileUsesRealIdentityAndApprovedDestinations() throws {
        try signIn()
        app.openProfileSurface()
        let email = try XCTUnwrap(ProcessInfo.processInfo.environment["ARGUS_TEST_EMAIL"])
        let identity = app.buttons["cuadrao.profile.identity"]
        XCTAssertTrue(identity.waitForExistence(timeout: 5))
        XCTAssertTrue(identity.label.contains(email))
        XCTAssertFalse(identity.label.contains("alex@example.com"))
        for route in ["preferences", "personalization", "notifications", "security", "privacy", "usage", "help"] {
            XCTAssertTrue(app.buttons["cuadrao.profile." + route].exists, route)
        }
        capture("connected-profile-full-groups")

        tapVisible(identity)
        XCTAssertTrue(app.buttons["cuadrao.profile.photo.choose"].waitForExistence(timeout: 5))
        XCTAssertFalse(app.textFields["cuadrao.profile.name"].isEnabled)
        tapVisible(app.buttons["cuadrao.profile.avatar.moon"])
        app.buttons["cuadrao.profile.save"].tap()
        XCTAssertTrue(identity.waitForExistence(timeout: 5))
        XCTAssertTrue(identity.label.contains(email))

        tapVisible(app.buttons["cuadrao.profile.preferences"])
        XCTAssertTrue(app.navigationBars["Preferences"].waitForExistence(timeout: 5))
        XCTAssertFalse(app.buttons["tab.home"].exists)
        XCTAssertTrue(app.descendants(matching: .any)["cuadrao.profile.development"].exists)
        for appearance in ["light", "dark", "system"] {
            let choice = app.buttons["cuadrao.appearance." + appearance]
            tapVisible(choice)
            XCTAssertTrue(choice.isSelected)
        }
        app.navigationBars.buttons.firstMatch.tap()
        XCTAssertTrue(app.buttons["tab.home"].waitForExistence(timeout: 5))

        tapVisible(app.buttons["cuadrao.profile.privacy"])
        tapVisible(app.buttons["Files"])
        XCTAssertTrue(app.navigationBars["Files"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.descendants(matching: .any)["cuadrao.profile.development"].exists)
        XCTAssertFalse(app.buttons["tab.home"].exists)
        app.navigationBars.buttons.firstMatch.tap()
        XCTAssertTrue(app.navigationBars["Data and privacy"].waitForExistence(timeout: 5))
        app.navigationBars.buttons.firstMatch.tap()
        XCTAssertTrue(app.buttons["tab.home"].waitForExistence(timeout: 5))

        tapVisible(app.buttons["cuadrao.profile.help"])
        XCTAssertTrue(app.descendants(matching: .any)["release.legal.terms"].exists)
        XCTAssertTrue(app.descendants(matching: .any)["release.legal.privacy"].exists)
        tapVisible(app.buttons["Feedback"])
        XCTAssertTrue(app.navigationBars["Feedback"].waitForExistence(timeout: 5))
        XCTAssertFalse(app.buttons["tab.home"].exists)
        app.navigationBars.buttons.firstMatch.tap()
        app.navigationBars.buttons.firstMatch.tap()
        tapVisible(app.buttons["auth.signOut"])
        XCTAssertTrue(app.buttons["cuadrao.welcome.signin"].waitForExistence(timeout: 20))
    }

    func testConnectedProfileReleaseGatesKeepSupportedSettings() throws {
        try signIn()
        app.terminate()
        app.launchArguments.append("--cuadrao-release-gates")
        app.launch()
        app.openProfileSurface()
        XCTAssertTrue(app.descendants(matching: .any)["release.profile.display"].waitForExistence(timeout: 10))
        XCTAssertFalse(app.buttons["cuadrao.profile.identity"].exists)
        for route in ["personalization", "security", "usage"] {
            XCTAssertFalse(app.buttons["cuadrao.profile." + route].exists, route)
        }
        for route in ["preferences", "notifications", "privacy", "help"] {
            XCTAssertTrue(app.buttons["cuadrao.profile." + route].exists, route)
        }
        tapVisible(app.buttons["cuadrao.profile.privacy"])
        for title in ["Memory", "Shared conversations", "Removed activity"] {
            XCTAssertFalse(app.buttons[title].exists, title)
        }
        XCTAssertTrue(app.buttons["Files"].exists)
        XCTAssertTrue(app.buttons["Conversations"].exists)
        app.navigationBars.buttons.firstMatch.tap()
        tapVisible(app.buttons["cuadrao.profile.preferences"])
        XCTAssertFalse(app.buttons["More options"].exists)
        XCTAssertTrue(app.buttons["cuadrao.appearance.light"].exists)
        capture("connected-profile-release-gates")
    }
}
