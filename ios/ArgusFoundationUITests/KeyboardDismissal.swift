import XCTest

extension XCUIApplication {
    /// Closes the keyboard the way a person does, by tapping away from the field. There is no Done control above the keyboard.
    func dismissKeyboard() {
        guard keyboards.firstMatch.exists else { return }
        let title = navigationBars.firstMatch.staticTexts.firstMatch
        if title.exists && title.isHittable { title.tap() } else { swipeDown() }
        _ = keyboards.firstMatch.waitForNonExistence(timeout: 3)
    }
}
