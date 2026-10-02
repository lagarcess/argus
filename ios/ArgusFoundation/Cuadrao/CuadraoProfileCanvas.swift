import SwiftUI

struct CanvasProfileDraft {
    let emailAddress = "alex@example.com"
    var name = "Alex Rivera"
    var preferredName = "Alex"
    var currency = "DOP"
    var avatar: CanvasProfileAvatarStyle = .initial
    var quietStart = Calendar.current.date(from: DateComponents(hour: 22)) ?? .now
    var quietEnd = Calendar.current.date(from: DateComponents(hour: 8)) ?? .now
    var responseLength = 0
    var tone = 0
    var instructions = ""
    var feedback = CanvasFeedbackDraft()
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
    case memory, files, conversations, shared, removed, voice, advanced, feedback
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
        case .feedback: es ? "Comentarios" : "Feedback"
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
        case .feedback: "bubble.left"
        }
    }
}

enum CanvasSettingsStyle {
    static let surface = WelcomePalette.surface
    static let separator = WelcomePalette.separator
}

struct CuadraoProfileCanvas: View {
    let spanish: Bool
    let includeExamples: Bool
    @Binding var profile: CanvasProfileDraft
    @Binding var path: [CanvasProfileRoute]
    let bottomSpace: CGFloat
    @Environment(\.dynamicTypeSize) private var typeSize
    @State private var signOut = false
    @State private var editor: CanvasProfileRoute?

    var body: some View {
        NavigationStack(path: $path) {
            ScrollView {
                VStack(alignment: .leading, spacing: 24) {
                    identity.padding(.bottom, 4)
                    group("App", routes: [.preferences, .personalization, .notifications])
                    group(spanish ? "Cuenta" : "Account", routes: [.security, .privacy, .usage])
                    group(spanish ? "Soporte" : "Support", routes: [.help])
                    Button(spanish ? "Cerrar sesión" : "Sign out") { signOut = true }
                        .font(.subheadline).foregroundStyle(.secondary)
                        .frame(maxWidth: .infinity, minHeight: 44)
                        .accessibilityIdentifier("cuadrao.profile.signout")
                }.padding(.horizontal, 24).padding(.top, 24).padding(.bottom, bottomSpace + 24)
            }
            .background(WelcomePalette.background).toolbar(.hidden, for: .navigationBar)
            .navigationDestination(for: CanvasProfileRoute.self) { route in
                CuadraoProfilePage(route: route, profile: $profile, spanish: spanish, includeExamples: includeExamples)
            }
            .sheet(item: $editor) { _ in
                NavigationStack { CuadraoProfileEditor(profile: $profile, spanish: spanish) }
                    .tint(WelcomePalette.pine)
            }
            .alert(spanish ? "Cerrar sesión" : "Sign out", isPresented: $signOut) {
                Button(spanish ? "Entendido" : "Got it", role: .cancel) {}
            } message: {
                Text(spanish ? "Esta vista previa no tiene una sesión conectada. Tu sesión de Argus sigue abierta."
                     : "This preview has no connected session. Your Argus session remains signed in.")
            }
        }.toolbar(.hidden, for: .tabBar)
    }

    private var identity: some View {
        Button { editor = .personal } label: {
            let layout = typeSize.isAccessibilitySize ? AnyLayout(VStackLayout(alignment: .leading, spacing: 18)) : AnyLayout(HStackLayout(spacing: 20))
            layout {
                CanvasProfileAvatar(name: profile.name, style: profile.avatar, size: 76)
                VStack(alignment: .leading, spacing: 6) {
                    Text(profile.name).font(.system(.title2, design: .default, weight: .semibold))
                        .foregroundStyle(.primary)
                    Text(profile.emailAddress).font(.subheadline).foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                    Text(spanish ? "Editar perfil" : "Edit profile")
                        .font(.subheadline.weight(.medium)).foregroundStyle(WelcomePalette.pine)
                        .padding(.top, 4)
                }
                Spacer(minLength: 0)
            }.contentShape(Rectangle())
        }.buttonStyle(.plain).accessibilityIdentifier("cuadrao.profile.identity")
    }

    private func group(_ title: String, routes: [CanvasProfileRoute]) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(title).font(.subheadline).foregroundStyle(.secondary).accessibilityAddTraits(.isHeader)
            VStack(spacing: 0) {
                ForEach(routes, id: \.self) { route in
                    NavigationLink(value: route) {
                        CanvasProfileRow(route: route, spanish: spanish)
                    }.buttonStyle(.plain).accessibilityIdentifier("cuadrao.profile.\(route)")
                    if route != routes.last {
                        Rectangle().fill(CanvasSettingsStyle.separator).frame(height: 0.5)
                            .padding(.leading, 54).padding(.trailing, 18).accessibilityHidden(true)
                    }
                }
            }.background(CanvasSettingsStyle.surface, in: RoundedRectangle(cornerRadius: 22))
        }
    }
}

extension CanvasProfileRoute: Identifiable {
    var id: Self { self }
}

struct CanvasProfileIcon: View {
    let route: CanvasProfileRoute
    var body: some View {
        Group {
            if route == .notifications {
                Image("CuadraoNotifications").resizable().scaledToFit()
            } else {
                Image(systemName: route.symbol).font(.system(size: 19, weight: .regular))
                    .environment(\.symbolVariants, .none)
            }
        }.frame(width: 22, height: 22).foregroundStyle(.secondary).accessibilityHidden(true)
    }
}

struct CanvasProfileRow: View {
    let route: CanvasProfileRoute
    let spanish: Bool
    var body: some View {
        HStack(spacing: 14) {
            CanvasProfileIcon(route: route)
            Text(route.title(spanish)).font(.body)
            Spacer(minLength: 8)
            Image(systemName: "chevron.right").font(.system(size: 12, weight: .semibold))
                .foregroundStyle(.tertiary).accessibilityHidden(true)
        }.padding(.horizontal, 18).padding(.vertical, 16)
            .frame(minHeight: 56).contentShape(Rectangle())
    }
}

struct CuadraoProfileEditor: View {
    @Binding var profile: CanvasProfileDraft
    let spanish: Bool
    @Environment(\.dismiss) private var dismiss
    @State private var name: String
    @State private var preferred: String
    @State private var avatar: CanvasProfileAvatarStyle
    @State private var photoLoading = false

    init(profile: Binding<CanvasProfileDraft>, spanish: Bool) {
        _profile = profile; self.spanish = spanish
        _name = State(initialValue: profile.wrappedValue.name)
        _preferred = State(initialValue: profile.wrappedValue.preferredName)
        _avatar = State(initialValue: profile.wrappedValue.avatar)
    }
    private var valid: Bool {
        !name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && name.count <= 60 && preferred.count <= 40
    }
    private var changed: Bool {
        name.trimmingCharacters(in: .whitespacesAndNewlines) != profile.name ||
        preferred.trimmingCharacters(in: .whitespacesAndNewlines) != profile.preferredName || avatar != profile.avatar
    }
    var body: some View {
        Form {
            Section {
                HStack { Spacer(); CanvasProfileAvatar(name: name, style: avatar); Spacer() }
                    .padding(.vertical, 12).listRowBackground(Color.clear)
            }
            CuadraoProfileAvatarPicker(name: name, spanish: spanish, avatar: $avatar, loading: $photoLoading)
            Section {
                field(spanish ? "Nombre" : "Name", text: $name, id: "cuadrao.profile.name")
                    .textContentType(.name)
                field(spanish ? "Cómo te llamamos" : "What we call you", text: $preferred,
                      id: "cuadrao.profile.preferred")
                    .textContentType(.nickname)
            } footer: {
                Text(spanish ? "Usaremos tu nombre preferido al conversar contigo."
                     : "We’ll use your preferred name when we talk with you.")
            }.listRowBackground(CanvasSettingsStyle.surface)
            Section {
                VStack(alignment: .leading, spacing: 7) {
                    Text(spanish ? "Correo" : "Email").font(.subheadline).foregroundStyle(.secondary)
                    Text(profile.emailAddress)
                }.padding(.vertical, 6)
            }.listRowBackground(CanvasSettingsStyle.surface)
            if !valid {
                Text(spanish ? "Escribe un nombre de hasta 60 caracteres y un nombre preferido de hasta 40."
                     : "Enter a name up to 60 characters and a preferred name up to 40.")
                    .font(.footnote).foregroundStyle(.secondary).listRowBackground(Color.clear)
            }
        }.scrollContentBackground(.hidden).background(WelcomePalette.background)
            .navigationTitle(spanish ? "Editar perfil" : "Edit profile").navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button(spanish ? "Cancelar" : "Cancel") { dismiss() }.accessibilityIdentifier("cuadrao.profile.cancel")
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button(spanish ? "Guardar" : "Save") {
                        profile.name = name.trimmingCharacters(in: .whitespacesAndNewlines)
                        profile.preferredName = preferred.trimmingCharacters(in: .whitespacesAndNewlines)
                        profile.avatar = avatar
                        dismiss()
                    }.disabled(!valid || !changed || photoLoading).accessibilityIdentifier("cuadrao.profile.save")
                }
            }
    }
    private func field(_ label: String, text: Binding<String>, id: String) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(label).font(.subheadline).foregroundStyle(.secondary)
            TextField(label, text: text).accessibilityLabel(label).accessibilityIdentifier(id)
        }.padding(.vertical, 6)
    }
}
