// Editable appearance of one TikZ connector and its label.

struct TikZEdgeStyle: Hashable, Codable {
    var strokeColor: TikZColorValue = .black
    var textColor: TikZColorValue = .black
    var lineWidth: Double = 1.0
    var directed: Bool = true
    var linePattern: TikZLinePattern = .solid
    var arrowHeadStyle: TikZArrowHeadStyle = .filled
}
