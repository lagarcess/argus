import SwiftUI

@main enum ConnectedSwipeChecks {
    static func main() {
        var checks = 0
        func check(_ condition: Bool, _ title: String) {
            precondition(condition, title)
            checks += 1
        }
        let income = ConnectedSwipeRegistration(leading: ["home.activity.swipe.edit"], trailing: [])
        check(income.swipes(.leading), "An edge with actions swipes")
        check(!income.swipes(.trailing), "An edge without actions never slides the row open")
        let pending = ConnectedSwipeRegistration(leading: [], trailing: [])
        check(!pending.swipes(.leading) && !pending.swipes(.trailing), "A row without actions never slides open")
        check(pending != income, "Actions returning after a pending write are a new registration")
        let expense = ConnectedSwipeRegistration(leading: ["home.activity.swipe.edit"], trailing: ["home.activity.swipe.category"])
        check(expense != income, "A changed action set is a new registration")
        check(ConnectedSwipeRegistration(leading: ["home.activity.swipe.edit"], trailing: []) == income,
            "An unchanged action set keeps its registration, so an open row is not reset on redraw")
        check(ConnectedSwipeRegistration(leading: [], trailing: ["home.activity.swipe.edit"]) != income,
            "The same action on the other edge is a different registration")
        print("ConnectedSwipeChecks: \(checks) passed")
    }
}
