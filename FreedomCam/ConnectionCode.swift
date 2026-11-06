import SwiftUI
import VisionKit

/// The QR code shown by the Home Assistant integration: freedomcam://connect?c=<base64url JSON>
/// with the provider, the bucket and read-only keys (custom_components/freedomcam/connection.py).
enum ConnectionCode {
    static func parse(_ text: String) -> StorageConfig? {
        guard let comps = URLComponents(string: text.trimmingCharacters(in: .whitespacesAndNewlines)),
              comps.scheme == "freedomcam", comps.host == "connect",
              let code = comps.queryItems?.first(where: { $0.name == "c" })?.value else { return nil }
        var b64 = code.replacingOccurrences(of: "-", with: "+").replacingOccurrences(of: "_", with: "/")
        b64 += String(repeating: "=", count: (4 - b64.count % 4) % 4)
        guard let data = Data(base64Encoded: b64),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let providerText = json["provider"] as? String, let provider = StorageProvider(rawValue: providerText),
              let bucket = json["bucket"] as? String, let key = json["access_key_id"] as? String,
              let secret = json["secret_access_key"] as? String else { return nil }
        var config = StorageConfig(provider: provider, accountId: json["account_id"] as? String ?? "",
                                   jurisdiction: json["jurisdiction"] as? String ?? "default",
                                   region: json["region"] as? String ?? "", endpoint: json["endpoint"] as? String ?? "",
                                   virtualHost: json["virtual_host"] as? Bool ?? false, bucket: bucket,
                                   accessKeyId: key, secretAccessKey: secret)
        config.normalize()
        return config.isComplete ? config : nil
    }
}

/// Camera view that reads the QR code. Closes by itself when it finds a valid one.
struct QRScannerView: View {
    let found: (StorageConfig) -> Void
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            Group {
                if DataScannerViewController.isSupported && DataScannerViewController.isAvailable {
                    Scanner { texto in
                        guard let config = ConnectionCode.parse(texto) else { return false }
                        found(config)
                        dismiss()
                        return true
                    }
                    .ignoresSafeArea(edges: .bottom)
                    .overlay(alignment: .bottom) {
                        Text("Point at the QR code of freedomCam in Home Assistant")
                            .font(.subheadline.weight(.semibold))
                            .padding(.horizontal, 16).padding(.vertical, 10)
                            .background(.ultraThinMaterial, in: Capsule())
                            .padding(.bottom, 40)
                    }
                } else {
                    EmptyState(emoji: "📷", title: String(localized: "No camera here"),
                               text: String(localized: "Open the QR code with the iPhone Camera app: it will offer to open freedomCam."))
                }
            }
            .navigationTitle("Scan code")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } } }
        }
    }
}

private struct Scanner: UIViewControllerRepresentable {
    let onCode: (String) -> Bool

    func makeUIViewController(context: Context) -> DataScannerViewController {
        let vc = DataScannerViewController(recognizedDataTypes: [.barcode(symbologies: [.qr])],
                                           qualityLevel: .balanced, isHighlightingEnabled: true)
        vc.delegate = context.coordinator
        try? vc.startScanning()
        return vc
    }

    func updateUIViewController(_ vc: DataScannerViewController, context: Context) {}

    func makeCoordinator() -> Coordinator { Coordinator(onCode: onCode) }

    final class Coordinator: NSObject, DataScannerViewControllerDelegate {
        let onCode: (String) -> Bool
        private var done = false

        init(onCode: @escaping (String) -> Bool) { self.onCode = onCode }

        func dataScanner(_ scanner: DataScannerViewController, didAdd items: [RecognizedItem],
                         allItems: [RecognizedItem]) {
            for case let .barcode(code) in items {
                guard !done, let texto = code.payloadStringValue else { continue }
                if onCode(texto) {
                    done = true
                    scanner.stopScanning()
                }
            }
        }
    }
}
