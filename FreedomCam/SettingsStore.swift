import Foundation
import Security

/// Keeps the storage settings in the iPhone Keychain (never in UserDefaults).
enum SettingsStore {
    private static let service = "com.jmugueta.freedomcam"
    private static let account = "r2-config"     // name kept from the first version

    static func load() -> StorageConfig {
        #if DEBUG
        // For simulator tests: SIMCTL_CHILD_R2_ENDPOINT, ..._BUCKET, ..._KEY_ID, ..._SECRET
        let env = ProcessInfo.processInfo.environment
        if env["FC_DEMO"] == "1" { return .demoConfig }
        if let endpoint = env["R2_ENDPOINT"], let bucket = env["R2_BUCKET"], let id = env["R2_KEY_ID"],
           let secret = env["R2_SECRET"] {
            var c = StorageConfig(provider: .other, endpoint: endpoint, bucket: bucket, accessKeyId: id,
                                  secretAccessKey: secret)
            c.normalize()
            return c
        }
        #endif
        var query = baseQuery
        query[kSecReturnData as String] = true
        query[kSecMatchLimit as String] = kSecMatchLimitOne
        var item: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &item) == errSecSuccess, let data = item as? Data,
              let config = try? JSONDecoder().decode(StorageConfig.self, from: data) else { return StorageConfig() }
        return config
    }

    static func save(_ config: StorageConfig) {
        guard let data = try? JSONEncoder().encode(config) else { return }
        SecItemDelete(baseQuery as CFDictionary)
        var query = baseQuery
        query[kSecValueData as String] = data
        query[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        SecItemAdd(query as CFDictionary, nil)
    }

    static func clear() { SecItemDelete(baseQuery as CFDictionary) }

    private static var baseQuery: [String: Any] {
        [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service,
         kSecAttrAccount as String: account]
    }
}
