import SwiftUI
import PDFKit
import MapKit
import CoreLocation

struct CuadraoReceiptReview: View {
    let id: UUID
    let workspace: ReceiptWorkspace
    let spanish: Bool
    var body: some View {
        if let draft = workspace.receipts.receipt(id) {
            ReceiptEditor(initial: draft, workspace: workspace, spanish: spanish)
        } else { ContentUnavailableView(spanish ? "Recibo no disponible" : "Receipt unavailable", systemImage: "receipt") }
    }
}

private struct ReceiptEditor: View {
    let workspace: ReceiptWorkspace
    let spanish: Bool
    @State private var chatFocus: CanvasChatFocus?
    @State private var draft: ReceiptDraft
    @State private var error = ""
    @State private var amountErrors: [String: String] = [:]
    @State private var showSource = false
    @State private var editingLine: ReceiptLine?
    @Environment(\.dismiss) private var dismiss
    @State private var discard = false
    @State private var details = false
    @State private var charges = false
    @State private var location = ReceiptLocationRequest()
    private var es: Bool { spanish }
    private var group: PlanGroup? { draft.groupID.flatMap(workspace.groups.group) }
    private var posted: PlanSharedExpense? { group?.expenses.first { $0.id == draft.id && $0.receiptID == draft.id } }
    private var shares: [UUID: Int] { posted?.shares ?? ((try? draft.shares(roster: group?.activeMembers.map(\.id) ?? [])) ?? [:]) }
    private var compatibleAccounts: [CanvasAccount] {
        workspace.accounts.accounts.filter { !$0.archived && $0.currency == draft.currency && $0.spaceID == CanvasSpace.personalID && [.cash, .checking, .savings, .card].contains($0.kind) }
    }
    init(initial: ReceiptDraft, workspace: ReceiptWorkspace, spanish: Bool) {
        self.workspace = workspace; self.spanish = spanish; _draft = State(initialValue: initial)
    }
    var body: some View {
        Form {
            Section {
                VStack(alignment: .leading, spacing: 10) {
                    Label(draft.prepared ? (es ? "Guardado · por revisar" : "Saved · ready to review") : (es ? "Confirmado" : "Confirmed"), systemImage: draft.prepared ? "checkmark.circle" : "checkmark.seal")
                        .font(CuadraoTypography.caption).foregroundStyle(.secondary).accessibilityIdentifier("receipt-status")
                    if draft.example { Text(es ? "Recibo de ejemplo" : "Sample receipt").font(CuadraoTypography.caption).foregroundStyle(WelcomePalette.pine) }
                    Text(posted?.title ?? (draft.merchant.isEmpty ? (es ? "Tu recibo" : "Your receipt") : draft.merchant)).font(CuadraoTypography.feature)
                    if draft.lines.isEmpty && posted == nil {
                        Text(es ? "Total por revisar" : "Total to review").font(CuadraoTypography.secondaryAmount)
                            .accessibilityIdentifier("receipt-total")
                    } else if let currency = draft.currency {
                        HStack(alignment: .firstTextBaseline) {
                            Text(currency).font(.caption).foregroundStyle(.secondary)
                            Text(money(posted?.cents ?? draft.total)).font(CuadraoTypography.amount)
                                .lineLimit(1).minimumScaleFactor(0.65)
                        }.accessibilityIdentifier("receipt-total")
                    }
                    Text((CanvasExpenseCategory(rawValue: draft.category) ?? .other).title(es) + " · " + draft.date.formatted(.dateTime.day().month(.abbreviated).year().locale(Locale(identifier: es ? "es-419" : "en_US"))))
                        .font(CuadraoTypography.supporting).foregroundStyle(.secondary)
                }.padding(.vertical, 8)
                Button { showSource = true } label: {
                    Label(es ? "Ver recibo original" : "View original receipt", systemImage: "doc.text.image").frame(minHeight: 44)
                }.accessibilityIdentifier("receipt-source")
                if !draft.prepared {
                    Button { askCuadrao() } label: {
                        Label(es ? "Preguntar a Cuadrao" : "Ask Cuadrao", systemImage: "bubble").frame(minHeight: 44)
                    }.accessibilityIdentifier("receipt-open-chat")
                }
                if draft.prepared {
                    DisclosureGroup(es ? "Corregir datos" : "Correct details", isExpanded: $details) {
                        TextField(es ? "Comercio" : "Merchant", text: $draft.merchant).accessibilityIdentifier("receipt-merchant")
                        DatePicker(es ? "Fecha" : "Date", selection: $draft.date, displayedComponents: .date)
                        Picker(es ? "Categoría" : "Category", selection: $draft.category) {
                            ForEach(CanvasExpenseCategory.allCases) { Text($0.title(es)).tag($0.rawValue) }
                        }
                        if let currency = draft.currency { Label(currency, systemImage: "lock").font(.caption).foregroundStyle(.secondary) }
                    }
                }
            }
            if draft.currency == nil {
                Section {
                    Menu {
                        ForEach(PlanCurrency.supported, id: \.self) { currency in
                            Button(currency) { chooseCurrency(currency) }
                        }
                    } label: {
                        Label(es ? "Elegir moneda" : "Choose currency", systemImage: "chevron.up.chevron.down")
                            .frame(maxWidth: .infinity, alignment: .leading).contentShape(Rectangle())
                    }.accessibilityIdentifier("receipt-currency")
                    Text(es ? "El recibo ya está guardado. Elige su moneda para revisar los montos; después quedará fija." : "Your receipt is saved. Choose its currency to review amounts; it stays fixed afterward.")
                        .font(CuadraoTypography.caption).foregroundStyle(.secondary)
                }
            }
            if let currency = draft.currency {
                Section(es ? "Artículos" : "Items") {
                    if draft.lines.isEmpty {
                        Text(es ? "Añade los artículos del recibo." : "Add the receipt's items.").font(.subheadline).foregroundStyle(.secondary)
                    }
                    ForEach(draft.lines) { line in
                        Button { if draft.prepared { editingLine = line } } label: {
                            HStack {
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(line.name).foregroundStyle(WelcomePalette.ink)
                                    Text("\(line.quantity) × \(money(line.unitCents))").font(.caption).foregroundStyle(.secondary)
                                }
                                Spacer()
                                Text(money(line.cents)).font(CuadraoTypography.rowAmount).foregroundStyle(WelcomePalette.ink)
                                if draft.prepared { Image(systemName: "chevron.right").font(.caption2) }
                            }.frame(minHeight: 44).contentShape(Rectangle())
                        }.buttonStyle(.plain).accessibilityIdentifier("receipt-line-\(draft.lines.firstIndex(where: { $0.id == line.id }) ?? 0)")
                    }
                    if draft.prepared {
                        Button(es ? "Añadir artículo" : "Add item", systemImage: "plus") { editingLine = ReceiptLine(name: "", unitCents: 0) }
                            .disabled(draft.lines.count >= 100).accessibilityIdentifier("receipt-add-item")
                    }
                    totalRow(es ? "Subtotal" : "Subtotal", draft.subtotal)
                    DisclosureGroup(es ? "Impuestos y propina" : "Tax and tip", isExpanded: $charges) {
                        if draft.prepared {
                            centInput(es ? "Impuesto del recibo" : "Receipt tax", key: \.taxCents, id: "receipt-tax")
                            centInput(es ? "Servicio del recibo" : "Receipt service charge", key: \.serviceCents, id: "receipt-service")
                            centInput(es ? "Propina adicional" : "Extra tip", key: \.addedTipCents, id: "receipt-tip")
                        } else {
                            totalRow(es ? "Impuesto" : "Tax", draft.taxCents)
                            totalRow(es ? "Servicio" : "Service", draft.serviceCents)
                            totalRow(es ? "Propina adicional" : "Extra tip", draft.addedTipCents)
                        }
                        Text(es ? "El impuesto y el servicio ya forman parte del total del recibo. Solo la propina adicional se suma después." : "Tax and service are already part of the receipt total. Only the extra tip is added afterward.").font(.caption).foregroundStyle(.secondary)
                    }
                    totalRow(es ? "Total del recibo" : "Receipt total", draft.receiptTotal)
                    if draft.addedTipCents > 0 { totalRow(es ? "Con propina adicional" : "Including extra tip", draft.total) }
                }
                if draft.prepared { destination }
                else if case .personal(let accountID) = draft.destination, let accountID, let account = workspace.accounts.account(accountID) {
                    Section(es ? "Guardado en" : "Saved to") {
                        Label(account.displayName(es) + " · " + currency, systemImage: "creditcard")
                    }
                }
                if let group { splitSection(group) }
            }
            Section {
                if let pin = draft.captureLocation {
                    Map(initialPosition: .region(MKCoordinateRegion(center: .init(latitude: pin.latitude, longitude: pin.longitude), span: .init(latitudeDelta: 0.01, longitudeDelta: 0.01)))) {
                        Marker(es ? "Ubicación añadida" : "Added location", coordinate: .init(latitude: pin.latitude, longitude: pin.longitude))
                    }.frame(height: 150).clipShape(RoundedRectangle(cornerRadius: 16))
                    Text((es ? "Ubicación añadida el " : "Location added on ") + pin.recordedAt.formatted(date: .abbreviated, time: .shortened)).font(.caption).foregroundStyle(.secondary)
                    if draft.prepared { Button(es ? "Quitar ubicación" : "Remove location", role: .destructive) { draft.captureLocation = nil } }
                } else if draft.prepared {
                    Button { location.request() } label: { Label(es ? "Añadir ubicación actual" : "Add current location", systemImage: "location").frame(minHeight: 44) }
                    Text(es ? "Opcional. No es la dirección del comercio." : "Optional. This is not the merchant's address.").font(.caption).foregroundStyle(.secondary)
                }
                if location.unavailable { Text(es ? "No pudimos obtener tu ubicación. Puedes continuar sin ella." : "Your location is unavailable. You can continue without it.").font(.caption).foregroundStyle(.secondary) }
            }
            Section {
                if !error.isEmpty { Text(error).foregroundStyle(.red).font(.subheadline).accessibilityIdentifier("receipt-error") }
                if draft.prepared {
                    Button { confirm() } label: {
                        Text(es ? "Confirmar gasto" : "Confirm expense").font(CuadraoTypography.action).frame(maxWidth: .infinity, minHeight: 44)
                    }.disabled(!valid).accessibilityIdentifier("receipt-confirm")
                    Text(es ? "Hasta confirmar, este recibo no cambia ningún balance." : "Until you confirm, this receipt changes no balances.").font(.caption).foregroundStyle(.secondary)
                } else {
                    Label(es ? "Gasto guardado" : "Expense saved", systemImage: "checkmark.seal.fill").foregroundStyle(WelcomePalette.pine).accessibilityIdentifier("receipt-confirmed")
                }
            }
        }.cuadraoFormKeyboard().scrollContentBackground(.hidden).background(WelcomePalette.background)
            .navigationTitle(es ? "Revisar recibo" : "Review receipt").navigationBarTitleDisplayMode(.inline)
            .sheet(isPresented: $showSource) { ReceiptSourceViewer(draft: draft, store: workspace.receipts, spanish: es) }
            .sheet(item: $editingLine) { line in
                if let currency = draft.currency {
                    ReceiptLineEditor(line: line, currency: currency, spanish: es, existing: draft.lines.contains { $0.id == line.id }) { revised in
                        if let revised {
                            if let index = draft.lines.firstIndex(where: { $0.id == revised.id }) { draft.lines[index] = revised }
                            else { draft.lines.append(revised) }
                        } else { draft.lines.removeAll { $0.id == line.id } }
                    }
                }
            }
            .contextualCuadrao(focus: $chatFocus, spanish: es)
            .onChange(of: draft) { old, value in
                guard old.prepared, value.prepared, value != workspace.receipts.receipt(value.id) else { return }
                do { try workspace.receipts.update(value); error = "" } catch { show(error) }
            }
            .onChange(of: location.value) { _, value in if let value, draft.prepared { draft.captureLocation = value } }
            .confirmationDialog(es ? "¿Descartar este recibo?" : "Discard this receipt?", isPresented: $discard, titleVisibility: .visible) {
                Button(es ? "Descartar recibo" : "Discard receipt", role: .destructive) {
                    do {
                        try workspace.receipts.discard(draft.id, groups: workspace.groups)
                        workspace.chat.removeReceipt(draft.id)
                        dismiss()
                    } catch { show(error) }
                }
            }
            .toolbar {
                if draft.prepared {
                    ToolbarItem(placement: .topBarTrailing) {
                        Menu {
                            Button(es ? "Preguntar a Cuadrao" : "Ask Cuadrao", systemImage: "bubble") { askCuadrao() }
                                .accessibilityIdentifier("receipt-open-chat")
                            Button(es ? "Descartar recibo" : "Discard receipt", systemImage: "trash", role: .destructive) { discard = true }
                        } label: { Image(systemName: "ellipsis").frame(width: 44, height: 44) }
                            .accessibilityLabel(es ? "Opciones del recibo" : "Receipt options")
                    }
                }
            }
    }
    private func askCuadrao() {
        chatFocus = .receipt(id: draft.id, title: draft.merchant.isEmpty ? (es ? "Tu recibo" : "Your receipt") : draft.merchant)
    }
    private var destination: some View {
        Section(es ? "Dónde guardarlo" : "Save to") {
            Picker(es ? "Destino" : "Destination", selection: Binding(get: { draft.groupID?.uuidString ?? "personal" }, set: chooseDestination)) {
                Text(es ? "Personal" : "Personal").tag("personal")
                ForEach(workspace.groups.groups.filter { !$0.archived && $0.kind == .trip && $0.currency == draft.currency }) { Text($0.name).tag($0.id.uuidString) }
            }.accessibilityIdentifier("receipt-destination")
            if case .personal(let accountID) = draft.destination {
                Picker(es ? "Cuenta" : "Account", selection: Binding(get: { accountID }, set: { draft.destination = .personal(accountID: $0) })) {
                    Text(es ? "Elige una cuenta" : "Choose an account").tag(UUID?.none)
                    ForEach(compatibleAccounts) { Text($0.displayName(es)).tag(Optional($0.id)) }
                }.accessibilityIdentifier("receipt-account")
                if compatibleAccounts.isEmpty { Text(es ? "No hay cuentas personales de esta moneda." : "There are no personal accounts in this currency.").font(.caption).foregroundStyle(.secondary) }
            }
            if let currency = draft.currency { Text(currency).font(.caption).foregroundStyle(.secondary) }
        }
    }
    private func chooseCurrency(_ currency: String) {
        do {
            try workspace.receipts.setCurrency(currency, for: draft.id)
            if let saved = workspace.receipts.receipt(draft.id) { draft = saved }
            error = ""
        } catch { show(error) }
    }
    private func chooseDestination(_ value: String) {
        guard draft.currency != nil else { return }
        if let id = UUID(uuidString: value), let group = workspace.groups.group(id) {
            draft.destination = .group(id); draft.payer = group.me; draft.participants = Set(group.activeMembers.map(\.id))
            for index in draft.lines.indices { draft.lines[index].members = [] }
        } else { draft.destination = .personal(accountID: nil) }
    }
    private func splitSection(_ group: PlanGroup) -> some View {
        Section(es ? "El reparto" : "The split") {
            if draft.prepared {
                Picker(es ? "Pagó" : "Paid by", selection: $draft.payer) {
                    ForEach(group.activeMembers) { Text($0.name).tag(Optional($0.id)) }
                }.accessibilityIdentifier("receipt-payer")
                Picker(es ? "Repartir" : "Split", selection: $draft.split) {
                    Text(es ? "Por igual" : "Equally").tag(ReceiptSplit.equal)
                    Text(es ? "Por consumo" : "By item").tag(ReceiptSplit.items)
                }.pickerStyle(.segmented).accessibilityIdentifier("receipt-split")
                ForEach(Array(group.activeMembers.enumerated()), id: \.element.id) { index, member in
                    Button {
                        if draft.participants.contains(member.id) {
                            draft.participants.remove(member.id)
                            for i in draft.lines.indices { draft.lines[i].members.remove(member.id) }
                        } else { draft.participants.insert(member.id) }
                    } label: {
                        HStack {
                            Image(systemName: draft.participants.contains(member.id) ? "checkmark.circle.fill" : "circle")
                            PlanMemberAvatar(member: member, index: index)
                            Text(member.name); Spacer()
                            Text(money(shares[member.id] ?? 0)).font(CuadraoTypography.rowAmount)
                        }.frame(minHeight: 44).contentShape(Rectangle())
                    }.buttonStyle(.plain).accessibilityIdentifier("receipt-member-\(index)")
                        .accessibilityLabel(member.name)
                        .accessibilityValue((draft.participants.contains(member.id) ? (es ? "Incluido" : "Included") : (es ? "Excluido" : "Excluded")) + ", " + money(shares[member.id] ?? 0))
                        .accessibilityAddTraits(draft.participants.contains(member.id) ? .isSelected : [])
                }
                if draft.split == .items {
                    ForEach(draft.lines) { line in
                        VStack(alignment: .leading, spacing: 8) {
                            Text(line.name).font(CuadraoTypography.supporting)
                            ViewThatFits(in: .horizontal) {
                                assignmentButtons(line, group: group, vertical: false)
                                assignmentButtons(line, group: group, vertical: true)
                            }
                        }.padding(.vertical, 4)
                    }
                    Text(draft.unassigned == 0 ? (es ? "Todos los artículos asignados" : "Every item assigned") : (es ? "\(draft.unassigned) artículos por asignar" : "\(draft.unassigned) items left to assign"))
                        .font(.caption).foregroundStyle(draft.unassigned == 0 ? WelcomePalette.pine : .secondary).accessibilityIdentifier("receipt-unassigned")
                    Text(es ? "Toca varias personas para compartir un artículo. Los cargos se reparten según lo consumido." : "Tap multiple people to share an item. Charges follow each person's items.").font(.caption).foregroundStyle(.secondary)
                }
            } else {
                if let payer = posted?.payer, let member = group.members.first(where: { $0.id == payer }) {
                    Text((es ? "Pagó " : "Paid by ") + member.name).font(CuadraoTypography.supporting)
                }
                ForEach(group.members.filter { shares[$0.id] != nil }) { member in
                    HStack { Text(member.name); Spacer(); Text(money(shares[member.id] ?? 0)).font(CuadraoTypography.rowAmount) }
                }
            }
            if !shares.isEmpty {
                totalRow(es ? "Tu parte" : "Your share", shares[group.me] ?? 0)
                let payer = posted?.payer ?? draft.payer
                let net = (payer == group.me ? (posted?.cents ?? draft.total) : 0) - (shares[group.me] ?? 0)
                if let currency = draft.currency { CuadraoOwedRow(cents: net, currency: currency, spanish: es) }
            }
        }
    }
    private func assignmentButtons(_ line: ReceiptLine, group: PlanGroup, vertical: Bool) -> some View {
        let layout = vertical ? AnyLayout(VStackLayout(alignment: .leading, spacing: 4)) : AnyLayout(HStackLayout(spacing: 6))
        return layout {
            ForEach(group.activeMembers.filter { draft.participants.contains($0.id) }) { member in
                Button {
                    guard let index = draft.lines.firstIndex(where: { $0.id == line.id }) else { return }
                    if draft.lines[index].members.contains(member.id) { draft.lines[index].members.remove(member.id) }
                    else { draft.lines[index].members.insert(member.id) }
                } label: {
                    HStack(spacing: 6) {
                        Image(systemName: line.members.contains(member.id) ? "checkmark.circle.fill" : "circle")
                        Text(member.name)
                    }
                        .font(.subheadline).fixedSize(horizontal: !vertical, vertical: true)
                        .padding(.horizontal, 8).frame(minHeight: 44)
                        .background(line.members.contains(member.id) ? WelcomePalette.sage : .clear, in: Capsule())
                }.buttonStyle(.plain).accessibilityIdentifier("receipt-assign-\(draft.lines.firstIndex(where: { $0.id == line.id }) ?? 0)-\(group.activeMembers.firstIndex(where: { $0.id == member.id }) ?? 0)")
                    .accessibilityLabel("\(line.name), \(member.name)")
                    .accessibilityValue(line.members.contains(member.id) ? (es ? "Asignado" : "Assigned") : (es ? "Sin asignar" : "Not assigned"))
                    .accessibilityAddTraits(line.members.contains(member.id) ? .isSelected : [])
            }
        }
    }
    private var valid: Bool {
        guard !amountErrors.values.contains(where: { !$0.isEmpty }), (try? draft.validate()) != nil else { return false }
        if let group { return (try? draft.shares(roster: group.activeMembers.map(\.id))) != nil && draft.payer != nil }
        if case .personal(let id) = draft.destination { return compatibleAccounts.contains { $0.id == id } }
        return false
    }
    private func confirm() {
        do {
            try workspace.receipts.update(draft)
            try workspace.receipts.confirm(draft.id, groups: workspace.groups, accounts: workspace.accounts)
            if let saved = workspace.receipts.receipt(draft.id) { draft = saved }
        } catch { show(error) }
    }
    private func show(_ failure: Error) {
        error = (failure as? ReceiptError)?.message(es) ?? (es ? "No se pudo guardar. Tus cambios aún no están confirmados. Inténtalo de nuevo." : "Could not save. Your changes are not confirmed. Try again.")
    }
    private func money(_ cents: Int) -> String {
        guard let currency = draft.currency else { return "" }
        return CanvasMoney.format(Decimal(cents) / 100, currency: currency)
    }
    private func totalRow(_ title: String, _ cents: Int) -> some View {
        HStack { Text(title).font(CuadraoTypography.supporting); Spacer(); Text(money(cents)).font(CuadraoTypography.rowAmount) }
    }
    private func centInput(_ title: String, key: WritableKeyPath<ReceiptDraft, Int>, id: String) -> some View {
        VStack(alignment: .leading) {
            HStack {
                Text(title).font(CuadraoTypography.supporting)
                if let currency = draft.currency {
                CanvasMoneyValueInput(value: Binding(get: { Double(draft[keyPath: key]) / 100 }, set: { draft[keyPath: key] = Int(($0 * 100).rounded()) }),
                                      error: $amountErrors.message(for: id), currency: currency, spanish: es,
                                      identifier: id, title: title, size: .row, alignment: .right).frame(minHeight: 44)
                }
            }
            if let error = amountErrors[id], !error.isEmpty { Text(error).font(.caption).foregroundStyle(.red) }
        }
    }
}
