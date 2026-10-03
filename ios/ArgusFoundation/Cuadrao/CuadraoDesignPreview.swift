import Foundation

/// The one design-preview switch, default off. The canvas sets it with `--cuadrao-design`
/// (or a build whose Info.plist sets `CUADRAO_DESIGN_PREVIEW` to `true`). Preview-only
/// appearance, local persistence and location requests check it; Connected launches never do.
enum CuadraoDesignPreview {
    static let isActive = ProcessInfo.processInfo.arguments.contains("--cuadrao-design")
        || Bundle.main.object(forInfoDictionaryKey: "CUADRAO_DESIGN_PREVIEW") as? String == "true"
}
