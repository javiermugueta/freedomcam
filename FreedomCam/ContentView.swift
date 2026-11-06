import SwiftUI

struct ContentView: View {
    @Environment(GalleryModel.self) private var model
    @State private var showSettings = false
    @State private var showCalendar = false
    @State private var showScanner = false
    @State private var viewing: Photo?

    var body: some View {
        NavigationStack {
            ZStack {
                AppBackground()
                VStack(spacing: 0) {
                    TopBar(showCalendar: $showCalendar, showSettings: $showSettings)
                    if model.config.isComplete {
                        gallery
                    } else {
                        WelcomeView(scan: { showScanner = true }, manual: { showSettings = true },
                                    demo: { model.updateConfig(.demoConfig) })
                            .frame(maxHeight: .infinity)
                    }
                }
            }
            .toolbar(.hidden, for: .navigationBar)
            .sheet(isPresented: $showSettings) { SettingsView() }
            .sheet(isPresented: $showCalendar) { CalendarSheet() }
            .sheet(isPresented: $showScanner) { QRScannerView { model.pendingConnection = $0 } }
            .onOpenURL { url in
                if let config = ConnectionCode.parse(url.absoluteString) { model.pendingConnection = config }
            }
            .alert("Connect to this bucket?", isPresented: Binding(
                get: { model.pendingConnection != nil }, set: { if !$0 { model.pendingConnection = nil } }
            ), presenting: model.pendingConnection) { config in
                Button("Connect") {
                    model.updateConfig(config)
                    model.pendingConnection = nil
                }
                Button("Cancel", role: .cancel) { model.pendingConnection = nil }
            } message: { config in
                Text("\(config.provider.title) · \(config.bucket)")
            }
            .fullScreenCover(item: $viewing) { photo in
                PhotoViewer(photos: model.visiblePhotos, start: photo, client: model.client)
            }
        }
        .task(id: model.selectedDay) { await model.reload() }
        .task(id: model.config) { await model.reload() }
        #if DEBUG
        // For screenshots: SIMCTL_CHILD_FC_SCREEN=settings | calendar | viewer, SIMCTL_CHILD_FC_FILTER=people
        .onAppear {
            if ProcessInfo.processInfo.environment["FC_FILTER"] == "people" { model.labelFilter = .personas }
            switch ProcessInfo.processInfo.environment["FC_SCREEN"] {
            case "settings": showSettings = true
            case "calendar": showCalendar = true
            default: break
            }
        }
        .onChange(of: model.photos) { _, fotos in
            if ProcessInfo.processInfo.environment["FC_SCREEN"] == "viewer", viewing == nil {
                let hora = ProcessInfo.processInfo.environment["FC_PHOTO"] ?? ""   // e.g. 14:28
                viewing = fotos.first { $0.time.hasPrefix(hora) && !$0.labels.isEmpty }
            }
        }
        #endif
    }

    /// DEBUG only: App Store screenshots show the gallery as it looks with a real bucket.
    private static var hideDemoBanner: Bool {
        #if DEBUG
        ProcessInfo.processInfo.environment["FC_NOBANNER"] == "1"
        #else
        false
        #endif
    }

    private var gallery: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                if model.config.demo && !Self.hideDemoBanner { DemoBanner() }
                DayHeader()
                DayStrip()
                CameraChips()
                LabelChips()
                PhotoGrid { viewing = $0 }
            }
            .padding(.bottom, 30)
        }
        .refreshable { await model.reload() }
    }
}

// MARK: - Top bar (replaces the navigation bar to save height)

struct TopBar: View {
    @Environment(GalleryModel.self) private var model
    @Binding var showCalendar: Bool
    @Binding var showSettings: Bool

    var body: some View {
        HStack(spacing: 10) {
            Text("freedomCam")
                .font(.title2.weight(.black))
                .foregroundStyle(Theme.gradient)
            Spacer()
            if model.config.isComplete {
                RoundButton(icon: "calendar", label: String(localized: "Choose date")) { showCalendar = true }
            }
            RoundButton(icon: "gearshape.fill", label: String(localized: "Settings")) { showSettings = true }
        }
        .padding(.horizontal)
        .padding(.top, 4)
        .padding(.bottom, 6)
    }
}

struct RoundButton: View {
    let icon: String
    let label: String
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Image(systemName: icon)
                .font(.headline)
                .foregroundStyle(Theme.accent)
                .frame(width: 40, height: 40)
                .background(Circle().fill(.background.opacity(0.85)).shadow(color: .black.opacity(0.08), radius: 3, y: 2))
        }
        .buttonStyle(.plain)
        .accessibilityLabel(label)
    }
}

// MARK: - Day header

struct DayHeader: View {
    @Environment(GalleryModel.self) private var model

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(titulo)
                .font(.title2.weight(.heavy))
                .lineLimit(1)
                .minimumScaleFactor(0.7)
            Text(subtitulo).font(.subheadline.weight(.medium)).foregroundStyle(.secondary)
        }
        .padding(.horizontal)
    }

    /// "Tuesday, November 3" / "Martes, 3 de noviembre"
    private var titulo: String {
        let texto = model.selectedDay.formatted(.dateTime.weekday(.wide).day().month(.wide))
        return texto.prefix(1).uppercased() + texto.dropFirst()
    }

    private var subtitulo: String {
        if model.loading && model.photos.isEmpty { return String(localized: "Looking for photos…") }
        let n = model.photos.count
        let personas = model.photos.filter { $0.labels.contains("person") }.count
        let cal = Calendar.current
        var partes: [String] = []
        if cal.isDateInToday(model.selectedDay) { partes.append(String(localized: "Today ☀️")) }
        if cal.isDateInYesterday(model.selectedDay) { partes.append(String(localized: "Yesterday 🌙")) }
        partes.append(n == 0 ? String(localized: "no photos") : String(localized: "\(n) photos"))
        if personas > 0 { partes.append(String(localized: "\(personas) with people 🧍")) }
        return partes.joined(separator: " · ")
    }
}

// MARK: - Day strip

struct DayStrip: View {
    @Environment(GalleryModel.self) private var model

    /// The week of the selected day (first weekday as in the iPhone's region).
    private var semana: [Date] {
        let cal = Calendar.current
        guard let lunes = cal.dateInterval(of: .weekOfYear, for: model.selectedDay)?.start else { return [] }
        return (0..<7).compactMap { cal.date(byAdding: .day, value: $0, to: lunes) }
    }

    var body: some View {
        let hoy = Calendar.current.startOfDay(for: Date())
        HStack(spacing: 6) {
            ForEach(semana, id: \.self) { dia in
                let futuro = dia > hoy
                DayPill(day: dia, selected: Calendar.current.isDate(dia, inSameDayAs: model.selectedDay),
                        hasPhotos: model.daysWithPhotos.contains(dia.dayKey))
                    .opacity(futuro ? 0.35 : 1)
                    .onTapGesture {
                        guard !futuro else { return }
                        withAnimation(.spring(duration: 0.3)) { model.selectedDay = dia }
                    }
                    .accessibilityAddTraits(futuro ? [] : .isButton)
            }
        }
        .padding(.horizontal)
        .padding(.vertical, 6)
        .task(id: "\(model.cameras)\(model.selectedDay.monthPath)") {
            // a week can span two months
            for dia in [semana.first, semana.last].compactMap({ $0 }) { await model.loadMonth(of: dia) }
        }
    }
}

struct DayPill: View {
    let day: Date
    let selected: Bool
    let hasPhotos: Bool

    var body: some View {
        VStack(spacing: 4) {
            Text(day.formatted(.dateTime.weekday(.abbreviated)).uppercased())
                .font(.caption2.weight(.bold))
            Text(day.formatted(.dateTime.day()))
                .font(.title3.weight(.heavy))
            Circle()
                .fill(hasPhotos ? (selected ? Color.white : Theme.accent) : .clear)
                .frame(width: 6, height: 6)
        }
        .frame(maxWidth: .infinity)
        .frame(height: 76)
        .foregroundStyle(selected ? .white : .primary)
        .background {
            RoundedRectangle(cornerRadius: 18, style: .continuous)
                .fill(selected ? AnyShapeStyle(Theme.gradient) : AnyShapeStyle(.background.opacity(0.8)))
                .shadow(color: selected ? Theme.accent.opacity(0.4) : .black.opacity(0.06), radius: selected ? 8 : 3, y: 3)
        }
        .scaleEffect(selected ? 1.06 : 1)
        .accessibilityElement(children: .combine)
        .accessibilityAddTraits(selected ? .isSelected : [])
    }
}

// MARK: - Filters

struct CameraChips: View {
    @Environment(GalleryModel.self) private var model

    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                Chip(text: String(localized: "📷 All"), count: model.countFor(camera: nil), selected: model.selectedCamera == nil) {
                    model.selectedCamera = nil
                }
                ForEach(model.cameras, id: \.self) { cam in
                    Chip(text: "\(model.emoji(of: cam)) \(model.name(of: cam))", count: model.countFor(camera: cam),
                         selected: model.selectedCamera == cam) {
                        model.selectedCamera = model.selectedCamera == cam ? nil : cam
                    }
                }
            }
            .padding(.horizontal)
        }
    }
}

struct LabelChips: View {
    @Environment(GalleryModel.self) private var model

    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(LabelFilter.allCases) { filtro in
                    Chip(text: filtro.title, count: nil, selected: model.labelFilter == filtro, small: true) {
                        model.labelFilter = filtro
                    }
                }
            }
            .padding(.horizontal)
        }
    }
}

struct Chip: View {
    let text: String
    let count: Int?
    let selected: Bool
    var small = false
    let action: () -> Void

    var body: some View {
        Button {
            withAnimation(.snappy) { action() }
        } label: {
            HStack(spacing: 6) {
                Text(text)
                if let count, count > 0 {
                    Text("\(count)")
                        .font(.caption.weight(.heavy))
                        .padding(.horizontal, 6).padding(.vertical, 1)
                        .background(Capsule().fill(selected ? .white.opacity(0.3) : Theme.accent.opacity(0.15)))
                }
            }
            .font((small ? Font.subheadline : .body).weight(.semibold))
            .padding(.horizontal, small ? 12 : 14)
            .padding(.vertical, small ? 7 : 9)
            .foregroundStyle(selected ? .white : .primary)
            .background {
                Capsule().fill(selected ? AnyShapeStyle(Theme.gradient) : AnyShapeStyle(.background.opacity(0.8)))
                    .shadow(color: .black.opacity(selected ? 0.12 : 0.05), radius: 3, y: 2)
            }
        }
        .buttonStyle(.plain)
        .accessibilityAddTraits(selected ? .isSelected : [])
    }
}

// MARK: - Calendar

struct CalendarSheet: View {
    @Environment(GalleryModel.self) private var model
    @Environment(\.dismiss) private var dismiss
    @State private var dia = Date()

    var body: some View {
        NavigationStack {
            DatePicker("Day", selection: $dia, in: ...Date(), displayedComponents: .date)
                .datePickerStyle(.graphical)
                .padding()
                .navigationTitle("Which day? 🗓️")
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .cancellationAction) { Button("Close") { dismiss() } }
                    ToolbarItem(placement: .confirmationAction) {
                        Button("Show") {
                            model.selectedDay = Calendar.current.startOfDay(for: dia)
                            dismiss()
                        }.bold()
                    }
                }
        }
        .presentationDetents([.medium, .large])
        .onAppear { dia = model.selectedDay }
    }
}

// MARK: - Welcome

struct WelcomeView: View {
    let scan: () -> Void
    let manual: () -> Void
    let demo: () -> Void

    var body: some View {
        VStack(spacing: 18) {
            Text("📸").font(.system(size: 90))
            Text("Hi there!").font(.largeTitle.weight(.heavy))
            Text("Here you will see the photos your cameras save when something happens. First tell me where they are.")
                .multilineTextAlignment(.center)
                .foregroundStyle(.secondary)
                .padding(.horizontal, 30)
            Button(action: scan) {
                Label("Scan the code from Home Assistant", systemImage: "qrcode.viewfinder")
                    .font(.headline)
                    .padding(.horizontal, 24).padding(.vertical, 14)
                    .foregroundStyle(.white)
                    .background(Capsule().fill(Theme.gradient))
                    .shadow(color: Theme.accent.opacity(0.4), radius: 10, y: 5)
            }
            .buttonStyle(.plain)
            Button("Enter it manually", action: manual)
                .font(.subheadline.weight(.semibold))
            Button(action: demo) {
                Label("Try the demo", systemImage: "play.circle")
            }
            .font(.subheadline.weight(.semibold))
            .foregroundStyle(.secondary)
            .padding(.top, 6)
        }
        .padding()
    }
}

// MARK: - Demo

struct DemoBanner: View {
    @Environment(GalleryModel.self) private var model

    var body: some View {
        HStack(spacing: 10) {
            Text("🎬").font(.title3)
            VStack(alignment: .leading, spacing: 1) {
                Text("Demo mode").font(.subheadline.weight(.heavy))
                Text("Made-up photos. Connect your bucket to see yours.").font(.caption).foregroundStyle(.secondary)
            }
            Spacer(minLength: 4)
            Button("Exit") { model.updateConfig(StorageConfig()) }
                .font(.subheadline.weight(.bold))
                .buttonStyle(.borderedProminent)
                .buttonBorderShape(.capsule)
                .controlSize(.small)
        }
        .padding(.horizontal, 14).padding(.vertical, 10)
        .background(RoundedRectangle(cornerRadius: 16, style: .continuous).fill(.background.opacity(0.85)))
        .padding(.horizontal)
    }
}
