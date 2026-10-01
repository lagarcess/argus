import Foundation
import Observation

// Fictional, device-local collaboration. No invites, payments or financial APIs.
struct PlanMember: Identifiable, Codable, Equatable {
    var id = UUID()
    var name: String
    var symbol: String
}
struct PlanSharedExpense: Identifiable, Codable, Equatable {
    var id = UUID()
    var title: String
    var cents: Int
    var payer: UUID
    var shares: [UUID: Int]
    var draft = false
    var receipt: Data?
    static func equal(_ cents: Int, among members: [UUID]) -> [UUID: Int] {
        guard cents >= 0, !members.isEmpty else { return [:] }
        return Dictionary(uniqueKeysWithValues: members.enumerated().map { ($0.element, cents / members.count + ($0.offset < cents % members.count ? 1 : 0)) })
    }
}
struct PlanRepayment: Identifiable, Codable, Equatable {
    var id = UUID()
    var from: UUID
    var to: UUID
    var cents: Int
}
enum PlanGroupKind: String, Codable, CaseIterable {
    case trip, saving
    func title(_ es: Bool) -> String { self == .trip ? (es ? "Compartir gastos" : "Share expenses") : (es ? "Ahorrar juntos" : "Save together") }
}
struct PlanGroup: Identifiable, Codable, Equatable {
    var id = UUID()
    var name: String
    var kind: PlanGroupKind = .trip
    var currency = "DOP"
    var look: CanvasPlanLook = .coast
    var cover: Data?
    var members: [PlanMember]
    var estimatedCents: Int = 4800000
    var expectedPeople = 8
    var expenses: [PlanSharedExpense] = []
    var repayments: [PlanRepayment] = []
    var archived = false
    var me: UUID { members[0].id }
    var total: Int { expenses.filter { !$0.draft }.reduce(0) { $0 + $1.cents } }
    func paid(_ id: UUID) -> Int { expenses.filter { !$0.draft && $0.payer == id }.reduce(0) { $0 + $1.cents } }
    func share(_ id: UUID) -> Int { expenses.filter { !$0.draft }.reduce(0) { $0 + ($1.shares[id] ?? 0) } }
    func balance(_ id: UUID) -> Int {
        paid(id) - share(id) + repayments.filter { $0.from == id }.reduce(0) { $0 + $1.cents }
        - repayments.filter { $0.to == id }.reduce(0) { $0 + $1.cents }
    }
    var progress: Double { min(1, Double(total) / Double(max(1, estimatedCents))) }
    var valid: Bool {
        PlanCurrency.supported.contains(currency) && !name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && !members.isEmpty && estimatedCents > 0 && expectedPeople > 0
    }
    mutating func record(_ expense: PlanSharedExpense) -> Bool {
        let ids = Set(members.map(\.id))
        guard expense.cents >= (expense.draft ? 0 : 1), expense.cents <= CanvasMoney.maximumCents, ids.contains(expense.payer),
              !expense.title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
              expense.draft || (expense.shares.values.allSatisfy { $0 >= 0 } && Set(expense.shares.keys).isSubset(of: ids)
                && expense.shares.values.reduce(0, +) == expense.cents) else { return false }
        if let index = expenses.firstIndex(where: { $0.id == expense.id }) { expenses[index] = expense }
        else { expenses.append(expense) }
        return true
    }
    mutating func repay(from: UUID, to: UUID, cents: Int) -> Bool {
        guard from != to, cents > 0, cents <= -balance(from), cents <= balance(to) else { return false }
        repayments.append(.init(from: from, to: to, cents: cents)); return true
    }
}

// Earlier previews supported DOP only. Preserve those saved groups and amounts.
extension PlanGroup {
    enum CodingKeys: String, CodingKey {
        case id, name, kind, currency, look, cover, members, estimatedCents, expectedPeople, expenses, repayments, archived
    }
    init(from decoder: Decoder) throws {
        let saved = try decoder.container(keyedBy: CodingKeys.self)
        id = try saved.decode(UUID.self, forKey: .id)
        name = try saved.decode(String.self, forKey: .name)
        kind = try saved.decode(PlanGroupKind.self, forKey: .kind)
        currency = try saved.decodeIfPresent(String.self, forKey: .currency) ?? "DOP"
        look = try saved.decode(CanvasPlanLook.self, forKey: .look)
        cover = try saved.decodeIfPresent(Data.self, forKey: .cover)
        members = try saved.decode([PlanMember].self, forKey: .members)
        estimatedCents = try saved.decode(Int.self, forKey: .estimatedCents)
        expectedPeople = try saved.decode(Int.self, forKey: .expectedPeople)
        expenses = try saved.decode([PlanSharedExpense].self, forKey: .expenses)
        repayments = try saved.decode([PlanRepayment].self, forKey: .repayments)
        archived = try saved.decode(Bool.self, forKey: .archived)
    }
}

@Observable final class CuadraoGroupPreview {
    var groups: [PlanGroup] = []
    private let defaults: UserDefaults?
    private let key = "cuadrao.design.groups.v1"
    init(spanish: Bool, defaults: UserDefaults? = .standard, reset: Bool = false, empty: Bool = false) {
        self.defaults = defaults
        if !reset, !empty, let data = defaults?.data(forKey: key), let saved = try? JSONDecoder().decode([PlanGroup].self, from: data) { groups = saved }
        else { resetExamples(spanish: spanish, empty: empty) }
    }
    func group(_ id: UUID) -> PlanGroup? { groups.first { $0.id == id } }
    func save(_ group: PlanGroup) {
        guard group.valid, self.group(group.id).map({ $0.currency == group.currency }) ?? true else { return }
        if let i = groups.firstIndex(where: { $0.id == group.id }) { groups[i] = group } else { groups.append(group) }
        persist()
    }
    func archive(_ id: UUID, _ archived: Bool) {
        guard var group = group(id) else { return }; group.archived = archived; save(group)
    }
    func resetExamples(spanish es: Bool, empty: Bool = false) {
        let members = [PlanMember(name: es ? "Tú" : "You", symbol: "sun.max.fill"), .init(name: "Ana", symbol: "leaf.fill"), .init(name: "Leo", symbol: "moon.fill"), .init(name: "Sol", symbol: "sparkle")]
        var trip = PlanGroup(name: es ? "Samaná con los panas" : "Samaná with friends", members: members)
        _ = trip.record(.init(title: es ? "La casa del finde" : "The weekend house", cents: 1200000, payer: members[0].id, shares: PlanSharedExpense.equal(1200000, among: members.map(\.id))))
        var saving = PlanGroup(name: es ? "Nuestro próximo viaje" : "Our next adventure", kind: .saving, look: .sunshine, members: members, estimatedCents: 8000000, expectedPeople: 4)
        _ = saving.record(.init(title: es ? "Primer aporte" : "First contribution", cents: 1000000, payer: members[0].id, shares: [members[0].id: 1000000]))
        groups = empty ? [] : [trip, saving]; persist()
    }
    private func persist() {
        if let data = try? JSONEncoder().encode(groups) { defaults?.set(data, forKey: key) }
    }
}
