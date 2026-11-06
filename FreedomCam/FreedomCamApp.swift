import SwiftUI

@main
struct FreedomCamApp: App {
    @State private var model = GalleryModel()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environment(model)
                .fontDesign(.rounded)
                .tint(Theme.accent)
        }
    }
}

enum Theme {
    static let accent = Color(red: 1.0, green: 0.42, blue: 0.33)          // coral
    static let accent2 = Color(red: 1.0, green: 0.72, blue: 0.25)         // mango
    static let gradient = LinearGradient(colors: [accent, accent2], startPoint: .topLeading, endPoint: .bottomTrailing)
    static let background = LinearGradient(
        colors: [Color(red: 1.0, green: 0.96, blue: 0.9), Color(red: 0.93, green: 0.95, blue: 1.0)],
        startPoint: .top, endPoint: .bottom)
    static let backgroundDark = LinearGradient(
        colors: [Color(red: 0.12, green: 0.1, blue: 0.14), Color(red: 0.07, green: 0.08, blue: 0.13)],
        startPoint: .top, endPoint: .bottom)
}

struct AppBackground: View {
    @Environment(\.colorScheme) private var scheme

    var body: some View {
        (scheme == .dark ? Theme.backgroundDark : Theme.background).ignoresSafeArea()
    }
}
