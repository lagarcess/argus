import SwiftUI

/// Local visual states only. No account service, persistence, or outgoing requests.
struct CuadraoEmailRegistration: View {
    let spanish: Bool
    @State private var email: String
    @State private var password: String
    @State private var passwordVisible = false
    @State private var emailEdited = false
    @State private var submission: Submission
    @State private var showConfirmation = false
    @FocusState private var focus: Field?

    private enum Field: Hashable { case email, password, visiblePassword }
    private enum Submission: Equatable { case idle, submitting, offline }

    enum Fixture: String {
        case empty, filled, invalid, offline, loading

        static var launch: Fixture {
            let value = ProcessInfo.processInfo.arguments.first { $0.hasPrefix("--registration-state=") }
            return value.flatMap { Fixture(rawValue: String($0.dropFirst("--registration-state=".count))) } ?? .empty
        }
    }

    init(spanish: Bool, fixture: Fixture = .launch) {
        self.spanish = spanish
        _email = State(initialValue: fixture == .empty ? "" : fixture == .invalid ? "alex@" : "alex@example.com")
        _password = State(initialValue: fixture == .empty || fixture == .invalid ? "" : "Cuadrao-preview")
        _emailEdited = State(initialValue: fixture == .invalid)
        _submission = State(initialValue: fixture == .offline ? .offline : fixture == .loading ? .submitting : .idle)
    }

    private var normalizedEmail: String { PreviewEmail.normalized(email) }
    private var validEmail: Bool { PreviewEmail.isValid(email) }
    private var emailError: Bool { emailEdited && !email.isEmpty && !validEmail && focus != .email }
    private var passwordFocused: Bool { focus == .password || focus == .visiblePassword }
    private var canSubmit: Bool { validEmail && password.count >= 8 }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 32) {
                RegistrationHeading(
                    title: spanish ? "Empieza con\ntu correo." : "Start with\nyour email.",
                    detail: spanish ? "Lo usarás para entrar a Cuadrao." : "You’ll use it to sign in to Cuadrao.")
                VStack(alignment: .leading, spacing: 24) {
                    emailField
                    passwordField
                }
                if submission == .offline {
                    RegistrationNotice(
                        title: spanish ? "No pudimos conectar." : "We couldn’t connect.",
                        detail: spanish ? "Revisa tu conexión e inténtalo de nuevo. Tus datos siguen aquí."
                            : "Check your connection and try again. Your details are still here.")
                }
            }
            .padding(.horizontal, 28)
            .padding(.top, 24)
            .padding(.bottom, 24)
        }
        .scrollDismissesKeyboard(.interactively)
        .safeAreaInset(edge: .bottom, spacing: 0) {
            RegistrationButton(
                title: submission == .submitting
                    ? (spanish ? "Creando cuenta…" : "Creating account…")
                    : submission == .offline ? (spanish ? "Reintentar" : "Try again")
                    : (spanish ? "Crear cuenta" : "Create account"),
                busy: submission == .submitting, enabled: canSubmit) {
                    focus = nil
                    submission = .submitting
                }
                .accessibilityIdentifier("cuadrao.signup.submit")
                .padding(.horizontal, 28)
                .padding(.top, 16)
                .padding(.bottom, 20)
                .background(Color.white)
        }
        .background(Color.white.ignoresSafeArea())
        .foregroundStyle(Color(white: 0.08))
        .navigationTitle("")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar(.visible, for: .navigationBar)
        .navigationDestination(isPresented: $showConfirmation) {
            CuadraoEmailConfirmation(spanish: spanish, email: normalizedEmail)
        }
        .onChange(of: focus) { old, _ in
            if old == .email { emailEdited = true }
        }
        .task(id: submission) {
            guard submission == .submitting else { return }
            do { try await Task.sleep(for: .milliseconds(900)) } catch { return }
            guard !Task.isCancelled else { return }
            submission = .idle
            showConfirmation = true
        }
    }

    private var emailField: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(spanish ? "Correo electrónico" : "Email address").font(.subheadline.weight(.medium))
            TextField(spanish ? "nombre@ejemplo.com" : "name@example.com", text: $email)
                .keyboardType(.emailAddress)
                .textContentType(.emailAddress)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
                .focused($focus, equals: .email)
                .submitLabel(.next)
                .onSubmit { focus = passwordVisible ? .visiblePassword : .password }
                .modifier(RegistrationField(focused: focus == .email, invalid: emailError))
                .disabled(submission == .submitting)
                .accessibilityLabel(spanish ? "Correo electrónico" : "Email address")
                .accessibilityIdentifier("cuadrao.signup.emailField")
            if emailError {
                Label(spanish ? "Revisa el correo. Por ejemplo: nombre@ejemplo.com."
                      : "Check the email. For example: name@example.com.", systemImage: "exclamationmark.circle")
                    .font(.footnote).foregroundStyle(.red)
            }
        }
    }

    private var passwordField: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(spanish ? "Contraseña" : "Password").font(.subheadline.weight(.medium))
            HStack(spacing: 0) {
                Group {
                    if passwordVisible {
                        TextField(spanish ? "Crea una contraseña" : "Create a password", text: $password)
                            .focused($focus, equals: .visiblePassword)
                    } else {
                        SecureField(spanish ? "Crea una contraseña" : "Create a password", text: $password)
                            .focused($focus, equals: .password)
                    }
                }
                .textContentType(.newPassword)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
                .submitLabel(.done)
                .onSubmit { focus = nil }
                .accessibilityLabel(spanish ? "Contraseña" : "Password")
                .accessibilityIdentifier("cuadrao.signup.password")
                Button {
                    let wasFocused = passwordFocused
                    passwordVisible.toggle()
                    if wasFocused { focus = passwordVisible ? .visiblePassword : .password }
                } label: {
                    Image(systemName: passwordVisible ? "eye.slash" : "eye")
                        .foregroundStyle(.secondary)
                        .frame(width: 44, height: 44)
                        .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .accessibilityLabel(passwordVisible
                    ? (spanish ? "Ocultar contraseña" : "Hide password")
                    : (spanish ? "Mostrar contraseña" : "Show password"))
            }
            .modifier(RegistrationField(focused: passwordFocused))
            .disabled(submission == .submitting)
            Label(spanish ? "Al menos 8 caracteres" : "At least 8 characters",
                  systemImage: password.count >= 8 ? "checkmark.circle.fill" : "circle")
                .font(.footnote)
                .foregroundStyle(password.count >= 8 ? WelcomePalette.pine : Color.secondary)
                .accessibilityLabel(password.count >= 8
                    ? (spanish ? "Longitud de contraseña suficiente" : "Password length met")
                    : (spanish ? "Se requieren al menos 8 caracteres" : "At least 8 characters required"))
        }
    }
}

#Preview("Email · Empty") {
    NavigationStack { CuadraoEmailRegistration(spanish: true, fixture: .empty) }
}
#Preview("Email · Invalid") {
    NavigationStack { CuadraoEmailRegistration(spanish: true, fixture: .invalid) }
}
#Preview("Email · Recovery") {
    NavigationStack { CuadraoEmailRegistration(spanish: true, fixture: .offline) }
}
#Preview("Email · English") {
    NavigationStack { CuadraoEmailRegistration(spanish: false, fixture: .filled) }
}
