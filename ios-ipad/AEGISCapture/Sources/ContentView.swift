import SwiftUI

/// AEGIS iOS shell — login + signal dashboard + capture CTA.
struct ContentView: View {
    @State private var serverURL = "https://aegis-api-0z1p.onrender.com"
    @State private var accountId = ""
    @State private var apiKey = ""
    @State private var lastSignal = "—"
    @State private var status = "Idle"

    var body: some View {
        NavigationView {
            Form {
                Section("Cloud") {
                    TextField("Server URL", text: $serverURL)
                    TextField("Account ID", text: $accountId)
                    SecureField("API Key", text: $apiKey)
                }
                Section("Status") {
                    Text("Signal: \(lastSignal)")
                    Text(status).font(.caption).foregroundColor(.secondary)
                }
                Section("Actions") {
                    Button("Start Capture (ReplayKit)") {
                        status = "Use RPScreenRecorder in CaptureService — MT5 must be visible"
                    }
                    Button("Open MT5 trade bridge") {
                        TradeBridge.openTrade(symbol: "EURUSD", side: "buy", lots: 0.01)
                    }
                }
                Section("Note") {
                    Text("iOS cannot capture another app in the background. Bring MT5 to foreground while capturing, or use Windows Capture on a PC/VPS.")
                        .font(.caption2)
                }
            }
            .navigationTitle("AEGIS")
        }
    }
}
