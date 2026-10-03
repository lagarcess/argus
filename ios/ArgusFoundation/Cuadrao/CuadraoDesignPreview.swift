import Foundation

/// The one design-preview switch, default off. The canvas sets it with `--cuadrao-design`
/// (or a build whose Info.plist sets `CUADRAO_DESIGN_PREVIEW` to `true`). Preview-only
/// appearance, local persistence and location requests check it; Connected launches never do.
enum CuadraoDesignPreview {
    /// A standalone preview build (`CUADRAO_DESIGN_PREVIEW = true` in its xcconfig) opens
    /// straight into the populated Home canvas. Integration's xcconfig keeps it `false`.
    static let standalone = Bundle.main.object(forInfoDictionaryKey: "CUADRAO_DESIGN_PREVIEW") as? String == "true"
    static let isActive = ProcessInfo.processInfo.arguments.contains("--cuadrao-design") || standalone
}
