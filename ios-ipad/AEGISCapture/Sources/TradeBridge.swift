import Foundation
import UIKit

/// Opens MetaTrader 5 iOS via URL scheme for user-confirmed trade.
enum TradeBridge {
    static func openTrade(symbol: String, side: String, lots: Double) {
        // Best-effort scheme; broker/MT5 builds may differ.
        let urlStr = "mt5://trade?symbol=\(symbol)&type=\(side)&lots=\(lots)"
        guard let url = URL(string: urlStr) else { return }
        DispatchQueue.main.async {
            UIApplication.shared.open(url, options: [:], completionHandler: nil)
        }
    }
}
