import XCTest

final class FoundationUITests: XCTestCase {
    private let app = XCUIApplication()
    private let destinations = ["home", "accounts", "argus", "plan", "search"]

    override func setUpWithError() throws {
        continueAfterFailure = false
        XCUIDevice.shared.orientation = .portrait
        app.launchArguments = ["-AppleLanguages", "(en)", "-AppleLocale", "en_US"]
        app.launch()
    }

    func testNavigationAndHeaderReturn() throws {
        var previousTabX: CGFloat = -1
        for destination in destinations {
            let tab = app.buttons["tab.\(destination)"]
            XCTAssertTrue(tab.waitForExistence(timeout: 5))
            XCTAssertFalse(tab.label.isEmpty)
            XCTAssertGreaterThanOrEqual(tab.frame.width, 44)
            XCTAssertGreaterThanOrEqual(tab.frame.height, 44)
            XCTAssertGreaterThan(tab.frame.midX, previousTabX)
            previousTabX = tab.frame.midX
            tab.tap()
            XCTAssertTrue(tab.isSelected)
            XCTAssertTrue(app.descendants(matching: .any)["screen.\(destination)"].exists)
            XCTAssertTrue(app.staticTexts["sample.notice"].exists)
            if destination == "plan" {
                for section in ["overview", "goals", "budgets", "debts"] {
                    let button = app.buttons["plan.\(section)"]
                    // Accessibility frames cross pixel/point conversions.
                    XCTAssertGreaterThanOrEqual(button.frame.width + 0.000_001, 44)
                    XCTAssertGreaterThanOrEqual(button.frame.height, 44)
                }
            }
            capture(destination)
        }
        app.buttons["tab.home"].tap()
        app.buttons["header.updates"].tap()
        XCTAssertTrue(app.buttons["sheet.close"].waitForExistence(timeout: 3))
        capture("updates")
        app.buttons["sheet.close"].tap()
        XCTAssertTrue(app.buttons["tab.home"].isSelected)
        app.buttons["tab.argus"].tap()
        for entry in ["header.recents", "header.temporary"] {
            app.buttons[entry].tap()
            XCTAssertTrue(app.buttons["sheet.close"].waitForExistence(timeout: 3))
            app.buttons["sheet.close"].tap()
            XCTAssertTrue(app.buttons["tab.argus"].isSelected)
        }
    }

    func testDarkNavigation() throws {
        openPreferences()
        app.buttons["appearance.dark"].tap()
        app.buttons["sheet.close"].tap()
        for destination in destinations {
            app.buttons["tab.\(destination)"].tap()
            XCTAssertTrue(app.buttons["tab.\(destination)"].isSelected)
            capture("dark-\(destination)")
            if destination == "home" {
                // Prove the final section can scroll clear of the floating navigation.
                app.scrollViews["screen.home"].swipeUp()
                capture("dark-home-scrolled")
            }
            if destination == "search" {
                try app.performAccessibilityAudit(for: .contrast)
            }
        }
        openPreferences()
        app.buttons["appearance.system"].tap()
    }

    func testAppearancePersistsAcrossRelaunch() {
        for appearance in ["light", "dark", "system"] {
            openPreferences()
            app.buttons["appearance.\(appearance)"].tap()
            XCTAssertTrue(app.buttons["appearance.\(appearance)"].isSelected)
            if appearance != "system" {
                XCTAssertEqual(app.staticTexts["appearance.resolved"].value as? String, appearance)
            }
            capture("appearance-\(appearance)")
            app.terminate()
            app.launch()
            openPreferences()
            XCTAssertTrue(app.buttons["appearance.\(appearance)"].isSelected)
            if appearance != "system" {
                XCTAssertEqual(app.staticTexts["appearance.resolved"].value as? String, appearance)
            }
            app.buttons["sheet.close"].tap()
            capture("persisted-\(appearance)")
        }
    }

    func testSearchStateSurvivesTabSwitchAndKeyboard() {
        app.buttons["tab.search"].tap()
        let field = app.textFields["search.field"]
        XCTAssertTrue(field.waitForExistence(timeout: 3))
        field.tap()
        field.typeText("cash")
        capture("search-keyboard")
        app.buttons["tab.accounts"].tap()
        app.buttons["tab.search"].tap()
        XCTAssertEqual(field.value as? String, "cash")
        capture("search-retained")
    }

    func testSpanishLargeTextAndAccessibility() throws {
        app.terminate()
        app.launchArguments = [
            "-AppleLanguages", "(es-419)", "-AppleLocale", "es_419",
            "-UIPreferredContentSizeCategoryName", "UICTContentSizeCategoryAccessibilityXXXL"
        ]
        app.launch()
        XCTAssertEqual(app.buttons["tab.home"].label, "Inicio")
        for destination in destinations {
            app.buttons["tab.\(destination)"].tap()
            XCTAssertTrue(app.buttons["tab.\(destination)"].isHittable)
            capture("spanish-large-\(destination)")
            try app.performAccessibilityAudit(for: [.hitRegion, .sufficientElementDescription, .trait])
        }
        openPreferences()
        capture("spanish-large-preferences")
    }

    private func openPreferences() {
        app.buttons["tab.home"].tap()
        app.buttons["header.profile"].tap()
        XCTAssertTrue(app.buttons["profile.preferences"].waitForExistence(timeout: 3))
        app.buttons["profile.preferences"].tap()
        XCTAssertTrue(app.buttons["appearance.system"].waitForExistence(timeout: 3))
    }

    private func capture(_ name: String) {
        let attachment = XCTAttachment(screenshot: app.screenshot())
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
    }
}
