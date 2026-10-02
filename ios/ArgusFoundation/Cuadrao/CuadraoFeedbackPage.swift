import SwiftUI

enum CanvasFeedbackKind: String, CaseIterable, Identifiable {
    case general, bug, feature
    var id: Self { self }
    func title(_ spanish: Bool) -> String {
        switch self {
        case .general: spanish ? "Comentario" : "General feedback"
        case .bug: spanish ? "Un problema" : "A problem"
        case .feature: spanish ? "Una idea" : "An idea"
        }
    }
}

struct CanvasFeedbackDraft: Equatable {
    var kind: CanvasFeedbackKind = .general
    var general = ""
    var feature = ""
    var bugTitle = ""
    var steps = ""
    var expected = ""
    var actual = ""

    var hasContent: Bool {
        let fields: [String]
        switch kind {
        case .general: fields = [general]
        case .feature: fields = [feature]
        case .bug: fields = [bugTitle, steps, expected, actual]
        }
        return fields.contains { !$0.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }
    }
}

struct CuadraoFeedbackPage: View {
    @Binding var saved: CanvasFeedbackDraft
    let spanish: Bool
    @State private var draft: CanvasFeedbackDraft
    @State private var draftSaved = false

    init(saved: Binding<CanvasFeedbackDraft>, spanish: Bool) {
        _saved = saved; self.spanish = spanish
        _draft = State(initialValue: saved.wrappedValue)
    }

    var body: some View {
        Form {
            Section {
                LabeledContent(spanish ? "¿Qué tienes en mente?" : "What’s on your mind?") {
                    CuadraoChoiceMenu(title: spanish ? "Tipo de comentario" : "Feedback type", selection: $draft.kind,
                        values: CanvasFeedbackKind.allCases, valueTitle: { $0.title(spanish) })
                        .accessibilityIdentifier("cuadrao.feedback.kind")
                }
            }.listRowBackground(CanvasSettingsStyle.surface)
            if draft.kind == .bug {
                Section {
                    field(spanish ? "¿Qué pasó?" : "What happened?", text: $draft.bugTitle, limit: 100, id: "title")
                    field(spanish ? "Pasos para repetirlo" : "Steps to reproduce", text: $draft.steps, limit: 1000, id: "steps")
                    field(spanish ? "¿Qué esperabas?" : "What did you expect?", text: $draft.expected, limit: 500, id: "expected")
                    field(spanish ? "¿Qué ocurrió?" : "What actually happened?", text: $draft.actual, limit: 500, id: "actual")
                } header: { Text(spanish ? "Ayúdanos a entenderlo" : "Help us understand") }
                    .listRowBackground(CanvasSettingsStyle.surface)
            } else {
                Section {
                    if draft.kind == .general {
                        field(spanish ? "Te escuchamos" : "We’re listening", text: $draft.general, limit: 1000, id: "general")
                    } else {
                        field(spanish ? "¿Qué te gustaría poder hacer?" : "What would you like to do?", text: $draft.feature, limit: 1000, id: "feature")
                    }
                }.listRowBackground(CanvasSettingsStyle.surface)
            }
            Section {
                Button(spanish ? "Guardar borrador" : "Save draft") {
                    saved = draft; draftSaved = true
                }.disabled(!draft.hasContent).accessibilityIdentifier("cuadrao.feedback.save")
                if draftSaved {
                    Label(spanish ? "Borrador guardado" : "Draft saved", systemImage: "checkmark")
                        .foregroundStyle(WelcomePalette.pine).font(.subheadline)
                        .accessibilityIdentifier("cuadrao.feedback.saved")
                }
            } footer: {
                Text(spanish ? "El borrador dura hasta cerrar la vista previa. No se envía ni se adjuntan datos."
                     : "The draft lasts until you close the preview. Nothing is sent and no data is attached.")
            }.listRowBackground(CanvasSettingsStyle.surface)
        }.onChange(of: draft) { _, _ in draftSaved = false }
            .scrollContentBackground(.hidden).background(WelcomePalette.background)
            .onAppear { draft = saved }
    }

    private func field(_ title: String, text: Binding<String>, limit: Int, id: String) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title).font(.subheadline).foregroundStyle(.secondary)
            TextField(title, text: text, axis: .vertical).lineLimit(2...6)
                .accessibilityIdentifier("cuadrao.feedback.\(id)")
                .onChange(of: text.wrappedValue) { _, value in
                    if value.count > limit { text.wrappedValue = String(value.prefix(limit)) }
                }
            Text("\(text.wrappedValue.count)/\(limit)").font(.caption2).foregroundStyle(.tertiary)
                .frame(maxWidth: .infinity, alignment: .trailing)
        }.padding(.vertical, 4).listRowBackground(CanvasSettingsStyle.surface)
    }
}
