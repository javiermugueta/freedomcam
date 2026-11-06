import CryptoKit
import Foundation

enum S3Error: LocalizedError {
    case incompleteConfig
    case http(Int, String)
    case badResponse

    var errorDescription: String? {
        switch self {
        case .incompleteConfig: return String(localized: "The bucket is not set up yet. Open Settings.")
        case let .http(code, message):
            switch code {
            case 401, 403: return String(localized: "The storage does not let me in (\(code)). Check the keys and the region in Settings.")
            case 404: return String(localized: "Bucket not found (404). Is the name right?")
            default: return String(localized: "The storage answered \(code). \(message)")
            }
        case .badResponse: return String(localized: "The storage answered something I do not understand.")
        }
    }
}

struct ListResult {
    var keys: [String] = []
    var prefixes: [String] = []
}

/// Minimal S3 client: list and download objects, signed with AWS Signature V4.
struct S3Client {
    let config: StorageConfig
    var session: URLSession = .shared

    /// Lista todo lo que hay bajo `prefix` (sigue la paginación). Con `delimiter` devuelve las "carpetas" en `prefixes`.
    func list(prefix: String, delimiter: String? = nil) async throws -> ListResult {
        if config.demo { return DemoBucket.list(prefix: prefix, delimiter: delimiter) }
        var resultado = ListResult()
        var continuacion: String?
        repeat {
            var query = [("list-type", "2"), ("prefix", prefix)]
            if let delimiter { query.append(("delimiter", delimiter)) }
            if let continuacion { query.append(("continuation-token", continuacion)) }
            let datos = try await send(key: nil, query: query)
            let pagina = ListParser.parse(datos)
            guard let pagina else { throw S3Error.badResponse }
            resultado.keys += pagina.keys
            resultado.prefixes += pagina.prefixes
            continuacion = pagina.truncated ? pagina.nextToken : nil
        } while continuacion != nil
        return resultado
    }

    func object(key: String) async throws -> Data {
        if config.demo { return try DemoBucket.object(key: key) }
        return try await send(key: key, query: [])
    }

    /// The object, or nil if it does not exist (indexes and the manifest are optional).
    func objectIfExists(key: String) async throws -> Data? {
        do {
            return try await object(key: key)
        } catch let S3Error.http(code, _) where code == 404 {
            return nil
        }
    }

    private func send(key: String?, query: [(String, String)]) async throws -> Data {
        guard config.isComplete else { throw S3Error.incompleteConfig }
        let request = try signedRequest(key: key, query: query, date: Date())
        let (datos, respuesta) = try await session.data(for: request)
        guard let http = respuesta as? HTTPURLResponse else { throw S3Error.badResponse }
        guard http.statusCode == 200 else {
            let mensaje = String(data: datos, encoding: .utf8).flatMap(ListParser.errorMessage) ?? ""
            throw S3Error.http(http.statusCode, mensaje)
        }
        return datos
    }

    // MARK: - SigV4

    static let hashVacio = SHA256.hash(data: Data()).hex

    /// Request for an object (`key`) or for the bucket itself (`key` nil), path-style or virtual-hosted.
    func signedRequest(key: String?, query: [(String, String)], date: Date) throws -> URLRequest {
        guard let base = config.baseURL, let baseHost = base.host, let scheme = base.scheme
        else { throw S3Error.incompleteConfig }
        let host = config.usesVirtualHost ? "\(config.bucket).\(baseHost)" : baseHost
        let hostCabecera = base.port.map { "\(host):\($0)" } ?? host
        let ruta = config.usesVirtualHost ? "/" + (key ?? "") : "/\(config.bucket)" + (key.map { "/" + $0 } ?? "")
        let region = config.signingRegion

        let rutaCanonica = ruta.split(separator: "/", omittingEmptySubsequences: false)
            .map { Self.encode(String($0)) }.joined(separator: "/")
        let pares: [(String, String)] = query.map { (Self.encode($0.0), Self.encode($0.1)) }
        let ordenados = pares.sorted { a, b in a.0 == b.0 ? a.1 < b.1 : a.0 < b.0 }
        let queryCanonica = ordenados.map { par in par.0 + "=" + par.1 }.joined(separator: "&")

        let fmt = DateFormatter()
        fmt.locale = Locale(identifier: "en_US_POSIX")
        fmt.timeZone = TimeZone(identifier: "UTC")
        fmt.dateFormat = "yyyyMMdd'T'HHmmss'Z'"
        let sello = fmt.string(from: date)
        let fecha = String(sello.prefix(8))

        let cabeceras = ["host": hostCabecera, "x-amz-content-sha256": Self.hashVacio, "x-amz-date": sello]
        let firmadas = cabeceras.keys.sorted().joined(separator: ";")
        let canonica = [
            "GET", rutaCanonica, queryCanonica,
            cabeceras.keys.sorted().map { "\($0):\(cabeceras[$0]!)" }.joined(separator: "\n") + "\n",
            firmadas, Self.hashVacio,
        ].joined(separator: "\n")

        let ambito = "\(fecha)/\(region)/s3/aws4_request"
        let aFirmar = ["AWS4-HMAC-SHA256", sello, ambito, SHA256.hash(data: Data(canonica.utf8)).hex]
            .joined(separator: "\n")
        var clave = SymmetricKey(data: Data("AWS4\(config.secretAccessKey)".utf8))
        for parte in [fecha, region, "s3", "aws4_request"] {
            clave = SymmetricKey(data: Data(HMAC<SHA256>.authenticationCode(for: Data(parte.utf8), using: clave)))
        }
        let firma = Data(HMAC<SHA256>.authenticationCode(for: Data(aFirmar.utf8), using: clave)).hex

        var texto = "\(scheme)://\(hostCabecera)" + rutaCanonica
        if !queryCanonica.isEmpty { texto += "?" + queryCanonica }
        guard let url = URL(string: texto) else { throw S3Error.incompleteConfig }
        var request = URLRequest(url: url)
        request.setValue(Self.hashVacio, forHTTPHeaderField: "x-amz-content-sha256")
        request.setValue(sello, forHTTPHeaderField: "x-amz-date")
        request.setValue("AWS4-HMAC-SHA256 Credential=\(config.accessKeyId)/\(ambito), SignedHeaders=\(firmadas), Signature=\(firma)",
                         forHTTPHeaderField: "Authorization")
        request.timeoutInterval = 30
        return request
    }

    /// Codificación de SigV4: todo menos los caracteres no reservados de RFC 3986.
    static func encode(_ s: String) -> String {
        let permitidos = CharacterSet(charactersIn: "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_.~")
        return s.addingPercentEncoding(withAllowedCharacters: permitidos) ?? s
    }
}

private extension Sequence where Element == UInt8 {
    var hex: String { map { String(format: "%02x", $0) }.joined() }
}

private extension Digest {
    var hex: String { Array(makeIterator()).hex }
}

// MARK: - XML de ListObjectsV2

private final class ListParser: NSObject, XMLParserDelegate {
    struct Pagina { var keys: [String] = []; var prefixes: [String] = []; var truncated = false; var nextToken: String? }

    private var pagina = Pagina()
    private var texto = ""
    private var enPrefijos = false
    private var mensaje: String?

    static func parse(_ datos: Data) -> Pagina? {
        let p = ListParser()
        let parser = XMLParser(data: datos)
        parser.delegate = p
        return parser.parse() ? p.pagina : nil
    }

    static func errorMessage(_ xml: String) -> String? {
        let p = ListParser()
        let parser = XMLParser(data: Data(xml.utf8))
        parser.delegate = p
        parser.parse()
        return p.mensaje
    }

    func parser(_ parser: XMLParser, didStartElement name: String, namespaceURI: String?, qualifiedName: String?,
                attributes: [String: String] = [:]) {
        texto = ""
        if name == "CommonPrefixes" { enPrefijos = true }
    }

    func parser(_ parser: XMLParser, foundCharacters string: String) { texto += string }

    func parser(_ parser: XMLParser, didEndElement name: String, namespaceURI: String?, qualifiedName: String?) {
        switch name {
        case "Key": pagina.keys.append(texto)
        case "Prefix" where enPrefijos: pagina.prefixes.append(texto)
        case "CommonPrefixes": enPrefijos = false
        case "IsTruncated": pagina.truncated = texto == "true"
        case "NextContinuationToken": pagina.nextToken = texto
        case "Message": mensaje = texto
        default: break
        }
    }
}
