import SwiftUI

struct CuadraoFirstAccountSheet: View {
    let data: CuadraoAccountsPreview
    let spanish: Bool
    var existing: CanvasAccount?
    @Environment(\.dismiss) private var dismiss
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var kind: CanvasAccountKind?
    @State private var pickingType = true
    @State private var assetsExpanded = false
    @State private var name = ""
    @State private var amount = ""
    @State private var currency = "DOP"
    @State private var error = ""
    @State private var share = 100
    @State private var customShare = ""
    @State private var sharingCustom = false
    @FocusState private var nameFocused: Bool

    private var hint: String? {
        if kind?.isAsset == true && sharingCustom && !(1...100).contains(Int(customShare) ?? 0) {
            return spanish ? "Introduce tu parte, de 1 a 100%." : "Enter your share, from 1 to 100%."
        }
        if kind == nil { return spanish ? "Elige un tipo de cuenta" : "Choose an account type" }
        if !error.isEmpty || (!amount.isEmpty && Decimal(string: amount) == nil) {
            return spanish ? "Revisa el monto" : "Check the amount"
        }
        return nil
    }
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 28) {
                    Text(data.selectedSpace.title(spanish)).font(.subheadline).foregroundStyle(.secondary)
                    typePicker
                    VStack(alignment: .leading, spacing: 10) {
                        fieldLabel(spanish ? "Nombre" : "Name")
                        TextField(spanish ? "Ej. Gastos del día" : "e.g. Everyday spending", text: $name)
                            .autocorrectionDisabled().focused($nameFocused).submitLabel(.done)
                            .onSubmit { nameFocused = false }
                            .modifier(RegistrationField(focused: nameFocused))
                            .accessibilityIdentifier("account-name")
                            .onChange(of: name) { _, value in if value.count > 60 { name = String(value.prefix(60)) } }
                    }
                    VStack(alignment: .leading, spacing: 10) {
                        fieldLabel(kind?.isDebt == true ? (spanish ? "Monto pendiente" : "Amount owed")
                            : kind?.isAsset == true ? (spanish ? "Valor total estimado" : "Estimated total value")
                            : (spanish ? "Balance actual" : "Current balance"))
                        CuadraoAmountField(raw: $amount, currency: $currency, error: $error,
                            spanish: spanish, allowNegative: kind?.isDebt != true && kind?.isAsset != true)
                    }
                    if kind?.isAsset == true {
                        VStack(alignment: .leading, spacing: 12) {
                            HStack {
                                Text(spanish ? "Tu parte" : "Your share")
                                Spacer()
                                Menu {
                                    Button(spanish ? "Todo · 100%" : "All · 100%") { share = 100; sharingCustom = false }
                                    Button(spanish ? "La mitad · 50%" : "Half · 50%") { share = 50; sharingCustom = false }
                                    Button(spanish ? "Otra parte" : "Another share") { sharingCustom = true }
                                } label: {
                                    Text(sharingCustom ? (spanish ? "Otra parte" : "Another share") : "\(share)%")
                                        .frame(minHeight: 44)
                                }
                            }
                            if sharingCustom {
                                TextField(spanish ? "Porcentaje" : "Percentage", text: $customShare)
                                    .keyboardType(.numberPad).modifier(RegistrationField())
                            }
                        }
                    }
                }.padding(24)
            }
            .scrollDismissesKeyboard(.interactively)
            .background(WelcomePalette.background)
            .navigationTitle(existing == nil ? (spanish ? "Añadir cuenta" : "Add account") : (spanish ? "Editar cuenta" : "Edit account"))
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button(spanish ? "Cancelar" : "Cancel") { dismiss() } }
            }
            .safeAreaInset(edge: .bottom, spacing: 0) {
                VStack(spacing: 0) {
                    if let hint {
                        HStack(spacing: 8) {
                            Image(systemName: "info.circle").accessibilityHidden(true)
                            Text(hint).font(.subheadline)
                        }.foregroundStyle(.secondary).padding(.top, 14).padding(.bottom, 12)
                            .frame(maxWidth: .infinity)
                            .transition(.move(edge: .bottom).combined(with: .opacity))
                    }
                    RegistrationButton(title: existing == nil ? (spanish ? "Añadir" : "Add") : (spanish ? "Guardar" : "Save"), enabled: hint == nil) {
                        guard let kind else { return }
                        var account = existing ?? CanvasAccount(name: "", kind: kind)
                        if existing == nil {
                            account.spaceID = data.selectedSpaceID
                            account.sharedWithHousehold = data.selectedSpace.kind == .household
                        }
                        account.name = name.trimmingCharacters(in: .whitespacesAndNewlines)
                        account.kind = kind; account.currency = currency
                        account.balance = Decimal(string: amount); account.share = sharingCustom ? (Int(customShare) ?? 100) : share
                        data.replace(account); dismiss()
                    }.accessibilityIdentifier("account-save")
                }
                .background(WelcomePalette.sage.opacity(0.65), in: RoundedRectangle(cornerRadius: 20))
                .clipped()
                .animation(reduceMotion ? nil : .easeInOut(duration: 0.22), value: hint)
                .padding(.horizontal, 24).padding(.top, 12).padding(.bottom, 16)
                .background(WelcomePalette.background)
            }
        }.tint(WelcomePalette.pine)
        .onAppear {
            guard let existing else { return }
            kind = existing.kind; pickingType = false; name = existing.name
            amount = existing.balance.map(CanvasMoney.raw) ?? ""
            currency = existing.currency; share = existing.share
        }
    }
    private func fieldLabel(_ label: String) -> some View {
        HStack(spacing: 8) {
            Text(label)
            Text(spanish ? "Opcional" : "Optional").foregroundStyle(.secondary)
        }.font(.subheadline)
    }
    private var typePicker: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text(spanish ? "Tipo de cuenta" : "Account type").font(.subheadline)
            if let kind, !pickingType {
                Button { withAnimation(reduceMotion ? nil : .easeInOut(duration: 0.2)) { pickingType = true } } label: {
                    HStack(spacing: 14) {
                        CanvasAccountIcon(kind: kind)
                        Text(kind.title(spanish)).foregroundStyle(.primary)
                        Spacer()
                        Image(systemName: "chevron.down").font(.caption).foregroundStyle(.secondary)
                    }.padding(18).background(WelcomePalette.sage.opacity(0.65), in: RoundedRectangle(cornerRadius: 16))
                }.buttonStyle(.plain).accessibilityLabel(spanish ? "Cambiar tipo, \(kind.title(spanish))" : "Change type, \(kind.title(spanish))")
            } else {
                typeGrid(CanvasAccountKind.allCases.filter { !$0.isAsset })
                DisclosureGroup(isExpanded: $assetsExpanded) {
                    typeGrid(CanvasAccountKind.allCases.filter(\.isAsset)).padding(.top, 12)
                } label: {
                    HStack(spacing: 12) {
                        CanvasAccountIcon(kind: .asset, size: 21)
                        Text(spanish ? "Otros activos" : "Other assets").foregroundStyle(.primary)
                    }.padding(.vertical, 10)
                }
            }
        }
    }
    private func typeGrid(_ kinds: [CanvasAccountKind]) -> some View {
        LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible()), GridItem(.flexible())], spacing: 10) {
            ForEach(kinds) { item in
                Button {
                    nameFocused = false
                    withAnimation(reduceMotion ? nil : .easeInOut(duration: 0.22)) {
                        kind = item; pickingType = false
                    }
                    if (item.isDebt || item.isAsset), (Decimal(string: amount) ?? 0) < 0 {
                        error = spanish ? "Introduce un monto positivo." : "Enter a positive amount."
                    }
                } label: {
                    VStack(spacing: 11) {
                        CanvasAccountIcon(kind: item, size: 26)
                        Text(item.title(spanish)).font(.caption).multilineTextAlignment(.center).foregroundStyle(.primary)
                    }.frame(maxWidth: .infinity, minHeight: 91)
                        .background(kind == item ? WelcomePalette.sage : WelcomePalette.surface, in: RoundedRectangle(cornerRadius: 16))
                }.buttonStyle(.plain).accessibilityIdentifier("account-type-" + item.rawValue)
            }
        }
    }
}
