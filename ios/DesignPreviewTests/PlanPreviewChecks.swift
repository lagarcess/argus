import Foundation

@main struct PlanPreviewChecks {
    static func main() throws {
        var count = 0
        func check(_ condition: @autoclosure () -> Bool, _ message: String) {
            precondition(condition(), message); count += 1
        }
        let suite = "cuadrao.plan.tests.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suite)!
        defer { defaults.removePersistentDomain(forName: suite) }
        let store = CuadraoPlanPreview(spanish: true, defaults: defaults, reset: true)
        check(store.plans.count == 4, "All plan kinds and shared context have fixtures")
        for household in [false, true] {
            let forecast = CanvasForecast(household: household)
            for pace in [0.0, forecast.daily, 3000] {
                let points = forecast.projection(daily: pace)
                check(points.first?.balance == forecast.current, "Forecast begins at recorded balance")
                check(points.count == CanvasForecast.lastDay - CanvasForecast.today + 1, "Forecast covers remaining days once")
                let expected = forecast.current - pace * Double(CanvasForecast.lastDay - CanvasForecast.today) + forecast.events.reduce(0) { $0 + $1.amount }
                check(abs(forecast.ending(daily: pace) - expected) < 0.001, "Cash conservation includes each scheduled item exactly once")
                check(points.map(\.balance).contains(forecast.lowest(daily: pace).balance), "Lowest point comes from the same projection")
            }
        }
        var goal = store.plans.first { $0.kind == .goal }!
        let recorded = goal.recorded
        check(goal.months(at: goal.remaining / 3) == 3, "Three-month goal projection")
        check(goal.months(at: 0) == nil, "Zero payment has no invented finish date")
        goal.monthly *= 2; store.save(goal)
        check(store.plan(goal.id)?.recorded == recorded, "Applying a plan never fabricates recorded savings")
        let debt = store.plans.first { $0.kind == .debt }!
        check(debt.months(at: debt.remaining * debt.annualRate / 1200) == nil, "Interest-only payment never pays off debt")
        check(debt.months(at: debt.remaining * (1 + debt.annualRate / 1200)) == 1, "A complete first payment finishes debt")
        for months in [3, 6, 12] {
            let payment = debt.monthlyAmount(finishingIn: months)
            check(debt.months(at: payment) == months, "A target month and its payment agree")
            check(debt.projectedValue(at: months, monthly: payment) == 0, "The chart reaches zero at the same payoff month")
        }
        var invalid = goal; invalid.target = .nan; store.save(invalid)
        check(store.plan(goal.id)?.target == goal.target, "Reject non-finite input")
        invalid = goal; invalid.name = "  "; store.save(invalid)
        check(store.plan(goal.id)?.name == goal.name, "Reject empty names")
        store.applyDaily(700, scope: "personal")
        store.archive(goal.id, true)
        let loaded = CuadraoPlanPreview(spanish: true, defaults: defaults)
        check(loaded.plan(goal.id)?.archived == true, "Archive survives reopening")
        check(loaded.daily(for: "personal") == 700, "Saved pace survives reopening")
        check(loaded.daily(for: "household") == CanvasForecast(household: true).daily, "Household pace is independent")
        loaded.archive(goal.id, false)
        check(loaded.plan(goal.id)?.recorded == recorded, "Restore preserves progress")
        loaded.resetExamples(spanish: true, empty: true)
        var new = CanvasPlan(name: "Nuevo plan", target: 1200, monthly: 100); new.recorded = 300
        loaded.save(new); loaded.enableForecastExample()
        check(loaded.plans == [new], "Exploring forecast from cold start preserves newly created plans")
        check(loaded.hasForecast, "Cold start can explore forecast independently")
        for currency in PlanCurrency.supported {
            var fixed = CanvasPlan(name: "Fixed currency", currency: currency, target: 1200, monthly: 100)
            store.save(fixed)
            fixed.currency = PlanCurrency.supported.first { $0 != currency }!
            store.save(fixed)
            check(store.plan(fixed.id)?.currency == currency, "Currency cannot change after creating a personal plan")
            fixed.currency = currency; fixed.name = "Renamed"; store.save(fixed)
            check(store.plan(fixed.id)?.name == fixed.name, "Other plan details remain editable")
            let restored = CuadraoPlanPreview(spanish: false, defaults: defaults)
            check(restored.plan(fixed.id)?.currency == currency, "The chosen currency survives reopening")
            check(restored.plan(fixed.id)?.target == fixed.target, "No conversion changes the amount")
        }
        let empty = CanvasPlan(name: "")
        check(empty.target == 0 && empty.monthly == 0, "Creation has no suggested financial amounts")
        check(CanvasMoney.maximumValue == 9_999_999.99 && CanvasMoney.maximumCents == 999_999_999, "Money boundaries include cents")
        print("Passed \(count) Plan preview checks")
    }
}
