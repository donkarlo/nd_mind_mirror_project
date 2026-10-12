// Source-level TikZ library dependencies required by visual editor generated syntax.

import Foundation

enum TikZSourceDependencyManager {
    static func ensuringRequiredLibraries(
        in source: String
    ) -> String {
        var result = source

        if result.contains("ellipse") || result.contains("regular polygon") {
            result = ensuringLibrary(
                "shapes.geometric",
                in: result
            )
        }

        if result.localizedCaseInsensitiveContains("latex") {
            result = ensuringLibrary(
                "arrows.meta",
                in: result
            )
        }

        return result
    }

    static func ensuringArrowsMeta(
        in source: String
    ) -> String {
        ensuringLibrary(
            "arrows.meta",
            in: source
        )
    }

    static func ensuringShapesGeometric(
        in source: String
    ) -> String {
        ensuringLibrary(
            "shapes.geometric",
            in: source
        )
    }

    private static func ensuringLibrary(
        _ library: String,
        in source: String
    ) -> String {
        let escaped = NSRegularExpression
            .escapedPattern(
                for: library
            )
        let pattern =
            #"\\usetikzlibrary\s*\{[^}]*"# +
            escaped +
            #"[^}]*\}"#

        if source.range(
            of: pattern,
            options: .regularExpression
        ) != nil {
            return source
        }

        let line =
            "\\usetikzlibrary{\(library)}\n"

        guard
            let picture = source.range(
                of: "\\begin{tikzpicture}"
            )
        else {
            return line + source
        }

        var result = source
        result.insert(
            contentsOf: line,
            at: picture.lowerBound
        )
        return result
    }
}
