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
    @StateObject private var auth = ProfileAuthModel()
    @Environment(\.scenePhase) private var scenePhase
    @AppStorage(AppearancePreference.storageKey) private var appearance = AppearancePreference.system
    @AppStorage(CuadraoAppearancePicker.storageKey) private var previewAppearance = AppearancePreference.light

    var body: some Scene {
        WindowGroup {
            if CuadraoCanvas.standalonePreview || ProcessInfo.processInfo.arguments.contains("--cuadrao-design") {
                CuadraoCanvas()
                    .preferredColorScheme(previewAppearance.colorScheme)
            } else {
            FoundationShell(appearance: $appearance)
                .environmentObject(auth)
                .task { await auth.start() }
                .onChange(of: scenePhase) { _, phase in
                    if phase == .active { Task { await auth.restore() } }
                }
                .preferredColorScheme(appearance.colorScheme)
                .tint(ArgusStyle.ink)
                .foregroundStyle(ArgusStyle.ink)
                .font(ArgusStyle.body())
            }
        }
    }
}
