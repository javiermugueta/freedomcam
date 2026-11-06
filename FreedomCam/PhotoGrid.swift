import SwiftUI

struct PhotoGrid: View {
    @Environment(GalleryModel.self) private var model
    let open: (Photo) -> Void

    private let columnas = [GridItem(.adaptive(minimum: 160), spacing: 12)]

    var body: some View {
        Group {
            if let error = model.error {
                EmptyState(emoji: "🙈", title: String(localized: "Oops…"), text: error)
            } else if model.loading && model.photos.isEmpty {
                ProgressView().controlSize(.large).frame(maxWidth: .infinity).padding(.top, 60)
            } else if model.visiblePhotos.isEmpty {
                if model.photos.isEmpty {
                    EmptyState(emoji: "🦗", title: String(localized: "Quiet day"), text: String(localized: "No camera saw anything this day."))
                } else {
                    EmptyState(emoji: "🔍", title: String(localized: "Nothing with that filter"), text: String(localized: "Try another camera or filter."))
                }
            } else {
                LazyVGrid(columns: columnas, spacing: 12) {
                    ForEach(model.visiblePhotos) { foto in
                        PhotoCard(photo: foto, client: model.client)
                            .onTapGesture { open(foto) }
                    }
                }
                .padding(.horizontal)
            }
        }
        .animation(.snappy, value: model.visiblePhotos)
    }
}

struct PhotoCard: View {
    let photo: Photo
    let client: S3Client
    @Environment(GalleryModel.self) private var model
    @State private var image: UIImage?
    @State private var failed = false

    var body: some View {
        Color.clear
            .aspectRatio(16 / 9, contentMode: .fit)
            .overlay {
                if let image {
                    Image(uiImage: image).resizable().scaledToFill()
                        .transition(.opacity)
                } else if failed {
                    Text("💥").font(.largeTitle)
                } else {
                    ProgressView()
                }
            }
            .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
            .overlay(alignment: .bottomLeading) {
                Text(photo.time.prefix(5))
                    .font(.caption.weight(.heavy))
                    .padding(.horizontal, 8).padding(.vertical, 4)
                    .background(.ultraThinMaterial, in: Capsule())
                    .padding(8)
            }
            .overlay(alignment: .topTrailing) {
                if !photo.labels.isEmpty {
                    Text(photo.labels.map(Pretty.labelEmoji).joined())
                        .font(.callout)
                        .padding(.horizontal, 7).padding(.vertical, 3)
                        .background(.ultraThinMaterial, in: Capsule())
                        .padding(8)
                }
            }
            .overlay(alignment: .topLeading) {
                Text(model.emoji(of: photo.camera))
                    .font(.callout)
                    .padding(6)
                    .background(.ultraThinMaterial, in: Circle())
                    .padding(8)
            }
            .background(RoundedRectangle(cornerRadius: 18, style: .continuous).fill(.background.opacity(0.8)))
            .shadow(color: .black.opacity(0.1), radius: 6, y: 4)
            .contentShape(Rectangle())
            .accessibilityElement()
            .accessibilityLabel("\(model.name(of: photo.camera)), \(photo.time)" +
                                (photo.labels.isEmpty ? "" : ", " + photo.labels.map(Pretty.labelName).joined(separator: ", ")))
            .accessibilityAddTraits(.isButton)
            .task(id: photo.key) {
                do {
                    let img = try await ImageCache.shared.thumbnail(photo.thumb ?? photo.key, client: client)
                    withAnimation(.easeOut(duration: 0.2)) { image = img }
                } catch {
                    failed = true
                }
            }
    }
}

struct EmptyState: View {
    let emoji: String
    let title: String
    let text: String

    var body: some View {
        VStack(spacing: 8) {
            Text(emoji).font(.system(size: 64))
            Text(title).font(.title2.weight(.heavy))
            Text(text).multilineTextAlignment(.center).foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.top, 50)
        .padding(.horizontal, 30)
    }
}
