// User-selectable directions for automatic TikZ graph layout.

enum TikZAutoLayoutDirection: String, CaseIterable, Identifiable {
    case topToBottom
    case bottomToTop
    case leftToRight
    case rightToLeft
    case rightTree
    case leftTree

    var id: String { rawValue }

    var title: String {
        switch self {
        case .topToBottom: return "Top to Bottom"
        case .bottomToTop: return "Bottom to Top"
        case .leftToRight: return "Left to Right"
        case .rightToLeft: return "Right to Left"
        case .rightTree: return "Right Tree"
        case .leftTree: return "Left Tree"
        }
    }
}
