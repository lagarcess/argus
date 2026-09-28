import SwiftUI

/// Display-only fixtures. These strings are never parsed, added, or persisted.
struct SampleAccount: Identifiable {
    let id: String
    let nameKey: String
    let kindKey: String
    let symbol: String
    let amount: String

    static let credit = SampleAccount(id: "credit", nameKey: "account.card", kindKey: "account.credit",
                                      symbol: "creditcard", amount: "DOP 8,500.00")

    static let all: [SampleAccount] = [
        .init(id: "checking", nameKey: "account.everyday", kindKey: "account.checking", symbol: "building.columns", amount: "DOP 72,729.25"),
        .init(id: "cash", nameKey: "account.pocket", kindKey: "account.cash", symbol: "banknote", amount: "DOP 3,500.00"),
        .init(id: "savings", nameKey: "account.safety", kindKey: "account.savings", symbol: "tray", amount: "DOP 60,000.00"),
        credit
    ]
}

enum SampleFinancialSnapshot {
    static let netWorth = "RD$127,729.25"
    static let cashAndBankAccounts = "DOP 136,229.25"
    static let owed = SampleAccount.credit.amount
}

struct PersonalContext: View {
    var body: some View {
        Text("context.personal").font(ArgusStyle.body(14, relativeTo: .subheadline))
            .foregroundStyle(ArgusStyle.secondary)
    }
}

struct HomeSampleView: View {
    @Binding var destination: AppDestination
    let showSample: () -> Void

    var body: some View {
        SamplePage {
            PersonalContext()
            VStack(alignment: .leading, spacing: 16) {
                Text("home.networth").font(ArgusStyle.body(14, relativeTo: .subheadline))
                Text(verbatim: SampleFinancialSnapshot.netWorth)
                    .font(ArgusStyle.display(36, relativeTo: .largeTitle))
                    .minimumScaleFactor(0.65)
                    .lineLimit(1)
                Text("home.balances").font(ArgusStyle.body(12, relativeTo: .caption))
                    .foregroundStyle(ArgusStyle.secondary)
            }
            VStack(spacing: 0) {
                SampleRow(title: "home.cash", subtitle: "sample.fixture", trailing: SampleFinancialSnapshot.cashAndBankAccounts)
                SampleRow(title: "home.owe", subtitle: "sample.fixture", trailing: SampleFinancialSnapshot.owed)
            }
            VStack(spacing: 0) {
                SampleRow(title: "home.record", subtitle: "sample.unavailable", action: showSample)
                SampleRow(title: "home.lunch", subtitle: "home.activity", action: showSample)
            }
            VStack(alignment: .leading, spacing: 14) {
                Text("home.coming").font(ArgusStyle.display(23, relativeTo: .title2))
                    .accessibilityAddTraits(.isHeader)
                SampleRow(title: "home.viewplan", subtitle: "home.planhint", action: { destination = .plan })
            }
        }
    }
}

struct AccountsSampleView: View {
    let showSample: () -> Void
    var body: some View {
        SamplePage {
            PersonalContext()
            Text("accounts.count").font(ArgusStyle.display(24, relativeTo: .title2))
                .accessibilityAddTraits(.isHeader)
            VStack(spacing: 0) {
                ForEach(SampleAccount.all) { account in
                    SampleRow(title: LocalizedStringKey(account.nameKey), subtitle: LocalizedStringKey(account.kindKey),
                              symbol: account.symbol, trailing: account.amount, action: showSample)
                }
            }
            Button(action: showSample) {
                Text("accounts.add").frame(maxWidth: .infinity)
            }
            .buttonStyle(PillButtonStyle())
            Text("accounts.disclosure")
                .font(ArgusStyle.body(12, relativeTo: .caption)).foregroundStyle(ArgusStyle.secondary)
        }
    }
}

struct ChatSampleView: View {
    let showSample: () -> Void
    var body: some View {
        ScrollView {
            VStack(spacing: 28) {
                SampleNotice().frame(maxWidth: .infinity, alignment: .leading)
                VStack(spacing: 22) {
                    ArgusMark().fill(ArgusStyle.ink.opacity(0.65))
                        .frame(width: 52, height: 52).accessibilityHidden(true)
                    Text("chat.greeting").font(ArgusStyle.display(30))
                        .multilineTextAlignment(.center)
                    Text("chat.description").font(ArgusStyle.body(14, relativeTo: .subheadline))
                        .foregroundStyle(ArgusStyle.secondary).multilineTextAlignment(.center)
                }
                .padding(.vertical, 44)
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 10) {
                        Button("chat.starter.compare", action: showSample)
                        Button("chat.starter.spending", action: showSample)
                    }
                    .buttonStyle(PillButtonStyle(primary: false))
                }
                VStack(alignment: .leading, spacing: 18) {
                    Text("chat.placeholder").foregroundStyle(ArgusStyle.secondary)
                    HStack {
                        Image(systemName: "plus").accessibilityHidden(true)
                        Spacer()
                        Text("sample.unavailable")
                            .font(ArgusStyle.body(12, relativeTo: .caption))
                        Image(systemName: "arrow.up.circle").accessibilityHidden(true)
                    }
                }
                .padding(20)
                .background(ArgusStyle.surface, in: RoundedRectangle(cornerRadius: 24))
                .accessibilityElement(children: .combine)
                .accessibilityLabel("chat.composer.unavailable")
                Text("chat.nothing.sent").font(ArgusStyle.body(12, relativeTo: .caption))
                    .foregroundStyle(ArgusStyle.secondary)
            }
            .padding(ArgusStyle.pageInset)
        }
    }
}

enum PlanSection: String, CaseIterable {
    case overview, goals, budgets, debts
    var title: LocalizedStringKey { LocalizedStringKey("plan." + rawValue) }
}

struct PlanSampleView: View {
    @State private var section = PlanSection.overview
    var body: some View {
        SamplePage {
            PersonalContext()
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 20) {
                    ForEach(PlanSection.allCases, id: \.self) { item in
                        Button { section = item } label: {
                            Text(item.title)
                                .font(ArgusStyle.body(14, relativeTo: .subheadline))
                                .frame(minWidth: 44, minHeight: 48)
                                .contentShape(Rectangle())
                                .foregroundStyle(section == item ? ArgusStyle.ink : ArgusStyle.secondary)
                                .overlay(alignment: .bottom) {
                                    Rectangle().fill(section == item ? ArgusStyle.ink : .clear).frame(height: 2)
                                }
                        }
                        .buttonStyle(.plain)
                        .accessibilityIdentifier("plan.\(item.rawValue)")
                        .accessibilityAddTraits(section == item ? .isSelected : [])
                    }
                }
            }
            VStack(alignment: .leading, spacing: 18) {
                Image(systemName: "target").font(.system(size: 32)).accessibilityHidden(true)
                Text(section.title).font(ArgusStyle.display())
                Text(LocalizedStringKey("plan." + section.rawValue + ".empty"))
                    .foregroundStyle(ArgusStyle.secondary)
                    .fixedSize(horizontal: false, vertical: true)
                Text("plan.disclosure").font(ArgusStyle.body(12, relativeTo: .caption))
                    .foregroundStyle(ArgusStyle.secondary)
            }
        }
    }
}

struct SearchSampleView: View {
    @Binding var destination: AppDestination
    @State private var query = ""
    @FocusState private var focused: Bool
    @Environment(\.locale) private var locale

    private var matches: [SampleAccount] {
        SampleAccount.all.filter {
            query.isEmpty || localized($0.nameKey).localizedCaseInsensitiveContains(query)
                || localized($0.kindKey).localizedCaseInsensitiveContains(query)
        }
    }

    private func localized(_ key: String) -> String {
        String(localized: String.LocalizationValue(key), locale: locale)
    }

    var body: some View {
        SamplePage {
            HStack(spacing: 12) {
                Image(systemName: "magnifyingglass").accessibilityHidden(true)
                TextField("search.placeholder", text: $query)
                    .font(ArgusStyle.body())
                    .focused($focused)
                    .autocorrectionDisabled()
                    .submitLabel(.search)
                    .onSubmit { focused = false }
                    .accessibilityIdentifier("search.field")
                if !query.isEmpty {
                    IconButton(title: "search.clear", symbol: "xmark.circle", identifier: "search.clear") { query = "" }
                }
            }
            .frame(minHeight: 48)
            .overlay(alignment: .bottom) { Rectangle().fill(ArgusStyle.line).frame(height: 1) }
            Text("search.scope").font(ArgusStyle.body(12, relativeTo: .caption))
                .foregroundStyle(ArgusStyle.secondary)
            VStack(alignment: .leading, spacing: 0) {
                Text("destination.accounts").font(ArgusStyle.display(23, relativeTo: .title2))
                    .accessibilityAddTraits(.isHeader)
                ForEach(matches) { account in
                    SampleRow(title: LocalizedStringKey(account.nameKey), subtitle: LocalizedStringKey(account.kindKey)) {
                        focused = false
                        destination = .accounts
                    }
                }
                if matches.isEmpty {
                    Text("search.empty").padding(.vertical, 24)
                        .foregroundStyle(ArgusStyle.secondary)
                }
            }
        }
        .onChange(of: destination) { _, newValue in
            if newValue != .search { focused = false }
        }
    }
}
