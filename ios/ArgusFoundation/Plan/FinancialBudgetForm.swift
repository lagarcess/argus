import SwiftUI
import ArgusSession

struct FinancialBudgetForm: View {
    @ObservedObject var model: FinancialBudgetModel
    @ObservedObject var loop: FinancialLoopModel
    @ObservedObject var draft: FinancialBudgetDraft
    @Environment(\.dismiss) private var dismiss
    @Environment(\.locale) private var locale
    @FocusState private var focused: Bool
    private var accounts: [FinancialAccount] {
        (model.options?.accounts ?? []).filter {
            $0.currency == draft.currency && (model.options?.eligibility["expense"] ?? []).contains($0.type)
        }
    }
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 22) {
                    Group {
                        field("budget.name", id: "budget.name", text: $draft.name)
                        Picker("accounts.currency", selection: $draft.currency) {
                            ForEach(Array(Set(model.options?.accounts.map(\.currency) ?? [draft.currency])).sorted(), id: \.self) {
                                Text(verbatim: $0).tag($0)
                            }
                        }.accessibilityIdentifier("budget.currency")
                        field("budget.limit", id: "budget.limit", text: $draft.limit).keyboardType(.decimalPad)
                        DatePicker("budget.month", selection: $draft.date, displayedComponents: .date)
                            .accessibilityIdentifier("budget.month").environment(\.timeZone, TimeZone(secondsFromGMT: 0)!)
                        Text("budget.calendarMonth").font(ArgusStyle.body(12, relativeTo: .caption)).foregroundStyle(ArgusStyle.secondary)
                        Text(verbatim: loop.plan.projection?.selection.timeZone ?? "").font(ArgusStyle.body(12, relativeTo: .caption))
                        Text("plan.includedAccounts").font(ArgusStyle.display(21))
                        ForEach(accounts) { account in
                            Toggle(isOn: Binding(get: { draft.accountIDs.contains(account.id) }, set: { selected in
                                if selected { draft.accountIDs.insert(account.id) } else { draft.accountIDs.remove(account.id) }
                            })) {
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(account.nickname ?? NSLocalizedString("accounts.type." + account.type, comment: ""))
                                    if account.archived { Text("accounts.archived").font(ArgusStyle.body(11, relativeTo: .caption)) }
                                }
                            }.accessibilityIdentifier("budget.account." + account.id.uuidString)
                        }
                        Text("budget.categories").font(ArgusStyle.display(21))
                        ForEach(model.options?.categories ?? [], id: \.self) { category in
                            Toggle(LocalizedStringKey("loop.category." + category), isOn: Binding(get: { draft.categoryIDs.contains(category) }, set: { selected in
                                if selected { draft.categoryIDs.insert(category) } else { draft.categoryIDs.remove(category) }
                            })).accessibilityIdentifier("budget.category." + category)
                        }
                        Toggle("budget.uncategorized", isOn: $draft.includeUncategorized).accessibilityIdentifier("budget.uncategorized")
                        Text("budget.disclosure").font(ArgusStyle.body(12, relativeTo: .caption)).foregroundStyle(ArgusStyle.secondary)
                    }.disabled(model.saving || loop.pendingConfirmation != nil)
                    if model.options == nil {
                        ProgressView("accounts.loading")
                        Button("accounts.retry") { Task { await model.loadOptions() } }.frame(minHeight: 44)
                    }
                    if let error = model.errorKey { Text(LocalizedStringKey(error)).accessibilityIdentifier("budget.form.error") }
                    if loop.pendingConfirmation != nil { PlanPendingView(loop: loop) }
                    else {
                        Button("budget.save") { focused = false; Task { await model.save(locale: locale) } }
                            .buttonStyle(PillButtonStyle()).disabled(!draft.ready || model.saving || model.options == nil).accessibilityIdentifier("budget.save")
                    }
                }.padding(24).font(ArgusStyle.body())
            }.background(ArgusStyle.background).scrollDismissesKeyboard(.interactively)
                .navigationTitle(draft.existing == nil ? "budget.add" : "budget.edit").navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .cancellationAction) { Button("accounts.cancel") { dismiss() }.disabled(model.saving) }
                    ToolbarItemGroup(placement: .keyboard) { Spacer(); Button("accounts.keyboard.done") { focused = false } }
                }.interactiveDismissDisabled(model.saving)
                .onChange(of: draft.currency) { _, _ in draft.accountIDs = [] }
        }
    }
    private func field(_ title: LocalizedStringKey, id: String, text: Binding<String>) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title)
            TextField(title, text: text).focused($focused).padding(14)
                .overlay(RoundedRectangle(cornerRadius: 14).stroke(ArgusStyle.line)).accessibilityIdentifier(id)
        }
    }
}
