import Foundation

/// The one design-preview switch, default off. A build whose Info.plist sets
/// `CUADRAO_DESIGN_PREVIEW` to `true` turns it on; DEBUG builds also accept `--cuadrao-design`.
/// Preview-only appearance, local persistence and location requests check it; Connected launches never do.
enum CuadraoDesignPreview {
    /// A standalone preview build (`CUADRAO_DESIGN_PREVIEW = true` in its xcconfig) opens
    /// straight into the populated Home canvas. Integration's xcconfig keeps it `false`.
    static let standalone = Bundle.main.object(forInfoDictionaryKey: "CUADRAO_DESIGN_PREVIEW") as? String == "true"
    #if DEBUG
    static let isActive = ProcessInfo.processInfo.arguments.contains("--cuadrao-design") || standalone
    #else
    static let isActive = standalone
    #endif
    /// Voice selection plays bundled sample clips, which stay out until their licensing is settled.
    /// It has its own default-off switch inside the preview: `--cuadrao-voice-selection`.
    static let voiceSelection = isActive && ProcessInfo.processInfo.arguments.contains("--cuadrao-voice-selection")
}
