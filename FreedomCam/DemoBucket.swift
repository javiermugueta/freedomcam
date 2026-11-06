import Foundation

/// The demo mode: a week of made-up photos inside the app (FreedomCam/Demo, see tools/make_demo.py),
/// served as if they came from a bucket in the freedomCam format. Works without network or account.
/// Days are relative: "offset" 0 is today, so the demo always shows the last 7 days.
enum DemoBucket {
    private struct File: Decodable {
        struct Camera: Decodable { let id: String; let kind: String }
        struct Entry: Decodable {
            let offset: Int
            let camera: String
            let time: String       // HHMMSS
            let labels: [String]
            let file: String
            let thumb: String
        }
        let cameras: [Camera]
        let photos: [Entry]
    }

    private static let folder = Bundle.main.url(forResource: "Demo", withExtension: nil)

    private static let file: File? = {
        guard let url = folder?.appendingPathComponent("demo.json"), let data = try? Data(contentsOf: url) else { return nil }
        return try? JSONDecoder().decode(File.self, from: data)
    }()

    static func cameraName(_ id: String) -> String {
        switch id {
        case "driveway": return String(localized: "Driveway")
        case "garden": return String(localized: "Garden")
        case "hall": return String(localized: "Hall")
        default: return Pretty.cameraName(id)
        }
    }

    private enum Content { case bundled(String), json(Data) }

    /// Bucket contents for "now": key -> bundled file (photos and thumbnails) or generated JSON.
    private static func contents(now: Date = Date()) -> [String: Content] {
        guard let file else { return [:] }
        let cal = Calendar.current
        let hoy = cal.startOfDay(for: now)
        let c = cal.dateComponents([.hour, .minute, .second], from: now)
        let ahora = String(format: "%02d%02d%02d", c.hour ?? 0, c.minute ?? 0, c.second ?? 0)
        var objetos: [String: Content] = [:]
        var dias: [String: [[String: Any]]] = [:]
        var meses: [String: [String: [String: Any]]] = [:]
        for e in file.photos {
            guard let dia = cal.date(byAdding: .day, value: -e.offset, to: hoy) else { continue }
            if e.offset == 0 && e.time > ahora { continue }        // no photos from the future today
            let sufijo = e.labels.isEmpty ? "" : "_" + e.labels.joined(separator: "-")
            let key = "\(e.camera)/\(dia.dayPath)/\(e.time)\(sufijo).jpg"
            objetos[key] = .bundled(e.file)
            objetos["_thumbs/" + key] = .bundled(e.thumb)
            let t = Array(e.time)
            dias[dia.dayPath, default: []].append(["camera": e.camera, "key": key, "thumb": "_thumbs/" + key,
                                                   "time": "\(t[0])\(t[1]):\(t[2])\(t[3]):\(t[4])\(t[5])", "labels": e.labels])
            let dd = String(dia.dayPath.suffix(2))
            var stats = meses[dia.monthPath, default: [:]][dd] ?? ["photos": 0]
            stats["photos"] = (stats["photos"] as? Int ?? 0) + 1
            meses[dia.monthPath, default: [:]][dd] = stats
        }
        for (path, fotos) in dias {
            objetos["_index/\(path).json"] = json(["version": 1, "photos": fotos])
        }
        for (mes, days) in meses {
            objetos["_index/\(mes).json"] = json(["version": 1, "days": days])
        }
        let desde = cal.date(byAdding: .day, value: -7, to: hoy) ?? hoy
        let manifiesto: [String: Any] = [
            "format": "freedomcam", "version": 1, "indexed_since": desde.dayKey,
            "cameras": file.cameras.map { ["id": $0.id, "name": cameraName($0.id), "kind": $0.kind] },
        ]
        objetos[Manifest.key] = json(manifiesto)
        return objetos
    }

    private static func json(_ value: Any) -> Content {
        .json((try? JSONSerialization.data(withJSONObject: value)) ?? Data())
    }

    static func object(key: String, now: Date = Date()) throws -> Data {
        switch contents(now: now)[key] {
        case let .json(data): return data
        case let .bundled(name):
            if let url = folder?.appendingPathComponent(name), let data = try? Data(contentsOf: url) { return data }
            throw S3Error.http(404, "")
        case nil: throw S3Error.http(404, "")
        }
    }

    static func list(prefix: String, delimiter: String?, now: Date = Date()) -> ListResult {
        let keys = contents(now: now).keys.filter { $0.hasPrefix(prefix) }.sorted()
        guard let delimiter else { return ListResult(keys: keys, prefixes: []) }
        var resultado = ListResult()
        var vistos = Set<String>()
        for key in keys {
            let resto = key.dropFirst(prefix.count)
            if let r = resto.range(of: delimiter) {
                let p = prefix + resto[..<r.upperBound]
                if vistos.insert(String(p)).inserted { resultado.prefixes.append(String(p)) }
            } else {
                resultado.keys.append(key)
            }
        }
        return resultado
    }
}
