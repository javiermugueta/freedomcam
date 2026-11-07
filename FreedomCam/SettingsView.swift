import SwiftUI

struct SettingsView: View {
    @Environment(GalleryModel.self) private var model
    @Environment(\.dismiss) private var dismiss
    @State private var config = StorageConfig()
    @State private var testing = false
    @State private var result: Result<[String], Error>?
    @State private var cacheBytes = 0
    @State private var showScanner = false

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    Button {
                        showScanner = true
                    } label: {
                        Label("Scan the code from Home Assistant", systemImage: "qrcode.viewfinder")
                    }
                } footer: {
                    Text("In Home Assistant: freedomCam → options → read-only keys for the app. The QR code appears in the integration.")
                }

                Section {
                    Picker("Provider", selection: $config.provider) {
                        ForEach(StorageProvider.allCases) { Text($0.title).tag($0) }
                    }
                    providerFields
                    TextField("Bucket name", text: $config.bucket)
                } header: {
                    Text("🪣 Where are the photos?")
                } footer: {
                    providerHelp
                }

                Section {
                    TextField("Access Key ID", text: $config.accessKeyId)
                    SecureField("Secret Access Key", text: $config.secretAccessKey)
                } header: {
                    Text("🔑 Access keys")
                } footer: {
                    Text("Use **read-only** keys limited to this bucket. They are kept in the iPhone Keychain.")
                }

                Section {
                    Button {
                        Task { await test() }
                    } label: {
                        HStack {
                            Text("Test connection")
                            Spacer()
                            if testing { ProgressView() }
                        }
                    }
                    .disabled(!config.isComplete || testing)

                    if let result {
                        switch result {
                        case let .success(cameras):
                            Label(cameras.isEmpty ? String(localized: "Connected, but the bucket is empty")
                                  : String(localized: "It works! Cameras: \(cameras.joined(separator: ", "))"),
                                  systemImage: "checkmark.seal.fill")
                                .foregroundStyle(.green)
                        case let .failure(error):
                            Label(error.localizedDescription, systemImage: "exclamationmark.triangle.fill")
                                .foregroundStyle(.red)
                        }
                    }
                }

                Section {
                    LabeledContent("Photos stored on this phone",
                                   value: ByteCountFormatter.string(fromByteCount: Int64(cacheBytes), countStyle: .file))
                    Button("Empty cache", role: .destructive) {
                        Task {
                            await ImageCache.shared.clearDisk()
                            cacheBytes = await ImageCache.shared.diskBytes()
                        }
                    }
                } header: {
                    Text("🧹 Space")
                }

                Section {
                    Link(destination: Self.docURL("guide")) {
                        Label("User guide", systemImage: "book")
                    }
                    Link(destination: Self.docURL("privacy")) {
                        Label("Privacy policy", systemImage: "hand.raised")
                    }
                    LabeledContent("Version", value: Self.version)
                } header: {
                    Text("ℹ️ Help")
                }

                if model.config.isComplete {
                    Section {
                        Button("Forget this connection", role: .destructive) {
                            SettingsStore.clear()
                            model.updateConfig(StorageConfig())
                            config = StorageConfig()
                            result = nil
                        }
                    }
                }
            }
            .autocorrectionDisabled()
            .textInputAutocapitalization(.never)
            .navigationTitle("Settings ⚙️")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        config.normalize()
                        model.updateConfig(config)
                        dismiss()
                    }
                    .bold()
                    .disabled(!config.isComplete)
                }
            }
            .onChange(of: config) { _, _ in result = nil }
            .sheet(isPresented: $showScanner) {
                QRScannerView { scanned in
                    config = scanned
                    Task { await test() }
                }
            }
        }
        .onAppear { config = model.config.demo ? StorageConfig() : model.config }
        .task { cacheBytes = await ImageCache.shared.diskBytes() }
    }

    @ViewBuilder private var providerFields: some View {
        switch config.provider {
        case .cloudflareR2:
            TextField("Account ID", text: $config.accountId)
                .onSubmit { config.normalize() }
            Picker("Jurisdiction", selection: $config.jurisdiction) {
                Text("Default").tag("default")
                Text("European Union").tag("eu")
                Text("FedRAMP").tag("fedramp")
            }
        case .other:
            TextField("https://s3.example.com", text: $config.endpoint)
                .keyboardType(.URL)
                .onSubmit { config.normalize() }
            TextField("Region", text: $config.region, prompt: Text(config.provider.defaultRegion))
            Toggle("Bucket in the host name", isOn: $config.virtualHost)
        default:
            TextField("Region", text: $config.region, prompt: Text(config.provider.defaultRegion))
        }
    }

    @ViewBuilder private var providerHelp: some View {
        VStack(alignment: .leading, spacing: 4) {
            switch config.provider {
            case .cloudflareR2:
                Text("Cloudflare → R2: the Account ID is in the right column. You can also paste the bucket's S3 API URL here.")
            case .awsS3:
                Text("The region of the bucket, e.g. eu-south-2 (Spain) or us-east-1.")
            case .backblazeB2:
                Text("The bucket's S3 endpoint is s3.<region>.backblazeb2.com, e.g. eu-central-003.")
            case .wasabi:
                Text("The region of the bucket, e.g. eu-central-1.")
            case .other:
                Text("MinIO, a NAS with S3, Scaleway… The endpoint of the S3 API, without the bucket. Use us-east-1 if your service has no regions.")
            }
            if let url = config.provider.helpURL {
                Link("How do I get the keys?", destination: url)
            }
        }
    }

    private func test() async {
        testing = true
        defer { testing = false }
        var c = config
        c.normalize()
        config = c
        do {
            result = .success(try await GalleryModel.test(c))
        } catch {
            result = .failure(error)
        }
    }
}

extension SettingsView {
    /// Page under docs/ on GitHub, in Spanish when the app is shown in Spanish.
    static func docURL(_ page: String) -> URL {
        let es = Bundle.main.preferredLocalizations.first == "es"
        return URL(string: "https://github.com/javiermugueta/freedomcam/blob/main/docs/\(page)\(es ? ".es" : "").md")!
    }

    static var version: String {
        let info = Bundle.main.infoDictionary
        return "\(info?["CFBundleShortVersionString"] as? String ?? "?") (\(info?["CFBundleVersion"] as? String ?? "?"))"
    }
}
