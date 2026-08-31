import SwiftUI
import CoreGraphics
import Combine
import ScreenCaptureKit   // BUG FIX: was missing — SCShareableContent below would not compile without this.

/// BUG FIX SUMMARY (see PR description / integration notes for detail):
///  1. Added `import ScreenCaptureKit` — the original file referenced
///     `SCShareableContent` with no import for the framework it comes
///     from, which fails to compile.
///  2. Networking now delegates to `TradeBridge`, which already had the
///     correct multipart/form-data upload matching the server contract
///     used by the Windows client (`api_client.py`) — the original
///     `sendToAPI()` here sent a raw JSON body instead, which the
///     `/aegis/analyze` endpoint does not accept.
///  3. The MT5 signal file now uses `TradeBridge`'s path
///     (`~/Library/Application Support/MetaQuotes/Terminal/Common/Files/aegis_signal.txt`),
///     which matches where MetaTrader 5 for Mac (Wine-based) actually
///     looks for Common\Files. The original wrote to `~/Documents`,
///     which the EA would never read from.
///  4. Screen capture uses `SCScreenshotManager` (ScreenCaptureKit,
///     macOS 14+) exclusively. An earlier version of this fix kept a
///     fallback to the deprecated `CGWindowListCreateImage` for macOS
///     13 — that API has since been fully removed (not just
///     deprecated) from the SDK, so any reference to it is now a hard
///     compile error regardless of version-availability guards. The
///     fallback is removed entirely; this app now requires macOS 14+
///     (Info.plist's LSMinimumSystemVersion is updated to match).
class CaptureService: NSObject, ObservableObject {
    @Published var isRunning = false
    @Published var screenshotCount = 0
    @Published var lastSignal = "HOLD"
    @Published var errorMessage: String?

    private var timer: Timer?
    private var region: CGRect = .zero
    private var config: Config?
    private var isCapturing = false
    private let bridge = TradeBridge()

    override init() {
        super.init()
    }

    func startCapture(config: Config, region: CGRect) {
        self.config = config
        self.region = region
        self.isRunning = true
        self.screenshotCount = 0
        self.errorMessage = nil

        checkScreenRecordingPermission()

        timer = Timer.scheduledTimer(withTimeInterval: config.intervalSec, repeats: true) { [weak self] _ in
            self?.captureScreenshot()
        }
    }

    func stopCapture() {
        isRunning = false
        timer?.invalidate()
        timer = nil
    }

    private func checkScreenRecordingPermission() {
        // This will trigger the system permission dialog on first run.
        Task {
            do {
                let content = try await SCShareableContent.current
                print("Screen recording permission granted: \(content.displays.count) displays")
            } catch {
                print("Screen recording permission error: \(error)")
                await MainActor.run {
                    self.errorMessage = "Please grant screen recording permission in System Settings > Privacy & Security > Screen Recording"
                }
            }
        }
    }

    private func captureScreenshot() {
        guard isRunning, !isCapturing else { return }
        isCapturing = true

        Task {
            let image = await self.captureScreenRegion()
            await MainActor.run {
                self.isCapturing = false
            }
            if let image {
                await self.processImage(image)
            }
        }
    }

    /// Captures the configured screen region using ScreenCaptureKit.
    /// Requires macOS 14+ (see Info.plist LSMinimumSystemVersion).
    private func captureScreenRegion() async -> NSImage? {
        do {
            guard let display = try await SCShareableContent.current.displays.first else {
                print("No displays available to capture")
                return nil
            }
            let filter = SCContentFilter(display: display, excludingApplications: [], exceptingWindows: [])
            let streamConfig = SCStreamConfiguration()
            streamConfig.sourceRect = region
            streamConfig.width = max(1, Int(region.width))
            streamConfig.height = max(1, Int(region.height))
            streamConfig.showsCursor = false
            let cgImage = try await SCScreenshotManager.captureImage(contentFilter: filter, configuration: streamConfig)
            return NSImage(cgImage: cgImage, size: region.size)
        } catch {
            print("ScreenCaptureKit capture failed: \(error)")
            await MainActor.run {
                self.errorMessage = "Screen capture failed: \(error.localizedDescription)"
            }
            return nil
        }
    }

    private func processImage(_ image: NSImage) async {
        guard let tiffData = image.tiffRepresentation,
              let bitmapImage = NSBitmapImageRep(data: tiffData) else {
            print("Failed to convert image")
            return
        }
        guard let pngData = bitmapImage.representation(using: .png, properties: [:]) else {
            print("Failed to convert to PNG")
            return
        }
        guard let config else { return }

        await bridge.sendFrame(imageData: pngData, config: config)

        await MainActor.run {
            self.screenshotCount += 1
            self.lastSignal = self.bridge.lastSignal
        }
    }
}
