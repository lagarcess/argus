import SwiftUI

/// The welcome screen's one brand composition: Marketing's mark-and-wordmark lockup, unchanged.
/// Light and dark artwork come from the asset catalog; it is drawn for the paper colours below.
struct CuadraoWelcomeLockup: View {
    /// Wide enough to read as the main mark, and it narrows on small screens rather than clipping.
    static let width: CGFloat = 268

    var body: some View {
        Image("CuadraoLockup")
            .resizable()
            .scaledToFit()
            .frame(maxWidth: Self.width)
            .accessibilityLabel("cuadrao")
            .accessibilityIdentifier("cuadrao.welcome.lockup")
    }
}

extension WelcomePalette {
    /// The website's page colours: #fafbf8 paper on light, #172b26 ink on dark. The welcome screen uses them
    /// because the dark lockup is drawn for #172b26 and changes tone on any other dark.
    static let brandPaper = adaptiveBrand(light: UIColor(red: 0xfa / 255, green: 0xfb / 255, blue: 0xf8 / 255, alpha: 1),
                                          dark: UIColor(red: 0x17 / 255, green: 0x2b / 255, blue: 0x26 / 255, alpha: 1))

    private static func adaptiveBrand(light: UIColor, dark: UIColor) -> Color {
        Color(uiColor: UIColor { $0.userInterfaceStyle == .dark ? dark : light })
    }
}
