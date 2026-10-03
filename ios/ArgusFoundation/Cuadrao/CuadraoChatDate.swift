import SwiftUI

struct CuadraoChatDate: View {
    let date: Date
    let spanish: Bool
    var body: some View {
        TimelineView(.periodic(from: .now, by: 60)) { context in
            Text(CanvasChatRecency.label(date, spanish: spanish, now: context.date))
                .font(.caption).foregroundStyle(.secondary).fixedSize()
        }
    }
}
