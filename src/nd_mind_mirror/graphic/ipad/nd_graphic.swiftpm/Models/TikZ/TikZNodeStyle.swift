// Editable appearance of one TikZ node.

struct TikZNodeStyle: Hashable, Codable {
    var fillColor: TikZColorValue = .white
    var strokeColor: TikZColorValue = .black
    var textColor: TikZColorValue = .black
    var lineWidth: Double = 1.0
}
