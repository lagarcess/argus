import SwiftUI

enum AppearancePreference: String, CaseIterable {
    case light, dark, system

    static let storageKey = "appearancePreference"

    var colorScheme: ColorScheme? {
        switch self {
        case .light: .light
        case .dark: .dark
        case .system: nil
        }
    }

    var title: LocalizedStringKey { LocalizedStringKey("appearance." + rawValue) }
}

@main
struct ArgusFoundationApp: App {
    @AppStorage(AppearancePreference.storageKey) private var appearance = AppearancePreference.system

    var body: some Scene {
        WindowGroup {
            FoundationShell(appearance: $appearance)
                .preferredColorScheme(appearance.colorScheme)
                .tint(ArgusStyle.ink)
                .foregroundStyle(ArgusStyle.ink)
                .font(ArgusStyle.body())
        }
    }
}
