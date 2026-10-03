import XCTest

/// Integration builds keep `CUADRAO_DESIGN_PREVIEW = false`, so design-preview journeys opt in
/// on every launch. These three arguments reproduce what a standalone preview build implies:
/// the design gate (`CuadraoDesignPreview.isActive`), the Home canvas and populated sample data.
/// Tests that need a first-use state reset it through the preview's own controls or arguments
/// (`--plan-empty`, `--insights-first-use`), exactly as they did in a standalone build.
enum CuadraoPreviewLaunch {
    static let arguments = ["--cuadrao-design", "--cuadrao-home", "--home-populated"]
    /// Voice selection has its own default-off switch while the sample clips stay out.
    static let voiceSelection = "--cuadrao-voice-selection"
}

extension XCUIApplication {
    /// An app whose next `launch()` opens the design preview's populated Home.
    static func cuadraoPreview() -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments = CuadraoPreviewLaunch.arguments
        return app
    }
}
