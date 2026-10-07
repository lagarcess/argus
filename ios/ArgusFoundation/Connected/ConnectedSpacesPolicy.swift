import Foundation

/// What the Home space row and the Spaces sheet offer, read from the Household model.
struct ConnectedSpacesPolicy: Equatable {
    enum Outcome: Equatable {
        /// Leave for Personal and open the Household introduction (create or join).
        case startHousehold
        /// Open the management of the Household that exists.
        case manageHousehold
        /// Designed, no backend: shown disabled.
        case comingSoon
        /// Nothing to manage yet: say so, create nothing.
        case emptyManage
    }

    let hasHousehold: Bool

    init(households: Int, active: Bool, pending: Bool) {
        hasHousehold = households > 0 || active || pending
    }

    @MainActor init(model: HouseholdModel) {
        self.init(households: model.households.count, active: model.active, pending: model.pending != nil)
    }

    /// With a household the row shows its menu; without one it shows Hogar as the way in.
    var showsHouseholdMenu: Bool { hasHousehold }
    var household: Outcome { .startHousehold }
    /// Business and custom spaces have no backend, so they are never an action.
    var extraSpace: Outcome { .comingSoon }
    var manage: Outcome { hasHousehold ? .manageHousehold : .emptyManage }
}

extension HouseholdModel {
    /// The one way into a new Household: back to Personal, then the introduction.
    func startHousehold() async {
        await select(nil)
        if isAvailable { showManagement = true }
    }
}
