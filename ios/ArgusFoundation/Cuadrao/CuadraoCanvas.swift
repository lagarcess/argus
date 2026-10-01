import SwiftUI

enum WelcomePalette {
    static let pine = adaptive(UIColor(red: 0.16, green: 0.29, blue: 0.25, alpha: 1),
                               UIColor(red: 0.67, green: 0.83, blue: 0.75, alpha: 1))
    static let sage = adaptive(UIColor(red: 0.91, green: 0.93, blue: 0.91, alpha: 1),
                               UIColor(red: 0.17, green: 0.22, blue: 0.20, alpha: 1))
    static let overlap = adaptive(UIColor(red: 0.25, green: 0.38, blue: 0.33, alpha: 1),
                                  UIColor(red: 0.37, green: 0.53, blue: 0.44, alpha: 1))
    static let background = adaptive(.white, UIColor(white: 0.10, alpha: 1))
    static let surface = adaptive(UIColor(white: 0.965, alpha: 1), UIColor(white: 0.14, alpha: 1))
    static let ink = adaptive(UIColor(white: 0.08, alpha: 1), UIColor(white: 0.94, alpha: 1))
    static let onAccent = adaptive(.white, UIColor(red: 0.08, green: 0.15, blue: 0.12, alpha: 1))
    static let separator = Color(uiColor: .separator).opacity(0.45)
    static let border = Color(uiColor: .separator)

    private static func adaptive(_ light: UIColor, _ dark: UIColor) -> Color {
        Color(uiColor: UIColor { $0.userInterfaceStyle == .dark ? dark : light })
    }
}

/// The native visual canvas. Add only the UI elements selected during design review.
struct CuadraoCanvas: View {
    static var standalonePreview: Bool {
        Bundle.main.object(forInfoDictionaryKey: "CUADRAO_DESIGN_PREVIEW") as? String == "true"
    }

    private let language = "es"

    private var spanish: Bool { language == "es" }

    var body: some View {
        if Self.standalonePreview || ProcessInfo.processInfo.arguments.contains("--cuadrao-home") {
            CuadraoHomeCanvas()
        } else {
        NavigationStack {
            welcome
                .toolbar(.hidden, for: .navigationBar)
        }
        .tint(WelcomePalette.ink)
        }
    }

    private var welcome: some View {
        GeometryReader { geometry in
            ScrollView {
                VStack(spacing: 0) {
                    CuadraoBrand()
                    .padding(.top, 28)

                    Spacer(minLength: 32)

                    VStack(spacing: 32) {
                        WelcomeSquares()
                        Text(spanish ? "Tus finanzas,\nen orden." : "Your finances,\nin order.")
                            .font(.system(.largeTitle, design: .serif))
                            .lineSpacing(2)
                            .fixedSize(horizontal: false, vertical: true)
                            .multilineTextAlignment(.center)
                    }

                    Spacer(minLength: 40)

                    VStack(spacing: 12) {
                        NavigationLink {
                            CuadraoCreateAccount(spanish: spanish)
                        } label: {
                            Text(spanish ? "Crear cuenta" : "Create account")
                                .font(.system(.body, weight: .semibold))
                                .frame(maxWidth: .infinity, minHeight: 56)
                                .foregroundStyle(WelcomePalette.onAccent)
                                .background(WelcomePalette.pine, in: RoundedRectangle(cornerRadius: 16))
                        }.buttonStyle(.plain)

                        NavigationLink {
                            CuadraoCreateAccount(spanish: spanish, signingIn: true)
                        } label: {
                            Text(spanish ? "Iniciar sesión" : "Sign in")
                                .font(.system(.body, weight: .semibold))
                                .frame(maxWidth: .infinity, minHeight: 56)
                                .overlay {
                                    RoundedRectangle(cornerRadius: 16)
                                        .stroke(WelcomePalette.border, lineWidth: 1)
                                }
                        }.buttonStyle(.plain)
                    }.padding(.bottom, 28)
                }
                .padding(.horizontal, 28)
                .frame(minHeight: geometry.size.height, alignment: .topLeading)
            }.scrollIndicators(.hidden)
        }
        .background(WelcomePalette.background.ignoresSafeArea())
        .foregroundStyle(WelcomePalette.ink)

    }
}

/// The overlapping forms echo the provisional mark without fixing the final logo.
private struct WelcomeSquares: View {
    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 22)
                .fill(WelcomePalette.pine)
                .frame(width: 116, height: 116)
                .offset(x: 36, y: -36)
            RoundedRectangle(cornerRadius: 22)
                .fill(WelcomePalette.sage)
                .frame(width: 116, height: 116)
                .offset(x: -36, y: 36)
            RoundedRectangle(cornerRadius: 5)
                .fill(WelcomePalette.overlap)
                .frame(width: 44, height: 44)
        }
        .frame(maxWidth: .infinity)
        .frame(height: 208)
        .accessibilityHidden(true)
    }
}

#Preview("Cuadrao · Welcome") {
    CuadraoCanvas().preferredColorScheme(.light)
}
