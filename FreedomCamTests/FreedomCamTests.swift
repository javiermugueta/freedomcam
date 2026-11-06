import XCTest
@testable import FreedomCam

final class FreedomCamTests: XCTestCase {
    func testParseConEtiquetas() throws {
        let p = try XCTUnwrap(Photo.parse("barrera_oeste/2026/11/05/122243_coche-persona.jpg"))
        XCTAssertEqual(p.camera, "barrera_oeste")
        XCTAssertEqual(p.day, "2026-11-05")
        XCTAssertEqual(p.time, "12:22:43")
        XCTAssertEqual(p.labels, ["car", "person"])          // etiquetas antiguas en español
        let nueva = try XCTUnwrap(Photo.parse("garden/2026/11/06/181502_car-person.jpg"))
        XCTAssertEqual(nueva.labels, ["car", "person"])      // formato v1, en inglés
    }

    func testParseSinEtiquetas() throws {
        let p = try XCTUnwrap(Photo.parse("hall/2026/11/05/180310.jpg"))
        XCTAssertEqual(p.labels, [])
        XCTAssertEqual(p.time, "18:03:10")
    }

    func testCarpetasReservadasNoSonCamaras() {
        XCTAssertTrue(GalleryModel.isCamera("hall"))
        XCTAssertFalse(GalleryModel.isCamera("_thumbs"))
        XCTAssertFalse(GalleryModel.isCamera("_index"))
    }

    func testParseDescartaRaros() {
        XCTAssertNil(Photo.parse("hall/2026/11/05/"))
        XCTAssertNil(Photo.parse("hall/2026/11/05/abc.jpg"))
        XCTAssertNil(Photo.parse("leeme.txt"))
    }

    func testFiltros() throws {
        let persona = try XCTUnwrap(Photo.parse("a/2026/11/05/100000_persona.jpg"))
        let coche = try XCTUnwrap(Photo.parse("a/2026/11/05/100001_coche.jpg"))
        let nada = try XCTUnwrap(Photo.parse("a/2026/11/05/100002.jpg"))
        XCTAssertTrue(LabelFilter.personas.matches(persona))
        XCTAssertFalse(LabelFilter.personas.matches(coche))
        XCTAssertTrue(LabelFilter.vehiculos.matches(coche))
        XCTAssertTrue(LabelFilter.nada.matches(nada))
        XCTAssertFalse(LabelFilter.nada.matches(persona))
    }

    func testPegarURLDeR2() {
        var c = StorageConfig(provider: .cloudflareR2, accountId: "https://abc.eu.r2.cloudflarestorage.com/cameras/")
        c.normalize()
        XCTAssertEqual(c.accountId, "abc")
        XCTAssertEqual(c.jurisdiction, "eu")
        XCTAssertEqual(c.bucket, "cameras")
        XCTAssertEqual(c.baseURL?.absoluteString, "https://abc.eu.r2.cloudflarestorage.com")
    }

    /// The first version only saved the R2 endpoint: it must still open as R2.
    func testConfiguracionAntigua() throws {
        let json = #"{"endpoint":"https://abc.r2.cloudflarestorage.com","bucket":"b","accessKeyId":"k","secretAccessKey":"s"}"#
        let c = try JSONDecoder().decode(StorageConfig.self, from: Data(json.utf8))
        XCTAssertEqual(c.provider, .cloudflareR2)
        XCTAssertEqual(c.accountId, "abc")
        XCTAssertEqual(c.signingRegion, "auto")
        XCTAssertTrue(c.isComplete)
    }

    func testEndpointsPorProveedor() {
        XCTAssertEqual(StorageConfig(provider: .awsS3, region: "eu-south-2").baseURL?.absoluteString,
                       "https://s3.eu-south-2.amazonaws.com")
        XCTAssertEqual(StorageConfig(provider: .backblazeB2).baseURL?.absoluteString,
                       "https://s3.eu-central-003.backblazeb2.com")
        XCTAssertEqual(StorageConfig(provider: .other, endpoint: "http://192.168.1.10:9000/").baseURL?.absoluteString,
                       "http://192.168.1.10:9000")
        XCTAssertNil(StorageConfig(provider: .other, endpoint: "minio").baseURL)
    }

    /// Signatures checked against the Home Assistant integration's signer, which matches the AWS SDK.
    func testFirmasComoAWS() throws {
        let fecha = Date(timeIntervalSince1970: 1_700_000_000)
        func firma(_ r: URLRequest) -> String? {
            r.value(forHTTPHeaderField: "Authorization")?.components(separatedBy: "Signature=").last
        }
        let r2 = S3Client(config: StorageConfig(provider: .cloudflareR2, accountId: "abc", bucket: "b",
                                                accessKeyId: "AKID", secretAccessKey: "secreto"))
        let a = try r2.signedRequest(key: nil, query: [("prefix", "hall/"), ("list-type", "2")], date: fecha)
        XCTAssertEqual(a.url?.absoluteString, "https://abc.r2.cloudflarestorage.com/b?list-type=2&prefix=hall%2F")
        XCTAssertEqual(firma(a), "77d0d2de75bc3d7a4e62d90b013ef1e54a825ba82c730ab2c158294d08e095db")

        let aws = S3Client(config: StorageConfig(provider: .awsS3, region: "eu-south-2", bucket: "fotos",
                                                 accessKeyId: "AKID", secretAccessKey: "secreto"))
        let b = try aws.signedRequest(key: "hall/2026/11/06/180310_person.jpg", query: [], date: fecha)
        XCTAssertEqual(b.url?.absoluteString, "https://fotos.s3.eu-south-2.amazonaws.com/hall/2026/11/06/180310_person.jpg")
        XCTAssertEqual(firma(b), "6180f109477100fa28df9828af490345d93d3835c0c0a8b2a42e6a5c89602730")

        let minio = S3Client(config: StorageConfig(provider: .other, endpoint: "http://192.168.1.10:9000", bucket: "cams",
                                                   accessKeyId: "AKID", secretAccessKey: "secreto"))
        let c = try minio.signedRequest(key: "cámara 1/2026/11/06/080000.jpg", query: [], date: fecha)
        XCTAssertEqual(c.url?.absoluteString, "http://192.168.1.10:9000/cams/c%C3%A1mara%201/2026/11/06/080000.jpg")
        XCTAssertEqual(firma(c), "4bb1ec73055906c290159f70203f814cf12120ef52d54b67e39b473e6137d23b")
    }

    func testIndiceDelDia() throws {
        let json = #"{"version":1,"date":"2026-11-06","photos":[{"camera":"hall","time":"18:03:10","key":"hall/2026/11/06/180310_person.jpg","thumb":"_thumbs/hall/2026/11/06/180310_person.jpg","labels":["person"],"size":1},{"camera":"g","time":"09:00:00","key":"g/2026/11/06/090000.jpg","labels":[]}]}"#
        let fotos = try JSONDecoder().decode(DayIndex.self, from: Data(json.utf8)).parsed
        XCTAssertEqual(fotos.count, 2)
        XCTAssertEqual(fotos[0].thumb, "_thumbs/hall/2026/11/06/180310_person.jpg")
        XCTAssertEqual(fotos[0].labels, ["person"])
        XCTAssertNil(fotos[1].thumb)
    }

    func testManifiesto() throws {
        let json = #"{"format":"freedomcam","version":1,"timezone":"Europe/Madrid","indexed_since":"2026-11-07","cameras":[{"id":"hall","name":"Hall","kind":"indoor"}],"extra":true}"#
        let m = try JSONDecoder().decode(Manifest.self, from: Data(json.utf8))
        XCTAssertEqual(m.indexedSince, "2026-11-07")
        XCTAssertEqual(m.cameras?.first?.name, "Hall")
    }

    /// Links made by the Home Assistant integration (connection.py).
    func testCodigoQR() throws {
        let r2 = try XCTUnwrap(ConnectionCode.parse("freedomcam://connect?c=eyJ2IjoxLCJwcm92aWRlciI6ImNsb3VkZmxhcmVfcjIiLCJidWNrZXQiOiJmb3RvcyIsImFjY2Vzc19rZXlfaWQiOiJSTyIsInNlY3JldF9hY2Nlc3Nfa2V5IjoiUk9TRUNSRVQiLCJhY2NvdW50X2lkIjoiYWJjIiwianVyaXNkaWN0aW9uIjoiZXUifQ"))
        XCTAssertEqual(r2.provider, .cloudflareR2)
        XCTAssertEqual(r2.baseURL?.absoluteString, "https://abc.eu.r2.cloudflarestorage.com")
        XCTAssertEqual(r2.bucket, "fotos")
        XCTAssertEqual(r2.accessKeyId, "RO")
        XCTAssertEqual(r2.secretAccessKey, "ROSECRET")
        let minio = try XCTUnwrap(ConnectionCode.parse("freedomcam://connect?c=eyJ2IjoxLCJwcm92aWRlciI6Im90aGVyIiwiYnVja2V0IjoiY2FtcyIsImFjY2Vzc19rZXlfaWQiOiJLIiwic2VjcmV0X2FjY2Vzc19rZXkiOiJTIiwicmVnaW9uIjoidXMtZWFzdC0xIiwiZW5kcG9pbnQiOiJodHRwOi8vMTkyLjE2OC4xLjEwOjkwMDAiLCJ2aXJ0dWFsX2hvc3QiOmZhbHNlfQ"))
        XCTAssertEqual(minio.baseURL?.absoluteString, "http://192.168.1.10:9000")
        XCTAssertEqual(minio.signingRegion, "us-east-1")
        XCTAssertNil(ConnectionCode.parse("https://example.com"))
        XCTAssertNil(ConnectionCode.parse("freedomcam://connect?c=basura"))
    }

    /// The demo bucket answers like a real one: manifest, indexes, photos and thumbnails, nothing in the future.
    func testModoDemo() throws {
        let tarde = Calendar.current.date(bySettingHour: 23, minute: 59, second: 0, of: Date())!
        let raiz = DemoBucket.list(prefix: "", delimiter: "/", now: tarde)
        XCTAssertEqual(Set(raiz.prefixes.map { String($0.dropLast()) }.filter(GalleryModel.isCamera)),
                       ["driveway", "garden", "hall"])
        let manifiesto = try JSONDecoder().decode(Manifest.self, from: DemoBucket.object(key: Manifest.key, now: tarde))
        XCTAssertEqual(manifiesto.cameras?.count, 3)
        let hoy = try JSONDecoder().decode(DayIndex.self, from: DemoBucket.object(key: DayIndex.key(tarde), now: tarde))
        XCTAssertFalse(hoy.photos.isEmpty)
        let foto = try XCTUnwrap(hoy.parsed.first)
        XCTAssertGreaterThan(try DemoBucket.object(key: foto.key, now: tarde).count, 10_000)
        XCTAssertLessThan(try DemoBucket.object(key: try XCTUnwrap(foto.thumb), now: tarde).count, 30_000)

        let madrugada = Calendar.current.date(bySettingHour: 0, minute: 1, second: 0, of: Date())!
        let temprano = try? DemoBucket.object(key: DayIndex.key(madrugada), now: madrugada)
        XCTAssertNil(temprano)                                   // at 00:01 there are no photos of today yet
        XCTAssertTrue(StorageConfig.demoConfig.isComplete)
    }
}
