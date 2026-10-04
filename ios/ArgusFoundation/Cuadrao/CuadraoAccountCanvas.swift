import SwiftUI

struct CuadraoAccountCanvas: View {
    let data: CuadraoAccountsPreview
    let accountID: UUID
    let spanish: Bool
    let actions: (CanvasAccountSheet) -> Void
    let record: (UUID) -> Void
    @State private var showingBalanceInfo = false
    @State private var chatFocus: CanvasChatFocus?

    var body: some View {
        if let account = data.account(accountID) {
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 30) {
                    VStack(alignment: .leading, spacing: 18) {
                        CanvasAccountIcon(kind: account.kind, size: 30)
                            .frame(width: 58, height: 58)
                            .background(WelcomePalette.sage, in: RoundedRectangle(cornerRadius: 18))
                        Text(account.displayName(spanish)).font(CuadraoTypography.screen)
                            .accessibilityIdentifier("account-detail-title")
                            .fixedSize(horizontal: false, vertical: true)
                        VStack(alignment: .leading, spacing: 9) {
                            Text(account.balanceLabel(spanish)).font(.subheadline).foregroundStyle(.secondary)
                            HStack(alignment: .firstTextBaseline, spacing: 9) {
                                Text(account.currency).font(.subheadline).foregroundStyle(.secondary)
                                Text(account.balance.map { CanvasMoney.format($0, currency: account.currency) } ?? "—")
                                    .font(CuadraoTypography.amount)
                                    .monospacedDigit().lineLimit(1).minimumScaleFactor(0.6)
                            }
                            Text(account.balance == nil ? (spanish ? "Sin balance registrado" : "No balance recorded")
                                 : (spanish ? "Actualizado hoy" : "Updated today"))
                                .font(.footnote).foregroundStyle(.secondary)
                        }
                    }
                    VStack(spacing: 12) {
                        RegistrationButton(title: spanish ? "Añadir movimiento" : "Add transaction") { record(accountID) }
                            .accessibilityIdentifier("account-detail-record")
                        Button(spanish ? "Comprobar balance" : "Check balance") { showingBalanceInfo = true }
                            .font(.system(size: 13, weight: .medium)).padding(.horizontal, 16).frame(minHeight: 44)
                            .overlay { Capsule().stroke(WelcomePalette.border, lineWidth: 1) }
                    }
                    LazyVStack(alignment: .leading, spacing: 16) {
                        Text(spanish ? "Movimientos" : "Activity").font(CuadraoTypography.section)
                        let entries = data.activity.filter { $0.accountID == accountID }.sorted { $0.date > $1.date }
                        if entries.isEmpty {
                            VStack(alignment: .leading, spacing: 8) {
                                Text(spanish ? "Aún no hay movimientos." : "No activity yet.").font(.body)
                                Text(spanish ? "Añade el primero cuando lo necesites." : "Add the first when you need to.")
                                    .font(.subheadline).foregroundStyle(.secondary)
                            }.padding(.vertical, 18)
                        } else {
                            ForEach(entries) { entry in
                                NavigationLink {
                                    CuadraoActivityDetail(data: data, activityID: entry.id, spanish: spanish, actions: actions, record: record)
                                } label: {
                                    HStack(spacing: 14) {
                                        Image(systemName: entry.income ? "arrow.down.left" : "arrow.up.right")
                                            .frame(width: 38, height: 38)
                                            .background(WelcomePalette.surface, in: Circle()).accessibilityHidden(true)
                                        VStack(alignment: .leading, spacing: 5) {
                                            Text(entry.title).font(.body)
                                            Text(entry.date, format: .dateTime.day().month(.abbreviated))
                                                .font(.caption).foregroundStyle(.secondary)
                                        }
                                        Spacer()
                                        Text((entry.income ? "+" : "−") + CanvasMoney.format(entry.amount, currency: account.currency))
                                            .font(CuadraoTypography.rowAmount)
                                    }.padding(.vertical, 10).contentShape(Rectangle())
                                }.buttonStyle(.plain).accessibilityIdentifier("account-detail-activity.\(entry.id)")
                                Divider()
                            }
                        }
                    }
                }.padding(24).padding(.bottom, 32)
            }.background(WelcomePalette.background)
                .navigationTitle("").navigationBarTitleDisplayMode(.inline)
                .toolbar(.visible, for: .navigationBar)
                .toolbar {
                    if #available(iOS 26.0, *) {
                        ToolbarItem(placement: .topBarTrailing) { moreButton }
                            .sharedBackgroundVisibility(.hidden)
                    } else {
                        ToolbarItem(placement: .topBarTrailing) { moreButton }
                    }
                }
                .contextualCuadrao(focus: $chatFocus, spanish: spanish)
                .alert(spanish ? "Comprobar balance" : "Check balance", isPresented: $showingBalanceInfo) {
                    Button(spanish ? "Entendido" : "Got it", role: .cancel) { }
                } message: {
                    Text(spanish ? "La conciliación sigue en la app conectada. Esta vista permite revisar el diseño de la cuenta."
                         : "Reconciliation remains in the connected app. This canvas previews the account design.")
                }
        }
    }
    private var moreButton: some View {
        Menu {
            if let account = data.account(accountID) {
                Button(spanish ? "Preguntar a Cuadrao" : "Ask Cuadrao", systemImage: "bubble") {
                    chatFocus = .account(id: accountID, title: account.displayName(spanish))
                }.accessibilityIdentifier("account-detail-ask")
            }
            Button(spanish ? "Cambiar nombre" : "Rename account", systemImage: "pencil") { actions(.rename(accountID)) }
            Button(spanish ? "Añadir movimiento" : "Add transaction", systemImage: "plus") { record(accountID) }
            Button(spanish ? "Archivar" : "Archive", systemImage: "archivebox") { actions(.archive(accountID)) }
        } label: {
            Image(systemName: "ellipsis").frame(width: 44, height: 44).contentShape(Rectangle())
        }.buttonStyle(.plain)
            .accessibilityLabel(spanish ? "Opciones de cuenta" : "Account actions")
            .accessibilityIdentifier("account-detail-options")
    }

}

/// Visual entry/review only. Saving stages a sample row, never a financial command.
struct CuadraoTransactionCanvas: View {
    let data: CuadraoAccountsPreview
    let account: CanvasAccount
    let spanish: Bool
    @Environment(\.dismiss) private var dismiss
    @State private var amount = ""
    @State private var currency = ""
    @State private var error = ""
    @State private var title = ""
    @State private var income = false
    @State private var date = Date.now
    @State private var reviewing = false
    private var valid: Bool { error.isEmpty && (Decimal(string: amount) ?? 0) > 0 }
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 28) {
                    HStack(spacing: 12) {
                        CanvasAccountIcon(kind: account.kind)
                        Text(account.displayName(spanish)).font(CuadraoTypography.action)
                    }.padding(.top, 8)
                    if reviewing {
                        Text((income ? "+" : "−") + CanvasMoney.format(Decimal(string: amount) ?? 0, currency: account.currency))
                            .font(CuadraoTypography.amount).monospacedDigit()
                        LabeledContent(spanish ? "Moneda" : "Currency", value: account.currency)
                        LabeledContent(spanish ? "Tipo" : "Type", value: income ? (spanish ? "Ingreso" : "Income") : (spanish ? "Gasto" : "Expense"))
                        if !title.isEmpty { LabeledContent(spanish ? "Concepto" : "Description", value: title) }
                        LabeledContent(spanish ? "Fecha" : "Date") { Text(date, format: .dateTime.day().month().year()) }
                    } else {
                        Picker(spanish ? "Tipo" : "Type", selection: $income) {
                            Text(spanish ? "Gasto" : "Expense").tag(false)
                            Text(spanish ? "Ingreso" : "Income").tag(true)
                        }.pickerStyle(.segmented)
                        CuadraoAmountField(raw: $amount, currency: $currency, error: $error, spanish: spanish, currencySelectable: false)
                        TextField(spanish ? "Concepto (opcional)" : "Description (optional)", text: $title)
                            .modifier(RegistrationField())
                        DatePicker(spanish ? "Fecha" : "Date", selection: $date, in: ...Date.now, displayedComponents: .date)
                    }
                }.padding(24)
            }.background(WelcomePalette.background)
                .navigationTitle(reviewing ? (spanish ? "Revisar movimiento" : "Review transaction") : (spanish ? "Añadir movimiento" : "Add transaction"))
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .cancellationAction) {
                        Button(reviewing ? (spanish ? "Atrás" : "Back") : (spanish ? "Cancelar" : "Cancel")) {
                            if reviewing { reviewing = false } else { dismiss() }
                        }
                    }
                }
                .safeAreaInset(edge: .bottom) {
                    RegistrationButton(title: reviewing ? (spanish ? "Guardar" : "Save") : (spanish ? "Revisar" : "Review"), enabled: valid) {
                        if reviewing {
                            data.activity.insert(CanvasActivity(accountID: account.id,
                                title: title.isEmpty ? (income ? (spanish ? "Ingreso" : "Income") : (spanish ? "Gasto" : "Expense")) : title,
                                amount: Decimal(string: amount) ?? 0, date: date, income: income), at: 0)
                            dismiss()
                        } else {
                            UIApplication.shared.sendAction(#selector(UIResponder.resignFirstResponder), to: nil, from: nil, for: nil)
                            reviewing = true
                        }
                    }.padding(24).background(WelcomePalette.background)
                }
        }.tint(WelcomePalette.pine).onAppear { currency = account.currency }
    }
}
