import SwiftUI

struct CuadraoGroupEditor: View {
    let store: CuadraoGroupPreview
    let spanish: Bool
    var initial: PlanGroup?
    var onSave: ((UUID) -> Void)?
    @State private var name = ""
    @State private var kind: PlanGroupKind = .trip
    @State private var look: CanvasPlanLook = .coast
    @State private var amount = 48000.0
    @State private var currency = "DOP"
    @State private var people = 8
    @State private var discard = false
    @Environment(\.dismiss) private var dismiss
    private var valid: Bool { !name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && amount.isFinite && (1...9999999).contains(amount) }
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 22) {
                    PlanGroupArtwork(look: look, cover: initial?.cover).frame(height: 150).clipShape(RoundedRectangle(cornerRadius: 28))
                    TextField(spanish ? "¿Qué vamos a hacer?" : "What are we planning?", text: $name)
                        .font(.system(.title, design: .serif)).accessibilityIdentifier("group-name")
                    Picker(spanish ? "Tipo de plan" : "Plan type", selection: $kind) {
                        ForEach(PlanGroupKind.allCases, id: \.self) { Text($0.title(spanish)).tag($0) }
                    }.pickerStyle(.segmented).disabled(initial?.expenses.isEmpty == false)
                    VStack(alignment: .leading, spacing: 10) {
                        Text(kind == .trip ? (spanish ? "Creemos que costará" : "We expect it to cost") : (spanish ? "Queremos reunir" : "We want to save")).foregroundStyle(.secondary)
                        HStack {
                            PlanCurrencyChoice(currency: $currency, locked: initial != nil, spanish: spanish)
                            TextField("0", value: $amount, format: .number).keyboardType(.decimalPad).font(.title2).accessibilityIdentifier("group-estimate")
                        }
                        Stepper(spanish ? "\(people) personas previstas" : "\(people) expected people", value: $people, in: 1...50)
                        Text(spanish ? "\(PlanFormat.amount(amount / Double(people), currency: currency)) por persona, si se divide igual." : "\(PlanFormat.amount(amount / Double(people), currency: currency)) each, if split equally.")
                            .font(.subheadline).foregroundStyle(look.color)
                    }.padding(20).background(look.color.opacity(0.07), in: RoundedRectangle(cornerRadius: 24))
                    if initial == nil {
                        Text(spanish ? "La moneda queda fija al crear el plan." : "Currency is fixed once you create the plan.").font(.caption).foregroundStyle(.secondary)
                    }
                    Text(spanish ? "Es una idea de partida. Nadie debe dinero por aceptar una invitación." : "A starting estimate. Accepting an invitation doesn't create a debt.")
                        .font(.caption).foregroundStyle(.secondary)
                    PlanLookPicker(look: $look, spanish: spanish)
                    PlanPrimaryButton(title: initial == nil ? (spanish ? "Crear grupo" : "Create group") : (spanish ? "Guardar cambios" : "Save changes")) {
                        var group = initial ?? PlanGroup(name: name, members: [.init(name: spanish ? "Tú" : "You", symbol: "sun.max.fill")])
                        group.currency = currency
                        group.name = name.trimmingCharacters(in: .whitespacesAndNewlines); group.kind = kind; group.look = look
                        group.estimatedCents = Int((amount * 100).rounded()); group.expectedPeople = people
                        store.save(group); dismiss(); onSave?(group.id)
                    }.disabled(!valid).opacity(valid ? 1 : 0.4).accessibilityIdentifier("group-save")
                    PlanPreviewFootnote(spanish: spanish)
                }.padding(24)
            }.scrollDismissesKeyboard(.interactively).background(WelcomePalette.background)
                .navigationTitle(spanish ? "Un plan juntos" : "A plan together").navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .cancellationAction) { Button(spanish ? "Cancelar" : "Cancel") { discard = true } }
                    ToolbarItemGroup(placement: .keyboard) { Spacer(); Button(spanish ? "Listo" : "Done") { UIApplication.shared.sendAction(#selector(UIResponder.resignFirstResponder), to: nil, from: nil, for: nil) } }
                }
                .confirmationDialog(spanish ? "¿Descartar cambios?" : "Discard changes?", isPresented: $discard, titleVisibility: .visible) {
                    Button(spanish ? "Descartar" : "Discard", role: .destructive) { dismiss() }
                }
        }.onAppear { if let initial { name = initial.name; currency = initial.currency; kind = initial.kind; look = initial.look; amount = Double(initial.estimatedCents) / 100; people = initial.expectedPeople } }
            .interactiveDismissDisabled().presentationDragIndicator(.visible)
    }
}

struct PlanLookPicker: View {
    @Binding var look: CanvasPlanLook
    let spanish: Bool
    var body: some View {
        HStack(spacing: 14) {
            ForEach(CanvasPlanLook.allCases) { choice in
                Button { look = choice } label: {
                    Image(systemName: choice.symbol).font(.title3).foregroundStyle(choice.color)
                        .frame(maxWidth: .infinity, minHeight: 48)
                        .background(choice.color.opacity(look == choice ? 0.18 : 0.04), in: RoundedRectangle(cornerRadius: 16))
                        .overlay { if look == choice { RoundedRectangle(cornerRadius: 16).stroke(choice.color.opacity(0.5), lineWidth: 1) } }
                }.accessibilityLabel(choice.title(spanish)).accessibilityAddTraits(look == choice ? .isSelected : [])
            }
        }.sensoryFeedback(.selection, trigger: look)
    }
}
