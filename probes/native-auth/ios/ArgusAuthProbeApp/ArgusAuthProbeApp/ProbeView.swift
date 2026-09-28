import SwiftUI

struct ProbeView: View {
    @Bindable var model: ProbeModel

    var body: some View {
        NavigationStack {
            List {
                Section("Actions") {
                    Button("Security check (test sitekey, passes)") { model.openTurnstile(sitekey: "1x00000000000000000000AA") }
                    Button("Security check (test sitekey, fails)") { model.openTurnstile(sitekey: "2x00000000000000000000AB") }
                    Button("Security check (test sitekey, interactive)") { model.openTurnstile(sitekey: "3x00000000000000000000FF") }
                }
                Section("Log") {
                    ForEach(model.entries.reversed()) { entry in
                        VStack(alignment: .leading, spacing: 2) {
                            Text(entry.step).font(.headline)
                            Text(entry.observed.sorted { $0.key < $1.key }.map { "\($0.key)=\($0.value)" }.joined(separator: " "))
                                .font(.caption.monospaced())
                                .foregroundStyle(.secondary)
                        }
                        .accessibilityIdentifier("log-\(entry.step)")
                    }
                }
            }
            .navigationTitle("Native auth probe")
        }
        .sheet(isPresented: Binding(get: { model.turnstilePage != nil }, set: { if !$0 { model.cancelTurnstile() } })) {
            if let page = model.turnstilePage {
                NavigationStack {
                    TurnstileWebView(page: page, onInteractive: { model.log("turnstile.interactive", [:]) }) { event, token, detail in
                        Task { await model.turnstileEvent(event, token: token, detail: detail) }
                    }
                    .navigationTitle("Security check")
                    .navigationBarTitleDisplayMode(.inline)
                    .toolbar {
                        ToolbarItem(placement: .cancellationAction) {
                            Button("Cancel") { model.cancelTurnstile() }
                        }
                    }
                }
                .presentationDetents([.medium])
            }
        }
    }
}
