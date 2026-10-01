import SwiftUI

struct CanvasProfileDraft {
    let emailAddress = "alex@example.com"
    var name = "Alex Rivera"
    var preferredName = "Alex"
    var currency = "DOP"
    var responseLength = 0
    var tone = 0
    var instructions = ""
    var push = false
    var email = false
    var budgets = true
    var goals = true
    var payments = true
    var records = true
    var household = true
    var quietHours = false
}

enum CanvasProfileRoute: Hashable {
    case personal, preferences, personalization, notifications, security, privacy, usage, help
    case memory, files, conversations, shared, removed, voice, advanced
    func title(_ es: Bool) -> String {
        switch self {
        case .personal: es ? "Mi perfil" : "My profile"
        case .preferences: es ? "Preferencias" : "Preferences"
        case .personalization: es ? "Personalización" : "Personalization"
        case .notifications: es ? "Notificaciones" : "Notifications"
        case .security: es ? "Seguridad" : "Security"
        case .privacy: es ? "Datos y privacidad" : "Data and privacy"
        case .usage: es ? "Uso" : "Usage"
        case .help: es ? "Ayuda y comentarios" : "Help and feedback"
        case .memory: es ? "Memoria" : "Memory"
        case .files: es ? "Archivos" : "Files"
        case .conversations: es ? "Conversaciones" : "Conversations"
        case .shared: es ? "Conversaciones compartidas" : "Shared conversations"
        case .removed: es ? "Movimientos eliminados" : "Removed activity"
        case .voice: es ? "Voz" : "Voice"
        case .advanced: es ? "Más opciones" : "More options"
        }
    }
    var symbol: String {
        switch self {
        case .personal: "person"
        case .preferences: "slider.horizontal.3"
        case .personalization: "sparkle"
        case .notifications: "bell"
        case .security: "lock"
        case .privacy: "hand.raised"
        case .usage: "chart.bar"
        case .help: "questionmark.circle"
        case .memory: "brain"
        case .files: "doc"
        case .conversations: "bubble.left.and.bubble.right"
        case .shared: "link"
        case .removed: "trash"
        case .voice: "waveform"
        case .advanced: "ellipsis"
        }
    }
}

struct CuadraoProfileCanvas: View {
    let spanish: Bool
    let includeExamples: Bool
    @State private var profile = CanvasProfileDraft()
    @State private var signOut = false

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 28) {
                    NavigationLink(value: CanvasProfileRoute.personal) {
                        HStack(spacing: 16) {
                            Text(String(profile.name.prefix(1)).uppercased())
                                .font(.title2.weight(.medium)).frame(width: 58, height: 58)
                                .foregroundStyle(WelcomePalette.pine)
                                .background(WelcomePalette.sage, in: Circle())
                            VStack(alignment: .leading, spacing: 5) {
                                Text(profile.name).font(.title3.weight(.semibold))
                                Text(profile.emailAddress).font(.subheadline).foregroundStyle(.secondary)
                            }
                            Spacer(minLength: 8)
                            Image(systemName: "chevron.right").font(.caption).foregroundStyle(.tertiary)
                        }.padding(.vertical, 8).contentShape(Rectangle())
                    }.buttonStyle(.plain).accessibilityIdentifier("cuadrao.profile.identity")
                    group("App", routes: [.preferences, .personalization, .notifications])
                    group(spanish ? "Cuenta" : "Account", routes: [.security, .privacy, .usage])
                    group(spanish ? "Ayuda" : "Support", routes: [.help])
                    Button(spanish ? "Cerrar sesión" : "Sign out") { signOut = true }
                        .font(.body).foregroundStyle(.secondary).frame(minHeight: 44)
                        .accessibilityIdentifier("cuadrao.profile.signout")
                }.padding(.horizontal, 24).padding(.top, 24).padding(.bottom, 24)
            }
            .background(Color.white).toolbar(.hidden, for: .navigationBar)
            .navigationDestination(for: CanvasProfileRoute.self) { route in
                if route == .personal {
                    CuadraoProfileEditor(profile: $profile, spanish: spanish)
                } else {
                    CuadraoProfilePage(route: route, profile: $profile, spanish: spanish, includeExamples: includeExamples)
                }
            }
            .alert(spanish ? "Cerrar sesión" : "Sign out", isPresented: $signOut) {
                Button(spanish ? "Entendido" : "Got it", role: .cancel) {}
            } message: {
                Text(spanish ? "Esta vista previa no tiene una sesión conectada. Tu sesión de Argus sigue abierta."
                     : "This preview has no connected session. Your Argus session remains signed in.")
            }
        }.toolbar(.hidden, for: .tabBar)
    }

    private func group(_ title: String, routes: [CanvasProfileRoute]) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title).font(.caption).foregroundStyle(.secondary).accessibilityAddTraits(.isHeader)
            ForEach(routes, id: \.self) { route in
                NavigationLink(value: route) { CanvasProfileRow(route: route, spanish: spanish) }
                    .buttonStyle(.plain)
                if route != routes.last { Divider().padding(.leading, 40) }
            }
        }
    }
}

struct CanvasProfileRow: View {
    let route: CanvasProfileRoute
    let spanish: Bool
    var body: some View {
        HStack(spacing: 16) {
            Group {
                if route == .notifications {
                    Image("CuadraoNotifications").resizable().scaledToFit()
                } else {
                    Image(systemName: route.symbol).font(.system(size: 20, weight: .regular))
                }
            }.frame(width: 24, height: 24).foregroundStyle(.secondary).accessibilityHidden(true)
            Text(route.title(spanish)).font(.body)
            Spacer(minLength: 8)
            Image(systemName: "chevron.right").font(.caption).foregroundStyle(.tertiary).accessibilityHidden(true)
        }.frame(minHeight: 48).contentShape(Rectangle())
    }
}

struct CuadraoProfileEditor: View {
    @Binding var profile: CanvasProfileDraft
    let spanish: Bool
    @Environment(\.dismiss) private var dismiss
    @State private var name: String
    @State private var preferred: String

    init(profile: Binding<CanvasProfileDraft>, spanish: Bool) {
        _profile = profile; self.spanish = spanish
        _name = State(initialValue: profile.wrappedValue.name)
        _preferred = State(initialValue: profile.wrappedValue.preferredName)
    }
    private var valid: Bool {
        !name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && name.count <= 60 && preferred.count <= 40
    }
    var body: some View {
        Form {
            Section {
                TextField(spanish ? "Nombre" : "Name", text: $name).textContentType(.name)
                    .accessibilityIdentifier("cuadrao.profile.name")
                TextField(spanish ? "Cómo te llamamos" : "What we call you", text: $preferred)
                    .accessibilityIdentifier("cuadrao.profile.preferred")
            } header: { Text(spanish ? "Tus datos" : "Your details") }
            Section {
                LabeledContent(spanish ? "Correo" : "Email", value: profile.emailAddress)
            }
            if !valid {
                Text(spanish ? "Escribe un nombre de hasta 60 caracteres y un nombre preferido de hasta 40."
                     : "Enter a name up to 60 characters and a preferred name up to 40.")
                    .font(.footnote).foregroundStyle(.secondary)
            }
        }.scrollContentBackground(.hidden).background(Color.white)
            .navigationTitle(spanish ? "Mi perfil" : "My profile").navigationBarTitleDisplayMode(.inline)
            .toolbar(.visible, for: .navigationBar)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button(spanish ? "Guardar" : "Save") {
                        profile.name = name.trimmingCharacters(in: .whitespacesAndNewlines)
                        profile.preferredName = preferred.trimmingCharacters(in: .whitespacesAndNewlines)
                        dismiss()
                    }.disabled(!valid)
                }
            }
    }
}
