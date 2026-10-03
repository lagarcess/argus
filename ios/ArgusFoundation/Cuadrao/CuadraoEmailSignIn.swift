import SwiftUI

/// Disconnected visual proposal. Typed values never leave this view hierarchy.
struct CuadraoEmailSignIn: View {
    let spanish: Bool
    @State private var email: String
    @State private var password: String
    @State private var visible = false
    @State private var emailEdited = false
    @State private var state: StateKind
    @State private var recovery = false
    @State private var previewComplete = false
    @FocusState private var focus: Field?
    private enum Field: Hashable { case email, password, visiblePassword }
    private enum StateKind: Equatable { case idle, loading, rejected, offline }

    enum Fixture: String {
        case empty, filled, rejected, offline
        static var launch: Fixture {
            let argument = ProcessInfo.processInfo.arguments.first { $0.hasPrefix("--signin-state=") }
            return argument.flatMap { Fixture(rawValue: String($0.dropFirst("--signin-state=".count))) } ?? .empty
        }
    }

    init(spanish: Bool, initialEmail: String = "", fixture: Fixture = .launch) {
        self.spanish = spanish
        _email = State(initialValue: initialEmail.isEmpty && fixture != .empty ? "alex@example.com" : initialEmail)
        _password = State(initialValue: fixture == .empty ? "" : "Cuadrao-preview")
        _state = State(initialValue: fixture == .rejected ? .rejected : fixture == .offline ? .offline : .idle)
    }

    private var ready: Bool { PreviewEmail.isValid(email) && !password.isEmpty }
    private var invalidEmail: Bool { emailEdited && !email.isEmpty && !PreviewEmail.isValid(email) && focus != .email }
    private var passwordFocused: Bool { focus == .password || focus == .visiblePassword }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 32) {
                RegistrationHeading(title: spanish ? "Inicia sesión." : "Sign in.",
                                    detail: spanish ? "Continúa donde te quedaste." : "Pick up where you left off.")
                VStack(alignment: .leading, spacing: 24) {
                    emailInput
                    passwordInput
                }
                if state == .rejected {
                    RegistrationNotice(symbol: "exclamationmark.circle",
                        title: spanish ? "No pudimos iniciar sesión." : "We couldn’t sign you in.",
                        detail: spanish ? "Revisa tu correo y contraseña, o recupera el acceso."
                            : "Check your email and password, or recover access.")
                } else if state == .offline {
                    RegistrationNotice(title: spanish ? "No pudimos conectar." : "We couldn’t connect.",
                        detail: spanish ? "Revisa tu conexión e inténtalo de nuevo. Tus datos siguen aquí."
                            : "Check your connection and try again. Your details are still here.")
                }
            }
            .padding(.horizontal, 28).padding(.vertical, 24)
        }
        .scrollDismissesKeyboard(.interactively)
        .safeAreaInset(edge: .bottom, spacing: 0) {
            RegistrationButton(title: state == .loading ? (spanish ? "Entrando…" : "Signing in…")
                               : state == .offline ? (spanish ? "Reintentar" : "Try again")
                               : (spanish ? "Iniciar sesión" : "Sign in"), busy: state == .loading, enabled: ready) {
                focus = nil
                state = .loading
            }
            .accessibilityIdentifier("cuadrao.signin.submit")
            .padding(.horizontal, 28).padding(.top, 16).padding(.bottom, 20)
            .background(WelcomePalette.background)
        }
        .background(WelcomePalette.background.ignoresSafeArea())
        .foregroundStyle(WelcomePalette.ink)
        .navigationTitle("").navigationBarTitleDisplayMode(.inline)
        .toolbar(.visible, for: .navigationBar)
        .onChange(of: focus) { old, _ in if old == .email { emailEdited = true } }
        .onChange(of: email) { _, _ in clearRejection() }
        .onChange(of: password) { _, _ in clearRejection() }
        .sheet(isPresented: $recovery) {
            NavigationStack { CuadraoPasswordRecovery(spanish: spanish, email: $email) }
                .tint(WelcomePalette.pine)
        }
        .task(id: state) {
            guard state == .loading else { return }
            do { try await Task.sleep(for: .milliseconds(800)) } catch { return }
            guard !Task.isCancelled else { return }
            state = .idle
            previewComplete = true
        }
        .alert(spanish ? "Vista previa" : "Design preview", isPresented: $previewComplete) {
            Button(spanish ? "Entendido" : "Got it", role: .cancel) {}
        } message: {
            Text(spanish ? "Aquí termina el diseño de acceso. No se envió información ni se inició una sesión."
                 : "The sign-in design ends here. No information was sent and no session was started.")
        }
    }

    private var emailInput: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(spanish ? "Correo electrónico" : "Email address").font(.subheadline.weight(.medium))
            TextField(spanish ? "nombre@ejemplo.com" : "name@example.com", text: $email)
                .textContentType(.username).keyboardType(.emailAddress)
                .textInputAutocapitalization(.never).autocorrectionDisabled()
                .focused($focus, equals: .email).submitLabel(.next)
                .onSubmit { focus = visible ? .visiblePassword : .password }
                .modifier(RegistrationField(focused: focus == .email, invalid: invalidEmail))
                .disabled(state == .loading)
                .accessibilityLabel(spanish ? "Correo electrónico" : "Email address")
                .accessibilityIdentifier("cuadrao.signin.email")
            if invalidEmail {
                Label(spanish ? "Revisa el formato del correo." : "Check the email format.", systemImage: "exclamationmark.circle")
                    .font(.footnote).foregroundStyle(.red)
            }
        }
    }

    private var passwordInput: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(spanish ? "Contraseña" : "Password").font(.subheadline.weight(.medium))
            HStack(spacing: 0) {
                Group {
                    if visible {
                        TextField(spanish ? "Tu contraseña" : "Your password", text: $password)
                            .focused($focus, equals: .visiblePassword)
                    } else {
                        SecureField(spanish ? "Tu contraseña" : "Your password", text: $password)
                            .focused($focus, equals: .password)
                    }
                }
                .textContentType(.password).textInputAutocapitalization(.never).autocorrectionDisabled()
                .submitLabel(.go)
                .onSubmit { if ready { focus = nil; state = .loading } }
                .accessibilityLabel(spanish ? "Contraseña" : "Password")
                .accessibilityIdentifier("cuadrao.signin.password")
                Button {
                    let wasFocused = passwordFocused
                    visible.toggle()
                    if wasFocused { focus = visible ? .visiblePassword : .password }
                } label: {
                    Image(systemName: visible ? "eye.slash" : "eye")
                        .foregroundStyle(.secondary).frame(width: 44, height: 44).contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .accessibilityLabel(visible ? (spanish ? "Ocultar contraseña" : "Hide password")
                                    : (spanish ? "Mostrar contraseña" : "Show password"))
            }
            .modifier(RegistrationField(focused: passwordFocused)).disabled(state == .loading)
            Button(spanish ? "¿Olvidaste tu contraseña?" : "Forgot password?") {
                focus = nil
                recovery = true
            }
            .font(.subheadline.weight(.medium)).foregroundStyle(WelcomePalette.pine)
            .frame(minHeight: 44).disabled(state == .loading)
            .accessibilityIdentifier("cuadrao.signin.recover")
        }
    }

    private func clearRejection() { if state == .rejected { state = .idle } }
}

#Preview("Sign in · Empty") { NavigationStack { CuadraoEmailSignIn(spanish: true, fixture: .empty) } }
#Preview("Sign in · Rejected") { NavigationStack { CuadraoEmailSignIn(spanish: true, fixture: .rejected) } }
#Preview("Sign in · Offline") { NavigationStack { CuadraoEmailSignIn(spanish: true, fixture: .offline) } }
#Preview("Sign in · English") { NavigationStack { CuadraoEmailSignIn(spanish: false, fixture: .filled) } }
