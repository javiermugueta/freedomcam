import Foundation
import Observation

/// State of the main screen: which day, which cameras, which filter and that day's photos.
@MainActor
@Observable
final class GalleryModel {
    var config: StorageConfig = SettingsStore.load()
    var cameras: [String] = []
    var selectedDay: Date = GalleryModel.initialDay()
    var selectedCamera: String?          // nil = all
    var labelFilter: LabelFilter = .todo
    var photos: [Photo] = []             // all of the day, all cameras, newest first
    var daysWithPhotos: Set<String> = [] // "YYYY-MM-DD" of the months already checked
    var loading = false
    var error: String?
    var newerFormat = false              // the bucket uses a format version this app does not know
    var pendingConnection: StorageConfig? // from a freedomcam:// link or the scanner, waiting for confirmation

    private var manifest: Manifest?
    private var manifestLoaded = false
    private var checkedMonths: Set<String> = []

    var client: S3Client { S3Client(config: config) }

    var visiblePhotos: [Photo] {
        photos.filter { (selectedCamera == nil || $0.camera == selectedCamera) && labelFilter.matches($0) }
    }

    func countFor(camera: String?) -> Int {
        photos.filter { camera == nil || $0.camera == camera }.count
    }

    func name(of camera: String) -> String {
        manifest?.cameras?.first { $0.id == camera }?.name ?? Pretty.cameraName(camera)
    }

    func emoji(of camera: String) -> String {
        Pretty.cameraEmoji(camera, kind: manifest?.cameras?.first { $0.id == camera }?.kind)
    }

    func updateConfig(_ nueva: StorageConfig) {
        config = nueva
        SettingsStore.save(nueva)
        cameras = []
        photos = []
        daysWithPhotos = []
        checkedMonths = []
        manifest = nil
        manifestLoaded = false
    }

    func reload() async {
        guard config.isComplete else { return }
        loading = true
        error = nil
        defer { loading = false }
        do {
            let client = client
            if !manifestLoaded {
                manifest = try await Self.loadManifest(client)
                manifestLoaded = true
                newerFormat = (manifest?.version ?? 0) > Manifest.supportedVersion
            }
            if cameras.isEmpty {
                cameras = try await Self.listCameras(client, manifest: manifest)
            }
            let dia = selectedDay
            let fotos = try await Self.photos(of: dia, client: client, cameras: cameras,
                                              indexedSince: manifest?.indexedSince)
            guard dia == selectedDay else { return }   // the user changed day while loading
            photos = fotos.sorted { $0.time > $1.time }
            if !fotos.isEmpty { daysWithPhotos.insert(dia.dayKey) }
            await loadMonth(of: dia)
        } catch {
            self.error = error.localizedDescription
        }
    }

    /// Marks which days of the month have photos (dots in the day strip).
    func loadMonth(of day: Date) async {
        let mes = day.monthPath
        guard config.isComplete, !cameras.isEmpty, !checkedMonths.contains(mes) else { return }
        checkedMonths.insert(mes)
        let dias = await Self.days(ofMonth: mes, client: client, cameras: cameras,
                                   indexedSince: manifest?.indexedSince)
        daysWithPhotos.formUnion(dias)
    }

    // MARK: - Reading the bucket (indexes first, listing as a fallback)

    nonisolated static func loadManifest(_ client: S3Client) async throws -> Manifest? {
        guard let datos = try await client.objectIfExists(key: Manifest.key) else { return nil }
        return try? JSONDecoder().decode(Manifest.self, from: datos)
    }

    /// Cameras of the manifest (in its order) plus any other folder with photos (older buckets).
    nonisolated static func listCameras(_ client: S3Client, manifest: Manifest?) async throws -> [String] {
        let carpetas = try await client.list(prefix: "", delimiter: "/").prefixes
            .map { String($0.dropLast()) }.filter(isCamera)
        let delManifiesto = manifest?.cameras?.map(\.id) ?? []
        return delManifiesto + carpetas.filter { !delManifiesto.contains($0) }.sorted()
    }

    /// The day index is used alone when it is complete (from `indexed_since`). Older days are listed
    /// camera by camera, taking the thumbnails from the index when there is one.
    nonisolated static func photos(of day: Date, client: S3Client, cameras: [String],
                                   indexedSince: String?) async throws -> [Photo] {
        let indice = try await client.objectIfExists(key: DayIndex.key(day))
            .flatMap { try? JSONDecoder().decode(DayIndex.self, from: $0) }
        if let indice, let desde = indexedSince, day.dayKey >= desde {
            return indice.parsed
        }
        let miniaturas = Dictionary((indice?.parsed ?? []).map { ($0.key, $0.thumb) }, uniquingKeysWith: { a, _ in a })
        let listadas = try await withThrowingTaskGroup(of: [Photo].self) { grupo in
            for camara in cameras {
                grupo.addTask { try await client.list(prefix: "\(camara)/\(day.dayPath)/").keys.compactMap(Photo.parse) }
            }
            var todas: [Photo] = []
            for try await parte in grupo { todas += parte }
            return todas
        }
        return listadas.map { foto in
            var f = foto
            f.thumb = miniaturas[foto.key] ?? nil
            return f
        }
    }

    /// Days with photos in a month ("YYYY/MM"): month summary, plus listing if the month is not fully indexed.
    nonisolated static func days(ofMonth mes: String, client: S3Client, cameras: [String],
                                 indexedSince: String?) async -> Set<String> {
        let dash = mes.replacingOccurrences(of: "/", with: "-")
        var dias = Set<String>()
        if let datos = try? await client.objectIfExists(key: MonthIndex.key(mes)),
           let resumen = try? JSONDecoder().decode(MonthIndex.self, from: datos) {
            dias.formUnion(resumen.days.filter { ($0.value.photos ?? 1) > 0 }.keys.map { "\(dash)-\($0)" })
        }
        if let desde = indexedSince, "\(dash)-01" >= desde { return dias }
        let listados: [String] = (try? await withThrowingTaskGroup(of: [String].self) { grupo in
            for camara in cameras {
                grupo.addTask {
                    let prefijos = try await client.list(prefix: "\(camara)/\(mes)/", delimiter: "/").prefixes
                    // camera/YYYY/MM/DD/ -> YYYY-MM-DD
                    return prefijos.map { (p: String) -> String in p.split(separator: "/").dropFirst().joined(separator: "-") }
                }
            }
            var todos: [String] = []
            for try await parte in grupo { todos += parte }
            return todos
        }) ?? []
        return dias.union(listados)
    }

    private static func initialDay() -> Date {
        #if DEBUG
        // For simulator screenshots: SIMCTL_CHILD_FC_DAY=YYYY-MM-DD
        if let texto = ProcessInfo.processInfo.environment["FC_DAY"],
           let dia = try? Date(texto + "T12:00:00Z", strategy: .iso8601) {
            return Calendar.current.startOfDay(for: dia)
        }
        #endif
        return Calendar.current.startOfDay(for: Date())
    }

    /// Tries a configuration without saving it. Returns the camera names found.
    static func test(_ config: StorageConfig) async throws -> [String] {
        let client = S3Client(config: config)
        let manifest = try await loadManifest(client)
        let ids = try await listCameras(client, manifest: manifest)
        return ids.map { id in manifest?.cameras?.first { $0.id == id }?.name ?? Pretty.cameraName(id) }
    }

    /// Folders starting with "_" belong to freedomCam (_thumbs, _index), not to cameras.
    nonisolated static func isCamera(_ folder: String) -> Bool { !folder.hasPrefix("_") }
}
