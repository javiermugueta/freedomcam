import Foundation

/// S3-compatible providers, with the same rules as the Home Assistant integration (const.py, storage.py).
enum StorageProvider: String, Codable, CaseIterable, Identifiable {
    case cloudflareR2 = "cloudflare_r2"
    case awsS3 = "aws_s3"
    case backblazeB2 = "backblaze_b2"
    case wasabi
    case other

    var id: String { rawValue }

    var title: String {
        switch self {
        case .cloudflareR2: return "Cloudflare R2"
        case .awsS3: return "Amazon S3"
        case .backblazeB2: return "Backblaze B2"
        case .wasabi: return "Wasabi"
        case .other: return String(localized: "Other S3-compatible")
        }
    }

    var defaultRegion: String {
        switch self {
        case .cloudflareR2: return "auto"
        case .awsS3: return "eu-west-1"
        case .backblazeB2: return "eu-central-003"
        case .wasabi: return "eu-central-1"
        case .other: return "us-east-1"
        }
    }

    var helpURL: URL? {
        switch self {
        case .cloudflareR2: return URL(string: "https://developers.cloudflare.com/r2/api/tokens/")
        case .awsS3: return URL(string: "https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_access-keys.html")
        case .backblazeB2: return URL(string: "https://www.backblaze.com/docs/cloud-storage-create-and-manage-app-keys")
        case .wasabi: return URL(string: "https://docs.wasabi.com/docs/creating-a-user-account-and-access-key")
        case .other: return nil
        }
    }
}

/// Where the photos are and the (read-only) keys to read them. Stored in the Keychain.
struct StorageConfig: Equatable, Codable {
    var provider: StorageProvider = .cloudflareR2
    var accountId = ""             // Cloudflare R2
    var jurisdiction = "default"   // Cloudflare R2: default, eu, fedramp
    var region = ""                // S3, B2, Wasabi, other
    var endpoint = ""              // other
    var virtualHost = false        // other: https://bucket.endpoint/ instead of https://endpoint/bucket/
    var bucket = ""
    var accessKeyId = ""
    var secretAccessKey = ""

    static let jurisdictions = ["default", "eu", "fedramp"]

    init(provider: StorageProvider = .cloudflareR2, accountId: String = "", jurisdiction: String = "default",
         region: String = "", endpoint: String = "", virtualHost: Bool = false, bucket: String = "",
         accessKeyId: String = "", secretAccessKey: String = "") {
        self.provider = provider
        self.accountId = accountId
        self.jurisdiction = jurisdiction
        self.region = region
        self.endpoint = endpoint
        self.virtualHost = virtualHost
        self.bucket = bucket
        self.accessKeyId = accessKeyId
        self.secretAccessKey = secretAccessKey
    }

    /// Also reads the first version (only `endpoint`, R2 implied): the provider is deduced from the URL.
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        bucket = try c.decodeIfPresent(String.self, forKey: .bucket) ?? ""
        accessKeyId = try c.decodeIfPresent(String.self, forKey: .accessKeyId) ?? ""
        secretAccessKey = try c.decodeIfPresent(String.self, forKey: .secretAccessKey) ?? ""
        accountId = try c.decodeIfPresent(String.self, forKey: .accountId) ?? ""
        jurisdiction = try c.decodeIfPresent(String.self, forKey: .jurisdiction) ?? "default"
        region = try c.decodeIfPresent(String.self, forKey: .region) ?? ""
        endpoint = try c.decodeIfPresent(String.self, forKey: .endpoint) ?? ""
        virtualHost = try c.decodeIfPresent(Bool.self, forKey: .virtualHost) ?? false
        if let p = try c.decodeIfPresent(StorageProvider.self, forKey: .provider) {
            provider = p
        } else {
            provider = .other
            normalize()
        }
    }

    var signingRegion: String {
        provider == .cloudflareR2 ? "auto" : (region.isEmpty ? provider.defaultRegion : region)
    }

    var usesVirtualHost: Bool {
        switch provider {
        case .awsS3: return true
        case .other: return virtualHost
        default: return false
        }
    }

    /// Endpoint of the S3 API, without the bucket.
    var baseURL: URL? {
        let texto: String
        switch provider {
        case .cloudflareR2:
            guard !accountId.isEmpty else { return nil }
            let j = jurisdiction == "default" ? "" : ".\(jurisdiction)"
            texto = "https://\(accountId)\(j).r2.cloudflarestorage.com"
        case .awsS3: texto = "https://s3.\(signingRegion).amazonaws.com"
        case .backblazeB2: texto = "https://s3.\(signingRegion).backblazeb2.com"
        case .wasabi: texto = "https://s3.\(signingRegion).wasabisys.com"
        case .other: texto = endpoint.trimmingCharacters(in: .whitespacesAndNewlines)
        }
        guard var c = URLComponents(string: texto), ["https", "http"].contains(c.scheme ?? ""), c.host != nil
        else { return nil }
        c.path = ""
        c.query = nil
        return c.url
    }

    var isComplete: Bool {
        baseURL != nil && !bucket.isEmpty && !accessKeyId.isEmpty && !secretAccessKey.isEmpty
    }

    /// Tidies what was typed or pasted: spaces, an S3 URL pasted with the bucket behind it,
    /// or a full R2 URL pasted in the Account ID field.
    mutating func normalize() {
        accountId = accountId.trimmingCharacters(in: .whitespacesAndNewlines)
        region = region.trimmingCharacters(in: .whitespacesAndNewlines)
        endpoint = endpoint.trimmingCharacters(in: .whitespacesAndNewlines)
        bucket = bucket.trimmingCharacters(in: .whitespacesAndNewlines)
        accessKeyId = accessKeyId.trimmingCharacters(in: .whitespacesAndNewlines)
        secretAccessKey = secretAccessKey.trimmingCharacters(in: .whitespacesAndNewlines)
        let pegado = provider == .cloudflareR2 && accountId.contains(".") ? accountId : endpoint
        guard let c = URLComponents(string: pegado), let host = c.host else { return }
        let ruta = c.path.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        if !ruta.isEmpty, bucket.isEmpty { bucket = ruta.components(separatedBy: "/")[0] }
        if host.hasSuffix(".r2.cloudflarestorage.com") {
            let partes = host.components(separatedBy: ".")
            provider = .cloudflareR2
            accountId = partes[0]
            jurisdiction = Self.jurisdictions.contains(partes[1]) ? partes[1] : "default"
            endpoint = ""
        } else if provider == .other {
            var limpio = c
            limpio.path = ""
            endpoint = limpio.string ?? endpoint
        }
    }
}
