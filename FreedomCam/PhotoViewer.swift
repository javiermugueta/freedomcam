import SwiftUI

/// Full-screen photo; swipe sideways to go to the next one.
struct PhotoViewer: View {
    let photos: [Photo]
    let client: S3Client
    @Environment(GalleryModel.self) private var model
    @State private var current: String
    @Environment(\.dismiss) private var dismiss

    init(photos: [Photo], start: Photo, client: S3Client) {
        self.photos = photos
        self.client = client
        _current = State(initialValue: start.key)
    }

    private var photo: Photo? { photos.first { $0.key == current } }

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()
            TabView(selection: $current) {
                ForEach(photos) { foto in
                    FullPhoto(photo: foto, client: client).tag(foto.key)
                }
            }
            .tabViewStyle(.page(indexDisplayMode: .never))
            .ignoresSafeArea()
        }
        .overlay(alignment: .top) { barra }
        .overlay(alignment: .bottom) { pie }
        .statusBarHidden()
    }

    private var barra: some View {
        HStack {
            Button { dismiss() } label: {
                Image(systemName: "xmark").font(.headline.weight(.bold)).frame(width: 44, height: 44)
                    .background(.ultraThinMaterial, in: Circle())
            }
            .accessibilityLabel(String(localized: "Close"))
            Spacer()
            if let photo { ShareButton(photo: photo, title: model.name(of: photo.camera), client: client) }
        }
        .foregroundStyle(.white)
        .padding(.horizontal)
    }

    @ViewBuilder private var pie: some View {
        if let photo {
            VStack(spacing: 4) {
                Text("\(model.emoji(of: photo.camera)) \(model.name(of: photo.camera))")
                    .font(.headline.weight(.heavy))
                Text(photo.time + (photo.labels.isEmpty ? "" : "  ·  " + photo.labels.map {
                    "\(Pretty.labelEmoji($0)) \(Pretty.labelName($0))"
                }.joined(separator: "  ")))
                .font(.subheadline.weight(.semibold))
                if let i = photos.firstIndex(of: photo) {
                    Text("\(i + 1) of \(photos.count)").font(.caption).opacity(0.7)
                }
            }
            .foregroundStyle(.white)
            .padding(.horizontal, 18).padding(.vertical, 10)
            .background(.ultraThinMaterial.opacity(0.9), in: RoundedRectangle(cornerRadius: 20, style: .continuous))
            .padding(.bottom, 20)
        }
    }
}

struct FullPhoto: View {
    let photo: Photo
    let client: S3Client
    @State private var image: UIImage?
    @State private var zoom: CGFloat = 1
    @GestureState private var pinch: CGFloat = 1

    var body: some View {
        Group {
            if let image {
                Image(uiImage: image).resizable().scaledToFit()
                    .scaleEffect(zoom * pinch)
                    .gesture(MagnifyGesture()
                        .updating($pinch) { valor, estado, _ in estado = valor.magnification }
                        .onEnded { valor in zoom = min(max(zoom * valor.magnification, 1), 5) })
                    .onTapGesture(count: 2) { withAnimation(.spring) { zoom = zoom > 1 ? 1 : 2.5 } }
            } else {
                ProgressView().tint(.white).controlSize(.large)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .task(id: photo.key) { image = try? await ImageCache.shared.full(photo.key, client: client) }
    }
}

struct ShareButton: View {
    let photo: Photo
    let title: String
    let client: S3Client
    @State private var image: UIImage?

    var body: some View {
        // ZStack with a placeholder: an empty Group would never run the .task that loads the image
        ZStack {
            Color.clear.frame(width: 44, height: 44)
            if let image {
                ShareLink(item: Image(uiImage: image),
                          preview: SharePreview("\(title) \(photo.day) \(photo.time)",
                                                image: Image(uiImage: image))) {
                    Image(systemName: "square.and.arrow.up").font(.headline.weight(.bold)).frame(width: 44, height: 44)
                        .background(.ultraThinMaterial, in: Circle())
                }
                .accessibilityLabel(String(localized: "Share"))
            }
        }
        .task(id: photo.key) { image = try? await ImageCache.shared.full(photo.key, client: client) }
    }
}
