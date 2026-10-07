import Foundation
import XCTest
@testable import FinancialModels

final class ConnectedAccountOrderTests: XCTestCase {
    private struct Item: Identifiable, Equatable { let id: UUID }
    private let a = Item(id: UUID()), b = Item(id: UUID()), c = Item(id: UUID()), d = Item(id: UUID())

    func testSavedOrderWinsAndUnknownAccountsGoLastInServerOrder() {
        let ordered = ConnectedAccountOrder.applying([c.id, a.id], to: [a, b, c, d])
        XCTAssertEqual(ordered, [c, a, b, d])
    }

    func testNoSavedOrderKeepsTheServerOrder() {
        XCTAssertEqual(ConnectedAccountOrder.applying([], to: [a, b, c]), [a, b, c])
    }

    func testAnArchivedOrRemovedIdInTheSavedOrderIsIgnored() {
        XCTAssertEqual(ConnectedAccountOrder.applying([d.id, c.id, a.id], to: [a, b, c]), [c, a, b])
    }

    func testMovingBeforeADestinationAndToTheEnd() {
        let ids = [a.id, b.id, c.id]
        XCTAssertEqual(ConnectedAccountOrder.moving(c.id, before: a.id, in: ids), [c.id, a.id, b.id])
        XCTAssertEqual(ConnectedAccountOrder.moving(a.id, before: nil, in: ids), [b.id, c.id, a.id])
        XCTAssertEqual(ConnectedAccountOrder.moving(a.id, before: a.id, in: ids), ids)
        XCTAssertEqual(ConnectedAccountOrder.moving(d.id, before: a.id, in: ids), ids)
    }

    func testOrderIsStoredPerPersonOnTheDevice() throws {
        let defaults = try XCTUnwrap(UserDefaults(suiteName: "account-order-" + UUID().uuidString))
        ConnectedAccountOrder.save([b.id, a.id], for: "person-1", defaults: defaults)
        XCTAssertEqual(ConnectedAccountOrder.load(for: "person-1", defaults: defaults), [b.id, a.id])
        XCTAssertEqual(ConnectedAccountOrder.load(for: "person-2", defaults: defaults), [])
    }
}
