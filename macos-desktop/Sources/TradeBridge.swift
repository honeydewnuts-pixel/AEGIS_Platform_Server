import Foundation

class TradeBridge: ObservableObject {
    @Published var lastSignal: String = "Waiting…"
    @Published var lastHTTP: Int = 0
    @Published var frames: Int = 0
    @Published var uploadsOK: Int = 0

    func sendFrame(imageData: Data, config: Config) async {
        guard let base = URL(string: config.serverURL.trimmingCharacters(in: .whitespacesAndNewlines)),
              !config.apiKey.isEmpty else {
            await MainActor.run { self.lastSignal = "Missing server URL or API key" }
            return
        }
        let url = base.appendingPathComponent("aegis/analyze")
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue(config.apiKey, forHTTPHeaderField: "X-API-Key")
        req.setValue(config.accountID, forHTTPHeaderField: "X-Account-Id")
        req.setValue("macos", forHTTPHeaderField: "X-Platform")
        req.timeoutInterval = 60

        let boundary = "AegisBoundary-\(UUID().uuidString)"
        req.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")

        var body = Data()
        func append(_ s: String) { body.append(Data(s.utf8)) }
        append("--\(boundary)\r\n")
        append("Content-Disposition: form-data; name=\"account_id\"\r\n\r\n")
        append("\(config.accountID)\r\n")
        append("--\(boundary)\r\n")
        append("Content-Disposition: form-data; name=\"captured_at_ms\"\r\n\r\n")
        append("\(Int(Date().timeIntervalSince1970 * 1000))\r\n")
        append("--\(boundary)\r\n")
        append("Content-Disposition: form-data; name=\"image\"; filename=\"chart.png\"\r\n")
        append("Content-Type: image/png\r\n\r\n")
        body.append(imageData)
        append("\r\n--\(boundary)--\r\n")
        req.httpBody = body

        do {
            let (data, resp) = try await URLSession.shared.data(for: req)
            let code = (resp as? HTTPURLResponse)?.statusCode ?? 0
            var signal = "HOLD"
            if let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
                signal = (obj["signal"] as? String) ?? (obj["action"] as? String) ?? "HOLD"
            }
            await MainActor.run {
                self.frames += 1
                self.lastHTTP = code
                if code == 200 { self.uploadsOK += 1 }
                self.lastSignal = "\(signal) · HTTP \(code)"
            }
            // Write signal for MT5 EA (shared container best-effort)
            if ["BUY", "SELL", "HOLD"].contains(signal.uppercased()) {
                let path = FileManager.default.homeDirectoryForCurrentUser
                    .appendingPathComponent("Library/Application Support/MetaQuotes/Terminal/Common/Files/aegis_signal.txt")
                try? FileManager.default.createDirectory(at: path.deletingLastPathComponent(), withIntermediateDirectories: true)
                try? signal.uppercased().data(using: .utf8)?.write(to: path)
            }
        } catch {
            await MainActor.run { self.lastSignal = "Error: \(error.localizedDescription)" }
        }
    }
}
