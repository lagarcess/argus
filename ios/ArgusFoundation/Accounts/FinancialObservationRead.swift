import Foundation
import ArgusSession

enum PersonalObservationRead: Equatable, Sendable {
    enum IncompleteReason: Equatable, Sendable {
        case pageFailure, verificationFailure, pageLimit, repeatedCursor
    }
    case complete(PersonalAccountObservations)
    case stale, incomplete(IncompleteReason), unavailable, cancelled
}

struct PersonalAccountObservations: Equatable, Sendable {
    struct CurrentMetadata: Equatable, Sendable {
        let nickname: String?
        let type: String
        let archived: Bool
        let ownershipShareBps: Int
        let updatedAt: String
    }
    struct Observation: Equatable, Sendable {
        enum Kind: String, Sendable { case opening, balanceCheck = "balance_check", valueUpdate = "value_update" }
        let recordID: UUID
        let revision: Int
        let kind: Kind
        let amountMinor: Int64
        let asOf: String
        let timeZone: String
        let recordedAt: String
        let instant: Date
        /// Opening is zero; checks count upward in accepted review order.
        let reviewOrder: Int

        fileprivate init?(recordID: UUID, revision: Int, kind: Kind, amountMinor: Int64,
                          asOf: String, timeZone: String, recordedAt: String, reviewOrder: Int) {
            guard revision > 0, let instant = AccountPresentation.parseDate(asOf),
                  AccountPresentation.parseDate(recordedAt) != nil else { return nil }
            self.recordID = recordID; self.revision = revision; self.kind = kind
            self.amountMinor = amountMinor; self.asOf = asOf; self.timeZone = timeZone
            self.recordedAt = recordedAt; self.instant = instant
            self.reviewOrder = reviewOrder
        }
    }
    enum Baseline: Equatable, Sendable { case periodStart, partialBaseline }
    enum Delta: Equatable, Sendable { case minor(Int64), unavailableOverflow }
    enum Selection: Equatable, Sendable {
        case none
        case unavailableOrder
        case single(Observation, baseline: Baseline)
        case pair(opening: Observation, closing: Observation, baseline: Baseline, delta: Delta)
    }

    let accountID: UUID
    let accountVersion: Int
    let currency: String
    let currencyFractionDigits: Int
    let currentMetadata: CurrentMetadata
    let observations: [Observation]
    let period: FinancialHomePeriod
    let selection: Selection

    private init(account: FinancialAccount, observations: [Observation], period: FinancialHomePeriod, selection: Selection) {
        accountID = account.id; accountVersion = account.version
        currency = account.currency; currencyFractionDigits = account.currencyFractionDigits
        currentMetadata = CurrentMetadata(nickname: account.nickname, type: account.type, archived: account.archived,
            ownershipShareBps: account.ownershipShareBps, updatedAt: account.updatedAt)
        self.observations = observations; self.period = period; self.selection = selection
    }

    static func accepted(requestedID: UUID, before: FinancialAccount, checksInServerOrder checks: [FinancialCheck],
                         after: FinancialAccount, period: FinancialHomePeriod) -> PersonalObservationRead {
        guard before.id == requestedID, after.id == requestedID, before.version == after.version,
              before.currency == after.currency, before.currencyFractionDigits == after.currencyFractionDigits else { return .stale }
        guard let start = AccountPresentation.parseDate(period.startAt),
              let end = AccountPresentation.parseDate(period.endAtExclusive), start < end else { return .unavailable }
        var facts: [Observation] = []
        var ids = Set<UUID>()
        if let opening = before.opening {
            guard let fact = Observation(recordID: opening.recordId, revision: opening.revision, kind: .opening,
                amountMinor: opening.amountMinor, asOf: opening.asOf, timeZone: opening.timeZone,
                recordedAt: opening.recordedAt, reviewOrder: 0) else { return .unavailable }
            facts.append(fact); ids.insert(fact.recordID)
        }
        for (index, check) in checks.enumerated() {
            guard let kind = Observation.Kind(rawValue: check.kind), kind != .opening,
                  ids.insert(check.recordId).inserted,
                  let fact = Observation(recordID: check.recordId, revision: check.revision, kind: kind,
                    amountMinor: check.observedAmountMinor, asOf: check.asOf, timeZone: check.timeZone,
                    recordedAt: check.recordedAt, reviewOrder: checks.count - index) else { return .unavailable }
            facts.append(fact)
        }
        let ordered = facts.sorted { left, right in
            if left.instant != right.instant { return left.instant < right.instant }
            return left.reviewOrder < right.reviewOrder
        }
        let eligible = ordered.filter { $0.instant < end }
        let reviewOrder = eligible.sorted { $0.reviewOrder < $1.reviewOrder }
        let prior = eligible.last { $0.instant <= start }
        let selection: Selection
        let reviewsMoveBackwardInTime = zip(reviewOrder, reviewOrder.dropFirst()).contains { $0.0.instant > $0.1.instant }
        if reviewsMoveBackwardInTime {
            selection = .unavailableOrder
        } else if let opening = prior ?? eligible.first, let closing = eligible.last {
            let baseline: Baseline = prior == nil ? .partialBaseline : .periodStart
            if opening.recordID == closing.recordID, opening.revision == closing.revision {
                selection = .single(opening, baseline: baseline)
            } else {
                let (delta, overflow) = closing.amountMinor.subtractingReportingOverflow(opening.amountMinor)
                selection = .pair(opening: opening, closing: closing, baseline: baseline,
                                  delta: overflow ? .unavailableOverflow : .minor(delta))
            }
        } else { selection = .none }
        return .complete(Self(account: after, observations: ordered, period: period, selection: selection))
    }
}
