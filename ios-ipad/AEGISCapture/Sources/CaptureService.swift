import Foundation
import ReplayKit

/// Frame grab via ReplayKit — user must start recording and keep MT5 visible.
final class CaptureService: NSObject {
    static let shared = CaptureService()
    private let recorder = RPScreenRecorder.shared()

    func start(onFrame: @escaping (Data) -> Void) {
        guard recorder.isAvailable else { return }
        recorder.isMicrophoneEnabled = false
        recorder.startCapture { sample, bufferType, error in
            if let error = error {
                print("AEGIS capture error: \(error)")
                return
            }
            // Production: convert video sample buffer → UIImage → PNG Data, throttle to 1/3s
            _ = (sample, bufferType, onFrame)
        } completionHandler: { error in
            if let error = error { print("startCapture: \(error)") }
        }
    }

    func stop() {
        recorder.stopCapture { _ in }
    }
}
