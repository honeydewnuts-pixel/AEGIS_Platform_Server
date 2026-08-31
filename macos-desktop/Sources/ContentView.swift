import SwiftUI

struct ContentView: View {
    @StateObject private var config = Config()
    @StateObject private var capture = CaptureService()
    @State private var region: CGRect = CGRect(x: 200, y: 150, width: 640, height: 400)
    @State private var isSelectingRegion = false
    @State private var startX: CGFloat = 0
    @State private var startY: CGFloat = 0
    @State private var endX: CGFloat = 0
    @State private var endY: CGFloat = 0
    @State private var showColorGuide = false
    
    var body: some View {
        VStack(spacing: 20) {
            // Title
            Text("AegisCapture")
                .font(.largeTitle)
                .fontWeight(.bold)
            
            // Status
            HStack {
                Circle()
                    .fill(capture.isRunning ? Color.green : Color.red)
                    .frame(width: 12, height: 12)
                Text(capture.isRunning ? "Running" : "Stopped")
                    .font(.headline)
            }
            
            Divider()
            
            // Configuration
            GroupBox(label: Text("Configuration")) {
                VStack(alignment: .leading, spacing: 10) {
                    HStack {
                        Text("Server URL:")
                            .frame(width: 100, alignment: .trailing)
                        TextField("Server URL", text: $config.serverURL)
                            .textFieldStyle(RoundedBorderTextFieldStyle())
                    }
                    
                    HStack {
                        Text("Account ID:")
                            .frame(width: 100, alignment: .trailing)
                        TextField("Account ID", text: $config.accountID)
                            .textFieldStyle(RoundedBorderTextFieldStyle())
                    }
                    
                    HStack {
                        Text("API Key:")
                            .frame(width: 100, alignment: .trailing)
                        SecureField("API Key", text: $config.apiKey)
                            .textFieldStyle(RoundedBorderTextFieldStyle())
                    }
                    
                    HStack {
                        Text("Interval (sec):")
                            .frame(width: 100, alignment: .trailing)
                        TextField("Interval", value: $config.intervalSec, format: .number)
                            .textFieldStyle(RoundedBorderTextFieldStyle())
                            .frame(width: 80)
                        Stepper("", value: $config.intervalSec, in: 1...10, step: 0.5)
                            .frame(width: 50)
                    }
                }
            }
            
            // Region Selection
            GroupBox(label: Text("Capture Region")) {
                VStack(spacing: 10) {
                    HStack {
                        Text("X: \(Int(config.regionX))")
                            .frame(width: 80, alignment: .leading)
                        Slider(value: $config.regionX, in: 0...500, step: 10)
                        Text("Y: \(Int(config.regionY))")
                            .frame(width: 80, alignment: .leading)
                        Slider(value: $config.regionY, in: 0...500, step: 10)
                    }
                    
                    HStack {
                        Text("W: \(Int(config.regionW))")
                            .frame(width: 80, alignment: .leading)
                        Slider(value: $config.regionW, in: 100...1200, step: 10)
                        Text("H: \(Int(config.regionH))")
                            .frame(width: 80, alignment: .leading)
                        Slider(value: $config.regionH, in: 100...800, step: 10)
                    }
                    
                    Button("Select Region with Mouse") {
                        isSelectingRegion = true
                    }
                    .disabled(capture.isRunning)
                }
            }
            
            // Signal Display
            GroupBox(label: Text("Latest Signal")) {
                HStack {
                    Text(capture.lastSignal)
                        .font(.largeTitle)
                        .fontWeight(.bold)
                        .foregroundColor(signalColor(capture.lastSignal))
                    Spacer()
                    Text("Screenshots: \(capture.screenshotCount)")
                        .font(.caption)
                }
            }
            
            // Action Buttons
            HStack(spacing: 20) {
                Button(capture.isRunning ? "Stop" : "Start") {
                    if capture.isRunning {
                        capture.stopCapture()
                    } else {
                        let regionRect = CGRect(
                            x: config.regionX,
                            y: config.regionY,
                            width: config.regionW,
                            height: config.regionH
                        )
                        capture.startCapture(config: config, region: regionRect)
                    }
                }
                .buttonStyle(.borderedProminent)
                .tint(capture.isRunning ? .red : .green)
                .disabled(config.accountID.isEmpty || config.apiKey.isEmpty)
                
                Button("Color Guide") {
                    showColorGuide = true
                }
                .buttonStyle(.bordered)
                
                Button("Reset") {
                    config.resetToDefaults()
                }
                .buttonStyle(.bordered)
            }
        }
        .padding(30)
        .frame(width: 600, height: 650)
        .sheet(isPresented: $showColorGuide) {
            ColorGuideView()
        }
        .overlay {
            if isSelectingRegion {
                RegionSelectionOverlay(
                    isSelecting: $isSelectingRegion,
                    region: $region,
                    config: config
                )
            }
        }
    }
    
    private func signalColor(_ signal: String) -> Color {
        switch signal {
        case "BUY":
            return .green
        case "SELL":
            return .red
        default:
            return .gray
        }
    }
}

// MARK: - Color Guide View
struct ColorGuideView: View {
    @Environment(\.dismiss) private var dismiss
    
    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            Text("MT5 Color Match Guide")
                .font(.title)
                .fontWeight(.bold)
                .padding(.bottom, 10)
            
            ScrollView {
                VStack(alignment: .leading, spacing: 10) {
                    Text("For AEGIS to work correctly, set these indicator colors in MT5:")
                        .font(.headline)
                    
                    GroupBox(label: Text("Main Window")) {
                        VStack(alignment: .leading, spacing: 5) {
                            HStack {
                                Rectangle()
                                    .fill(Color.white)
                                    .frame(width: 30, height: 20)
                                Text("BB34 Upper = White (#FFFFFF)")
                            }
                            HStack {
                                Rectangle()
                                    .fill(Color.cyan)
                                    .frame(width: 30, height: 20)
                                Text("BB17 Upper = Cyan (#00FFFF)")
                            }
                            HStack {
                                Rectangle()
                                    .fill(Color.white)
                                    .frame(width: 30, height: 20)
                                Text("BB34 Middle = White (#FFFFFF)")
                            }
                            HStack {
                                Rectangle()
                                    .fill(Color.cyan)
                                    .frame(width: 30, height: 20)
                                Text("BB17 Middle = Cyan (#00FFFF)")
                            }
                            HStack {
                                Rectangle()
                                    .fill(Color.white)
                                    .frame(width: 30, height: 20)
                                Text("BB34 Lower = White (#FFFFFF)")
                            }
                            HStack {
                                Rectangle()
                                    .fill(Color.cyan)
                                    .frame(width: 30, height: 20)
                                Text("BB17 Lower = Cyan (#00FFFF)")
                            }
                        }
                    }
                    
                    GroupBox(label: Text("RSI Window")) {
                        VStack(alignment: .leading, spacing: 5) {
                            HStack {
                                Rectangle()
                                    .fill(Color.cyan)
                                    .frame(width: 30, height: 20)
                                Text("RSI9 = Cyan (#00FFFF)")
                            }
                            HStack {
                                Rectangle()
                                    .fill(Color(red: 1.0, green: 0.0, blue: 1.0)) // Magenta
                                    .frame(width: 30, height: 20)
                                Text("MA7 = Magenta (#FF00FF)")
                            }
                            HStack {
                                Rectangle()
                                    .fill(Color.white)
                                    .frame(width: 30, height: 20)
                                Text("BB34 Upper = White (#FFFFFF)")
                            }
                            HStack {
                                Rectangle()
                                    .fill(Color.white)
                                    .frame(width: 30, height: 20)
                                Text("BB34 Middle = White (#FFFFFF)")
                            }
                            HStack {
                                Rectangle()
                                    .fill(Color.white)
                                    .frame(width: 30, height: 20)
                                Text("BB34 Lower = White (#FFFFFF)")
                            }
                        }
                    }
                    
                    Text("Make sure these colors match your MT5 chart exactly!")
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .padding(.top, 10)
                }
            }
            
            Button("Close") {
                dismiss()
            }
            .buttonStyle(.borderedProminent)
            .frame(maxWidth: .infinity, alignment: .center)
        }
        .padding(30)
        .frame(width: 500, height: 600)
    }
}

// MARK: - Region Selection Overlay
struct RegionSelectionOverlay: View {
    @Binding var isSelecting: Bool
    @Binding var region: CGRect
    var config: Config
    
    var body: some View {
        ZStack {
            Color.black.opacity(0.5)
                .edgesIgnoringSafeArea(.all)
                .onTapGesture {
                    isSelecting = false
                }
            
            VStack {
                Text("Click and drag to select region")
                    .font(.headline)
                    .foregroundColor(.white)
                    .padding()
                    .background(Color.black.opacity(0.7))
                    .cornerRadius(10)
                
                Rectangle()
                    .stroke(Color.red, lineWidth: 2)
                    .frame(width: region.width, height: region.height)
                    .position(x: region.midX, y: region.midY)
                    .gesture(
                        DragGesture()
                            .onChanged { value in
                                region = CGRect(
                                    x: value.startLocation.x,
                                    y: value.startLocation.y,
                                    width: value.translation.width,
                                    height: value.translation.height
                                )
                            }
                            .onEnded { _ in
                                // Update config
                                config.regionX = region.origin.x
                                config.regionY = region.origin.y
                                config.regionW = region.size.width
                                config.regionH = region.size.height
                                isSelecting = false
                            }
                    )
            }
        }
    }
}

// MARK: - Preview
struct ContentView_Previews: PreviewProvider {
    static var previews: some View {
        ContentView()
    }
}
