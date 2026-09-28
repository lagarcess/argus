import SwiftUI

@main
struct ProbeApp: App {
    @State private var model = ProbeModel()

    var body: some Scene {
        WindowGroup {
            ProbeView(model: model)
                .onOpenURL { url in Task { await model.handleCallback(url) } }
                .task { await model.autorun() }
        }
    }
}
