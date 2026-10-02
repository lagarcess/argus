import SwiftUI

enum WelcomePalette {
    static let pine = Color(red: 0.16, green: 0.29, blue: 0.25)
    static let sage = Color(red: 0.91, green: 0.93, blue: 0.91)
    static let overlap = Color(red: 0.25, green: 0.38, blue: 0.33)
    static let sunshine = Color(red: 0.67, green: 0.43, blue: 0.13)
    static let bloom = Color(red: 0.48, green: 0.40, blue: 0.64)
    static let clay = Color(red: 0.68, green: 0.36, blue: 0.26)
    /// Preview surfaces only; Connected keeps tip appearance tokens.
    static let background = Color.white
    static let surface = Color(white: 0.965)
    static let ink = Color(white: 0.08)
    static let onAccent = Color.white
    static let separator = Color(white: 0.85)
    static let border = Color(white: 0.80)
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
        .tint(Color(white: 0.08))
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
                                .foregroundStyle(.white)
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
                                        .stroke(Color(white: 0.80), lineWidth: 1)
                                }
                        }.buttonStyle(.plain)
                    }.padding(.bottom, 28)
                }
                .padding(.horizontal, 28)
                .frame(minHeight: geometry.size.height, alignment: .topLeading)
            }.scrollIndicators(.hidden)
        }
        .background(Color.white.ignoresSafeArea())
        .foregroundStyle(Color(white: 0.08))

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
