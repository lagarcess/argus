import SwiftUI
import ArgusSession

struct FinancialHomeDestination: View {
    @EnvironmentObject private var auth: ProfileAuthModel
    @Binding var destination: AppDestination
    let showProfile: () -> Void

    var body: some View {
        if auth.state == .authenticated, let loop = auth.financialLoop, let accounts = auth.accounts {
            FinancialHomeView(loop: loop, accounts: accounts, destination: $destination)
        } else {
            ScrollView {
                VStack(alignment: .leading, spacing: 24) {
                    PersonalContext()
                    Text("loop.home.welcome").font(ArgusStyle.display())
                    Text("accounts.gate.body").foregroundStyle(ArgusStyle.secondary)
                    Button("auth.signIn", action: showProfile).buttonStyle(PillButtonStyle())
                }.padding(24)
            }
        }
    }
}

struct FinancialHomeView: View {
    @ObservedObject var loop: FinancialLoopModel
    @ObservedObject var accounts: AccountsModel
    @ObservedObject private var plan: FinancialPlanModel
    @Binding var destination: AppDestination
    @Environment(\.locale) private var locale
    @State private var choosingAccount = false

    init(loop: FinancialLoopModel, accounts: AccountsModel, destination: Binding<AppDestination>) {
        self.loop = loop; self.accounts = accounts; self.plan = loop.plan; self._destination = destination
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 32) {
                PersonalContext()
                if loop.pendingConfirmation != nil {
                    VStack(alignment: .leading, spacing: 8) {
                        Text(LocalizedStringKey(loop.pendingTitle)).font(ArgusStyle.body(15))
                        Text("loop.pending.body").font(ArgusStyle.body(12, relativeTo: .caption)).foregroundStyle(ArgusStyle.secondary)
                        Button("loop.pending.retry") { Task { await loop.retryPending() } }
                            .buttonStyle(PillButtonStyle()).disabled(loop.recovering)
                            .accessibilityIdentifier("loop.pending.retry")
                    }.padding(16).overlay(RoundedRectangle(cornerRadius: 14).stroke(ArgusStyle.line))
                }
                if let recoveryError = loop.recoveryErrorKey {
                    Text(LocalizedStringKey(recoveryError)).foregroundStyle(ArgusStyle.secondary)
                }
                if let home = loop.home {
                    if home.currencies.isEmpty {
                        Text("loop.home.empty").font(ArgusStyle.display())
                        Button("accounts.add") { destination = .accounts; accounts.create() }.buttonStyle(PillButtonStyle())
                    }
                    ForEach(home.currencies, id: \.currency) { summary in currencySummary(summary) }
                    Button { choosingAccount = true } label: {
                        HStack {
                            VStack(alignment: .leading, spacing: 6) {
                                Text("loop.record")
                                Text("loop.record.hint").font(ArgusStyle.body(12, relativeTo: .caption)).foregroundStyle(ArgusStyle.secondary)
                            }
                            Spacer(); Image(systemName: "chevron.right").font(.system(size: 12))
                        }.padding(.vertical, 16).contentShape(Rectangle())
                    }.buttonStyle(.plain).disabled(accounts.accounts.isEmpty || loop.pendingConfirmation != nil).accessibilityIdentifier("home.record")
                    if !home.recentActivity.isEmpty {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("loop.recent").font(ArgusStyle.display(22))
                            ForEach(home.recentActivity, id: \.recordId) { activity in
                                if let account = accounts.accounts.first(where: { $0.id == activity.accountId }) {
                                    Button { destination = .accounts; Task { await accounts.open(account); await loop.open(account) } } label: {
                                        FinancialActivityRow(activity: activity, currency: account.currency)
                                    }.buttonStyle(.plain)
                                }
                            }
                        }
                    }
                    FinancialBudgetList(plan: plan, model: loop.budgets, origin: .home, compact: true)
                    FinancialComingUpView(model: loop.plan, viewPlan: { destination = .plan })
                    VStack(alignment: .leading, spacing: 16) {
                        HStack {
                            Text("destination.accounts").font(ArgusStyle.display(22))
                            Spacer()
                            Button("loop.viewAll") { destination = .accounts }.font(ArgusStyle.body(12, relativeTo: .caption))
                        }
                        ForEach(accounts.accounts.filter { !$0.archived }.prefix(3)) { account in
                            Button { destination = .accounts; Task { await accounts.open(account); await loop.open(account) } } label: {
                                AccountRow(account: account)
                            }.buttonStyle(.plain)
                        }
                    }
                }
                if plan.loading { ProgressView("accounts.loading") }
                if let error = plan.errorKey {
                    Text(LocalizedStringKey(error)).foregroundStyle(ArgusStyle.secondary)
                    Button("accounts.retry") { Task { await loop.refresh() } }.frame(minHeight: 44)
                }
            }.padding(.horizontal, 24).padding(.top, 20).padding(.bottom, 24)
        }
        .task(id: accounts.identity?.revision) { await accounts.load(); await loop.refresh() }
        .onChange(of: accounts.accounts) { _, _ in Task { await loop.refresh() } }
        .refreshable { await accounts.load(); await loop.refresh() }
        .confirmationDialog("loop.chooseAccount", isPresented: $choosingAccount, titleVisibility: .visible) {
            ForEach(accounts.accounts.filter { !$0.archived }) { account in
                Button(account.nickname ?? NSLocalizedString("accounts.type." + account.type, comment: "")) { loop.record(account) }
            }
        }
    }

    private func currencySummary(_ summary: FinancialCurrencySummary) -> some View {
        VStack(alignment: .leading, spacing: 20) {
            VStack(alignment: .leading, spacing: 14) {
                HStack(spacing: 6) {
                    Text("loop.home.netWorth"); Text(verbatim: "· " + summary.currency)
                }.font(ArgusStyle.body(14, relativeTo: .subheadline))
                if summary.knownAccounts > 0 {
                    Text(verbatim: money(summary.netWorthMinor, summary)).font(ArgusStyle.display(36)).monospacedDigit()
                        .accessibilityIdentifier("home.netWorth." + summary.currency)
                } else { Text("accounts.unknown").font(ArgusStyle.display(22)) }
                if summary.knownAccounts > 0 {
                    Text("loop.home.source").font(ArgusStyle.body(12, relativeTo: .caption)).foregroundStyle(ArgusStyle.secondary)
                }
                if summary.unknownAccounts > 0 {
                    Text(verbatim: String(format: NSLocalizedString("loop.home.unknownCount", comment: ""), summary.unknownAccounts))
                        .font(ArgusStyle.body(12, relativeTo: .caption)).foregroundStyle(ArgusStyle.secondary)
                }
            }
            VStack(spacing: 12) {
                if summary.knownAccounts > 0 {
                    summaryRow("loop.home.cash", value: money(summary.cashMinor, summary))
                    if summary.otherAssetsMinor != "0" { summaryRow("loop.home.other", value: money(summary.otherAssetsMinor, summary)) }
                    summaryRow("loop.home.debt", value: money(summary.debtsMinor, summary))
                }
                if let period = loop.home?.period,
                   let income = summary.grossIncomeMinor,
                   let purchases = summary.grossPurchasesMinor,
                   let refunds = summary.refundsMinor,
                   let net = summary.netSpendingMinor {
                    Text(verbatim: period.month).font(ArgusStyle.body(12, relativeTo: .caption))
                        .foregroundStyle(ArgusStyle.secondary)
                    summaryRow("loop.home.income", value: money(income, summary))
                    summaryRow("loop.home.purchases", value: money(purchases, summary))
                    summaryRow("loop.home.refunds", value: money(refunds, summary))
                    summaryRow("loop.home.netSpending", value: money(net, summary))
                    Text("loop.home.recordedOnly").font(ArgusStyle.body(11, relativeTo: .caption))
                        .foregroundStyle(ArgusStyle.secondary)
                } else {
                    summaryRow("loop.home.spending", value: money(summary.recordedSpendingMinor, summary))
                }
            }.padding(.top, 6)
        }
    }
    private func summaryRow(_ title: LocalizedStringKey, value: String) -> some View {
        HStack { Text(title); Spacer(); Text(verbatim: value).monospacedDigit() }.font(ArgusStyle.body(12, relativeTo: .caption))
    }
    private func money(_ minor: String, _ summary: FinancialCurrencySummary) -> String {
        summary.currency + " " + AccountPresentation.amount(AccountPresentation.decimal(minor, digits: summary.currencyFractionDigits), locale: locale)
    }
}

struct AccountRow: View {
    let account: FinancialAccount
    @Environment(\.locale) private var locale
    var body: some View {
        HStack(spacing: 14) {
            Image(systemName: AccountPresentation.symbol(account.type)).font(.system(size: 21)).frame(width: 24)
            VStack(alignment: .leading, spacing: 7) {
                Text(account.nickname ?? NSLocalizedString("accounts.type." + account.type, comment: "")).font(ArgusStyle.body(15))
                Text(LocalizedStringKey("accounts.type." + account.type)).font(ArgusStyle.body(12, relativeTo: .caption)).foregroundStyle(ArgusStyle.secondary)
            }
            Spacer(minLength: 8)
            Group {
                if let amount = account.balance.amount {
                    Text(verbatim: account.currency + " " + AccountPresentation.amount(amount, locale: locale)).monospacedDigit()
                } else { Text("accounts.unknown") }
            }.font(ArgusStyle.body(12, relativeTo: .caption)).multilineTextAlignment(.trailing)
        }.padding(.vertical, 18).frame(maxWidth: .infinity, alignment: .leading)
            .contentShape(Rectangle())
            .overlay(alignment: .bottom) { Rectangle().fill(ArgusStyle.line).frame(height: 1) }
            .accessibilityElement(children: .combine)
    }
}
