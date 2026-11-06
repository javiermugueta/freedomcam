import Foundation

/// One photo of the bucket. Keys are `<camera>/YYYY/MM/DD/HHMMSS[_label-label].jpg` (docs/bucket-format.md).
struct Photo: Identifiable, Hashable {
    let key: String
    let camera: String
    let day: String          // "YYYY-MM-DD"
    let time: String         // "HH:MM:SS"
    let labels: [String]     // person, car, motorcycle, bicycle, dog, cat
    var thumb: String?       // thumbnail key, when the day index has it

    var id: String { key }

    static func parse(_ key: String) -> Photo? {
        let partes = key.split(separator: "/").map(String.init)
        guard partes.count == 5, partes[4].hasSuffix(".jpg") else { return nil }
        let nombre = String(partes[4].dropLast(4))
        let trozos = nombre.split(separator: "_", maxSplits: 1).map(String.init)
        let hhmmss = trozos[0]
        guard hhmmss.count == 6, hhmmss.allSatisfy(\.isNumber) else { return nil }
        let h = Array(hhmmss)
        let labels = trozos.count > 1 ? trozos[1].split(separator: "-").map { Pretty.canonical(String($0)) } : []
        return Photo(key: key, camera: partes[0], day: "\(partes[1])-\(partes[2])-\(partes[3])",
                     time: "\(h[0])\(h[1]):\(h[2])\(h[3]):\(h[4])\(h[5])", labels: labels)
    }
}

// MARK: - Bucket documents (freedomcam.json and _index/)

struct Manifest: Decodable {
    struct Camera: Decodable {
        let id: String
        let name: String?
        let kind: String?
    }

    let format: String?
    let version: Int?
    let cameras: [Camera]?
    let indexedSince: String?       // first day whose index is complete ("YYYY-MM-DD")

    enum CodingKeys: String, CodingKey {
        case format, version, cameras
        case indexedSince = "indexed_since"
    }

    static let key = "freedomcam.json"
    static let supportedVersion = 1
}

struct DayIndex: Decodable {
    struct Entry: Decodable {
        let key: String
        let thumb: String?
    }

    let photos: [Entry]

    static func key(_ day: Date) -> String { "_index/\(day.dayPath).json" }

    var parsed: [Photo] {
        photos.compactMap { e in
            var p = Photo.parse(e.key)
            p?.thumb = e.thumb
            return p
        }
    }
}

struct MonthIndex: Decodable {
    let days: [String: Day]

    struct Day: Decodable { let photos: Int? }

    static func key(_ monthPath: String) -> String { "_index/\(monthPath).json" }
}

// MARK: - Names and emojis

/// Camera names come from the manifest; without it the folder name is tidied up.
enum Pretty {
    static func cameraName(_ id: String) -> String {
        let texto = id.replacingOccurrences(of: "_", with: " ").replacingOccurrences(of: "-", with: " ")
        return texto.prefix(1).uppercased() + texto.dropFirst()
    }

    static func cameraEmoji(_ id: String, kind: String? = nil) -> String {
        let s = id.lowercased()
        let pistas: [(String, String)] = [
            ("jardin", "🌳"), ("garden", "🌳"), ("yard", "🌳"), ("barrera", "🚧"), ("gate", "🚧"),
            ("placeta", "🏘️"), ("street", "🏘️"), ("calle", "🏘️"), ("hall", "🚪"), ("door", "🚪"),
            ("entrada", "🚪"), ("sotano", "🧺"), ("basement", "🧺"), ("garaje", "🚗"), ("garage", "🚗"),
            ("patio", "🪴"), ("terraza", "🪴"), ("salon", "🛋️"), ("living", "🛋️"), ("cocina", "🍳"),
            ("kitchen", "🍳"),
        ]
        if let e = pistas.first(where: { s.contains($0.0) }) { return e.1 }
        switch kind {
        case "indoor": return "🏠"
        case "outdoor": return "🌤️"
        default: return "📷"
        }
    }

    /// Labels written before format v1 (in Spanish) -> format label.
    static let legacyLabels = ["persona": "person", "coche": "car", "moto": "motorcycle", "bici": "bicycle",
                               "perro": "dog", "gato": "cat"]

    static func canonical(_ label: String) -> String { legacyLabels[label] ?? label }

    static func labelEmoji(_ label: String) -> String {
        ["person": "🧍", "car": "🚗", "motorcycle": "🏍️", "bicycle": "🚲", "dog": "🐶", "cat": "🐱"][label] ?? "❓"
    }

    static func labelName(_ label: String) -> String {
        switch label {
        case "person": return String(localized: "person")
        case "car": return String(localized: "car")
        case "motorcycle": return String(localized: "motorcycle")
        case "bicycle": return String(localized: "bicycle")
        case "dog": return String(localized: "dog")
        case "cat": return String(localized: "cat")
        default: return label
        }
    }
}

/// Quick filter by what was detected in the photo.
enum LabelFilter: String, CaseIterable, Identifiable {
    case todo, personas, vehiculos, animales, nada

    var id: String { rawValue }

    var title: String {
        switch self {
        case .todo: return String(localized: "All")
        case .personas: return String(localized: "🧍 People")
        case .vehiculos: return String(localized: "🚗 Vehicles")
        case .animales: return String(localized: "🐾 Animals")
        case .nada: return String(localized: "🍃 Nothing")
        }
    }

    func matches(_ photo: Photo) -> Bool {
        let l = Set(photo.labels)
        switch self {
        case .todo: return true
        case .personas: return l.contains("person")
        case .vehiculos: return !l.isDisjoint(with: ["car", "motorcycle", "bicycle"])
        case .animales: return !l.isDisjoint(with: ["dog", "cat"])
        case .nada: return l.isEmpty
        }
    }
}

extension Date {
    /// "YYYY-MM-DD" in the local calendar.
    var dayKey: String {
        let c = Calendar.current.dateComponents([.year, .month, .day], from: self)
        return String(format: "%04d-%02d-%02d", c.year!, c.month!, c.day!)
    }

    /// "YYYY/MM/DD" for bucket prefixes.
    var dayPath: String { dayKey.replacingOccurrences(of: "-", with: "/") }

    var monthPath: String { String(dayPath.prefix(7)) }
}
