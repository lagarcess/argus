import SwiftUI

struct CuadraoProfilePage: View {
    let route: CanvasProfileRoute
    @Binding var profile: CanvasProfileDraft
    let spanish: Bool
    let includeExamples: Bool
    @State private var notice: String?

    var body: some View {
        Group {
            if route == .feedback {
                CuadraoFeedbackPage(saved: $profile.feedback, spanish: spanish)
            } else {
                Form { content.listRowBackground(CanvasSettingsStyle.surface) }
            }
        }
            .environment(\.defaultMinListRowHeight, 52)
            .scrollContentBackground(.hidden).background(WelcomePalette.background)
            .navigationTitle(route.title(spanish)).navigationBarTitleDisplayMode(.large)
            .toolbar(.visible, for: .navigationBar)
            .alert(notice ?? "", isPresented: Binding(get: { notice != nil }, set: { if !$0 { notice = nil } })) {
                Button(spanish ? "Entendido" : "Got it", role: .cancel) { notice = nil }
            } message: {
                Text(spanish ? "Esta acción aún no está conectada en la vista previa. No se cambia ni se envía información de tu cuenta."
                     : "This action is not connected in the preview. No account information is changed or sent.")
            }
    }

    @ViewBuilder private var content: some View {
        switch route {
        case .preferences: preferences
        case .notifications: notifications
        case .privacy: privacy
        case .help: help
        case .feedback: EmptyView()
        case .files, .conversations: records
        case .voice:
            Section {
                CuadraoVoicePreference(spanish: spanish)
                LabeledContent(spanish ? "Idioma" : "Language", value: spanish ? "El de la conversación" : "Matches the conversation")
            } footer: {
                Text(spanish ? "La voz cambia cómo suena Cuadrao. Esta vista previa no activa el micrófono."
                     : "Voice changes how Cuadrao sounds. This preview does not activate the microphone.")
            }
        case .personal: EmptyView()
        }
    }

    private var preferences: some View {
        Group {
            Section {
                CuadraoAppearancePicker(spanish: spanish)
            } header: { Text(spanish ? "Apariencia" : "Appearance") }
              footer: { Text(spanish ? "Sistema sigue la apariencia de tu iPhone." : "System follows your iPhone’s appearance.") }
            Section {
                LabeledContent(spanish ? "Idioma" : "Language", value: spanish ? "Español" : "English")
            } header: { Text(spanish ? "Pantalla" : "Display") }
            Section {
                LabeledContent(spanish ? "Región" : "Region", value: spanish ? "República Dominicana" : "Dominican Republic")
                LabeledContent(spanish ? "Moneda preferida" : "Preferred currency") {
                    CuadraoChoiceMenu(title: spanish ? "Moneda preferida" : "Preferred currency",
                        selection: $profile.currency, values: PlanCurrency.supported, valueTitle: { $0 })
                        .accessibilityIdentifier("cuadrao.profile.currency")
                }
            } header: { Text(spanish ? "Región y moneda" : "Region and currency") }
              footer: { Text(spanish ? "Elegir una moneda no convierte ni combina tus balances." : "Choosing a currency does not convert or combine your balances.") }
            Section { link(.voice) }
        }
    }

    private var notifications: some View {
        Group {
            Section {
                Toggle(spanish ? "En este dispositivo" : "On this device", isOn: $profile.push)
            } header: { Text(spanish ? "Dónde recibirlas" : "Delivery") }
              footer: { Text(spanish ? "Novedades sigue disponible aunque desactives estos avisos. Los controles de esta vista previa no solicitan permisos ni envían notificaciones." : "Updates remain available when these alerts are off. Preview controls do not request permission or send notifications.") }
            Section {
                Toggle(spanish ? "Presupuestos" : "Budgets", isOn: $profile.budgets)
                Toggle(spanish ? "Metas" : "Goals", isOn: $profile.goals)
                Toggle(spanish ? "Pagos próximos" : "Upcoming payments", isOn: $profile.payments)
                Toggle(spanish ? "Por revisar" : "Needs review", isOn: $profile.records)
                Toggle(spanish ? "Hogar" : "Household", isOn: $profile.household)
            } header: { Text(spanish ? "Sobre qué" : "Topics") }
            Section {
                Toggle(spanish ? "Horario de descanso" : "Quiet hours", isOn: $profile.quietHours)
                if profile.quietHours {
                    DatePicker(spanish ? "Desde" : "From", selection: $profile.quietStart, displayedComponents: .hourAndMinute)
                        .accessibilityIdentifier("cuadrao.quiet.start")
                    DatePicker(spanish ? "Hasta" : "Until", selection: $profile.quietEnd, displayedComponents: .hourAndMinute)
                        .accessibilityIdentifier("cuadrao.quiet.end")
                }
            }
        }
    }

    private var privacy: some View {
        Group {
            Section {
                link(.files); link(.conversations)
            } header: { Text(spanish ? "Tus datos" : "Your data") }
            Section {
                // Entry point only; the consequences/verification flow ships separately (DESIGN.md §13).
                Button(spanish ? "Eliminar cuenta" : "Delete account", role: .destructive) {
                    notice = spanish ? "Eliminar cuenta" : "Delete account"
                }
            } footer: { Text(spanish ? "Compartir un hogar no comparte tus chats ni archivos." : "Joining a household does not share your chats or files.") }
        }
    }

    private var records: some View {
        let kind: CanvasSearchKind = route == .files ? .files : .chats
        let rows = includeExamples ? CanvasSearchReference.examples(spanish).filter { $0.kind == kind } : []
        return Group {
            Section {
                ForEach(rows) { item in
                    NavigationLink {
                        CuadraoSearchReferenceDetail(item: item, spanish: spanish, source: nil)
                    } label: {
                        VStack(alignment: .leading, spacing: 5) {
                            Text(item.title)
                            Text(item.detail).font(.caption).foregroundStyle(.secondary)
                        }.padding(.vertical, 6)
                    }
                }
                if rows.isEmpty { Text(spanish ? "Nada guardado todavía." : "Nothing saved yet.").foregroundStyle(.secondary) }
            }
        }
    }

    private var help: some View {
        Group {
            Section {
                previewAction(spanish ? "Centro de ayuda" : "Help center")
                link(.feedback)
            }
            Section {
                previewAction(spanish ? "Términos de uso" : "Terms of use")
                previewAction(spanish ? "Política de privacidad" : "Privacy policy")
            } header: { Text(spanish ? "Acerca de Cuadrao" : "About Cuadrao") }
        }
    }

    private func link(_ route: CanvasProfileRoute) -> some View {
        NavigationLink(value: route) {
            HStack(spacing: 14) {
                CanvasProfileIcon(route: route)
                Text(route.title(spanish)).frame(minHeight: 30)
            }
        }
    }
    private func previewAction(_ title: String) -> some View {
        Button(title) { notice = title }.foregroundStyle(.primary).frame(minHeight: 30)
    }
}
