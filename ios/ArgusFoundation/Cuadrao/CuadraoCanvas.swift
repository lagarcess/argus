import SwiftUI

enum WelcomePalette {
    /// Design-preview only (default off): dark-appearance tokens apply under `CuadraoDesignPreview`.
    /// Every other launch, including Connected Cuadrao, keeps the shipped light tokens exactly.
    static let adaptsToAppearance = CuadraoDesignPreview.isActive
        || ProcessInfo.processInfo.arguments.contains("--cuadrao-release-ui")

    static let pine = adaptive(Color(red: 0.16, green: 0.29, blue: 0.25),
                               UIColor(red: 0.16, green: 0.29, blue: 0.25, alpha: 1),
                               UIColor(red: 0.67, green: 0.83, blue: 0.75, alpha: 1))
    static let moneyInput = adaptive(Color(red: 0.18, green: 0.47, blue: 0.40),
                                     UIColor(red: 0.18, green: 0.47, blue: 0.40, alpha: 1),
                                     UIColor(red: 0.67, green: 0.83, blue: 0.75, alpha: 1))
    static let sage = adaptive(Color(red: 0.91, green: 0.93, blue: 0.91),
                               UIColor(red: 0.91, green: 0.93, blue: 0.91, alpha: 1),
                               UIColor(red: 0.17, green: 0.22, blue: 0.20, alpha: 1))
    static let overlap = adaptive(Color(red: 0.25, green: 0.38, blue: 0.33),
                                  UIColor(red: 0.25, green: 0.38, blue: 0.33, alpha: 1),
                                  UIColor(red: 0.37, green: 0.53, blue: 0.44, alpha: 1))
    static let sunshine = Color(red: 0.67, green: 0.43, blue: 0.13)
    static let bloom = Color(red: 0.48, green: 0.40, blue: 0.64)
    static let owedNegative = adaptive(Color(red: 0.68, green: 0.36, blue: 0.26),
                                       UIColor(red: 0.68, green: 0.36, blue: 0.26, alpha: 1),
                                       UIColor(red: 0.94, green: 0.63, blue: 0.48, alpha: 1))
    static let clay = Color(red: 0.68, green: 0.36, blue: 0.26)
    static let background = adaptive(Color.white, .white, UIColor(white: 0.10, alpha: 1))
    static let surface = adaptive(Color(white: 0.965), UIColor(white: 0.965, alpha: 1), UIColor(white: 0.14, alpha: 1))
    static let ink = adaptive(Color(white: 0.08), UIColor(white: 0.08, alpha: 1), UIColor(white: 0.94, alpha: 1))
    static let onAccent = adaptive(Color.white, .white, UIColor(red: 0.08, green: 0.15, blue: 0.12, alpha: 1))
    static let separator: Color = adaptsToAppearance ? Color(uiColor: .separator).opacity(0.45) : Color(white: 0.85)
    static let border: Color = adaptsToAppearance ? Color(uiColor: .separator) : Color(white: 0.80)
    static let disabledInk: Color = adaptsToAppearance ? Color.secondary : Color(white: 0.43)

    /// `fixed` is the shipped token; `light`/`dark` resolve by trait only in the design preview.
    private static func adaptive(_ fixed: Color, _ light: UIColor, _ dark: UIColor) -> Color {
        guard adaptsToAppearance else { return fixed }
        return Color(uiColor: UIColor { $0.userInterfaceStyle == .dark ? dark : light })
    }
}

/// The native visual canvas. Add only the UI elements selected during design review.
struct CuadraoCanvas: View {
    private let language = "es"

    private var spanish: Bool { language == "es" }

    var body: some View {
        if ProcessInfo.processInfo.arguments.contains("--cuadrao-home") {
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
                            .font(CuadraoTypography.screen)
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
struct WelcomeSquares: View {
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
