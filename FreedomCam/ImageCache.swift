import ImageIO
import UIKit

/// Downloads and keeps photos (they never change: the key has the time). Memory for thumbnails,
/// disk (Caches) for the JPEG files, so going back to a day already seen uses no data.
actor ImageCache {
    static let shared = ImageCache()

    private let memoria = NSCache<NSString, UIImage>()
    private var enCurso: [String: Task<Data, Error>] = [:]
    private let carpeta: URL = {
        let url = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("fotos", isDirectory: true)
        try? FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
        return url
    }()

    init() { memoria.countLimit = 300 }

    func thumbnail(_ key: String, client: S3Client, maxPixel: CGFloat = 500) async throws -> UIImage {
        let id = "\(key)#\(Int(maxPixel))" as NSString
        if let img = memoria.object(forKey: id) { return img }
        let datos = try await data(key, client: client)
        let img = Self.downsample(datos, maxPixel: maxPixel) ?? UIImage()
        memoria.setObject(img, forKey: id)
        return img
    }

    func full(_ key: String, client: S3Client) async throws -> UIImage {
        let datos = try await data(key, client: client)
        return UIImage(data: datos) ?? UIImage()
    }

    func clearDisk() {
        try? FileManager.default.removeItem(at: carpeta)
        try? FileManager.default.createDirectory(at: carpeta, withIntermediateDirectories: true)
        memoria.removeAllObjects()
    }

    func diskBytes() -> Int {
        let archivos = (try? FileManager.default.contentsOfDirectory(at: carpeta, includingPropertiesForKeys: [.fileSizeKey])) ?? []
        return archivos.reduce(0) { $0 + ((try? $1.resourceValues(forKeys: [.fileSizeKey]).fileSize) ?? 0) }
    }

    private func data(_ key: String, client: S3Client) async throws -> Data {
        let archivo = carpeta.appendingPathComponent(key.replacingOccurrences(of: "/", with: "_"))
        if let datos = try? Data(contentsOf: archivo) { return datos }
        if let tarea = enCurso[key] { return try await tarea.value }
        let tarea = Task { try await client.object(key: key) }
        enCurso[key] = tarea
        defer { enCurso[key] = nil }
        let datos = try await tarea.value
        try? datos.write(to: archivo)
        return datos
    }

    private static func downsample(_ datos: Data, maxPixel: CGFloat) -> UIImage? {
        guard let fuente = CGImageSourceCreateWithData(datos as CFData, nil) else { return nil }
        let opciones: [CFString: Any] = [
            kCGImageSourceCreateThumbnailFromImageAlways: true,
            kCGImageSourceCreateThumbnailWithTransform: true,
            kCGImageSourceThumbnailMaxPixelSize: maxPixel,
        ]
        guard let cg = CGImageSourceCreateThumbnailAtIndex(fuente, 0, opciones as CFDictionary) else { return nil }
        return UIImage(cgImage: cg)
    }
}
