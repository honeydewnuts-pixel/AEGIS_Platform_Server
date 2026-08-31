import SwiftUI

@main
struct AegisCaptureApp: App {
    @StateObject var config = Config()
    
    var body: some Scene {
        Window("AEGIS Capture", id: "main") {
            ContentView()
                .environmentObject(config)
        }
        .windowResizability(.contentSize)
    }
}
