import SwiftUI

struct ReleaseNotificationPreferences: View {
    let permission: ReleasePushPermission
    let spanish: Bool
    let requestPermission: () -> Void
    let openSettings: () -> Void

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                Text(spanish ? "Lo importante, a tiempo" : "What matters, on time").font(CuadraoTypography.feature)
                Text(spanish ? "Recibe un aviso cuando una factura venza en 3 días y el día de su vencimiento. Tus novedades siguen en la app aunque no actives notificaciones."
                    : "Get a reminder 3 days before a bill is due and on its due date. Your updates stay in the app even if you don't enable notifications.")
                    .font(CuadraoTypography.body)
                VStack(alignment: .leading, spacing: 8) {
                    Label(spanish ? "Vista previa" : "Preview", systemImage: "bell").font(CuadraoTypography.caption)
                    Text(ReleaseSafePushCopy.title(spanish: spanish)).font(.body.weight(.semibold))
                    Text(ReleaseSafePushCopy.body(spanish: spanish)).font(CuadraoTypography.supporting)
                }.padding(20).frame(maxWidth: .infinity, alignment: .leading)
                    .background(WelcomePalette.surface, in: RoundedRectangle(cornerRadius: 20))
                    .accessibilityIdentifier("updates-safe-push-preview")
                Text(spanish ? "Los avisos no muestran montos, saldos, comercios ni nombres de documentos. No enviamos novedades por correo."
                    : "Notifications don't show amounts, balances, merchants or document names. We don't send updates by email.")
                    .font(CuadraoTypography.supporting).foregroundStyle(.secondary)
                switch permission {
                case .unavailable:
                    Text(spanish ? "Las notificaciones aún no están disponibles." : "Notifications aren't available yet.")
                case .notDetermined:
                    Button(spanish ? "Activar notificaciones" : "Enable notifications", action: requestPermission)
                        .frame(minHeight: 44).accessibilityIdentifier("updates-enable-push")
                case .requesting:
                    ProgressView(spanish ? "Esperando tu decisión…" : "Waiting for your choice…")
                case .authorized:
                    Label(spanish ? "Notificaciones permitidas" : "Notifications allowed", systemImage: "checkmark")
                    settingsButton
                case .denied:
                    Text(spanish ? "Las notificaciones están desactivadas. Puedes cambiarlas en Ajustes; tus novedades siguen aquí."
                        : "Notifications are off. You can change this in Settings; your updates remain here.")
                    settingsButton
                }
            }.frame(maxWidth: .infinity, alignment: .leading).padding(24)
        }.background(WelcomePalette.background).foregroundStyle(WelcomePalette.ink)
            .navigationTitle(spanish ? "Notificaciones" : "Notifications").navigationBarTitleDisplayMode(.inline)
    }
    private var settingsButton: some View {
        Button(spanish ? "Abrir Ajustes" : "Open Settings", action: openSettings)
            .frame(minHeight: 44).accessibilityIdentifier("updates-open-settings")
    }
}
