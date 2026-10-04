package com.ndmindmirror.android.latex.compiler

import com.ndmindmirror.android.AndroidWorkspaceService
import java.io.File

/**
 * Builds the minimal local dependency tree required by Tectonic.
 *
 * Project paths are rewritten to a private compile workspace because the native
 * engine cannot read Android Storage Access Framework URIs directly.
 */
class LatexCompileWorkspaceBuilder(
    private val workspace: AndroidWorkspaceService,
    private val runtimeDirectory: File,
) {
    fun prepare(sourcePath: String, source: String): LatexCompileWorkspace {
        runtimeDirectory.mkdirs()
        clearPreviousOutputs()

        val workspaceDirectory = File(runtimeDirectory, WORKSPACE_DIRECTORY_NAME)
        if (workspaceDirectory.exists()) {
            workspaceDirectory.deleteRecursively()
        }
        workspaceDirectory.mkdirs()

        val visited = mutableSetOf<String>()
        val transformedSource = transformText(sourcePath, source, visited)
        return LatexCompileWorkspace(
            jobDirectory = runtimeDirectory,
            sourcePath = sourcePath,
            transformedSource = transformedSource,
        )
    }

    private fun clearPreviousOutputs() {
        OUTPUT_FILE_NAMES.forEach { name ->
            File(runtimeDirectory, name).delete()
        }
    }

    private fun transformText(
        currentPath: String,
        source: String,
        visited: MutableSet<String>,
    ): String {
        var transformed = source

        transformed = replaceSinglePathCommand(
            transformed,
            currentPath,
            INPUT_PATTERN,
            setOf("tex", "ltx", "tikz"),
            visited,
        ) { command, localPath -> "\\$command{$localPath}" }

        transformed = replaceGraphics(transformed, currentPath, visited)
        transformed = replaceBibliography(transformed, currentPath, visited)
        transformed = replaceAddBibResource(transformed, currentPath, visited)
        transformed = replaceListing(transformed, currentPath, visited)
        transformed = replaceInputMinted(transformed, currentPath, visited)
        transformed = replaceCustomPackages(transformed, currentPath, visited)
        transformed = replaceCustomDocumentClass(transformed, currentPath, visited)
        transformed = replaceBibliographyStyle(transformed, currentPath, visited)

        return transformed
    }

    private fun replaceGraphics(
        source: String,
        currentPath: String,
        visited: MutableSet<String>,
    ): String {
        return GRAPHICS_PATTERN.replace(source) { match ->
            val options = match.groups[1]?.value.orEmpty()
            val rawPath = match.groups[2]?.value.orEmpty()
            val resolved = resolveExisting(
                currentPath,
                rawPath,
                GRAPHIC_EXTENSIONS,
            ) ?: return@replace match.value

            materialize(resolved, visited)
            val optionPart = if (options.isBlank()) "" else "[$options]"
            "\\includegraphics$optionPart{${localReference(resolved)}}"
        }
    }

    private fun replaceBibliography(
        source: String,
        currentPath: String,
        visited: MutableSet<String>,
    ): String {
        return BIBLIOGRAPHY_PATTERN.replace(source) { match ->
            val values = match.groups[1]?.value
                ?.split(',')
                ?.map { it.trim() }
                ?.filter { it.isNotBlank() }
                .orEmpty()
            if (values.isEmpty()) return@replace match.value

            val resolvedValues = values.map { raw ->
                val resolved = resolveExisting(currentPath, raw, setOf("bib"))
                    ?: return@map raw
                materialize(resolved, visited)
                localReference(resolved).removeSuffix(".bib")
            }
            "\\bibliography{${resolvedValues.joinToString(",")}}"
        }
    }

    private fun replaceAddBibResource(
        source: String,
        currentPath: String,
        visited: MutableSet<String>,
    ): String {
        return ADD_BIB_RESOURCE_PATTERN.replace(source) { match ->
            val options = match.groups[1]?.value.orEmpty()
            val rawPath = match.groups[2]?.value.orEmpty()
            val resolved = resolveExisting(currentPath, rawPath, setOf("bib"))
                ?: return@replace match.value

            materialize(resolved, visited)
            val optionPart = if (options.isBlank()) "" else "[$options]"
            "\\addbibresource$optionPart{${localReference(resolved)}}"
        }
    }

    private fun replaceListing(
        source: String,
        currentPath: String,
        visited: MutableSet<String>,
    ): String {
        return LISTING_PATTERN.replace(source) { match ->
            val options = match.groups[1]?.value.orEmpty()
            val rawPath = match.groups[2]?.value.orEmpty()
            val resolved = resolveExisting(currentPath, rawPath, emptySet())
                ?: return@replace match.value

            materialize(resolved, visited)
            val optionPart = if (options.isBlank()) "" else "[$options]"
            "\\lstinputlisting$optionPart{${localReference(resolved)}}"
        }
    }

    private fun replaceInputMinted(
        source: String,
        currentPath: String,
        visited: MutableSet<String>,
    ): String {
        return INPUT_MINTED_PATTERN.replace(source) { match ->
            val options = match.groups[1]?.value.orEmpty()
            val language = match.groups[2]?.value.orEmpty()
            val rawPath = match.groups[3]?.value.orEmpty()
            val resolved = resolveExisting(currentPath, rawPath, emptySet())
                ?: return@replace match.value

            materialize(resolved, visited)
            val optionPart = if (options.isBlank()) "" else "[$options]"
            "\\inputminted$optionPart{$language}{${localReference(resolved)}}"
        }
    }

    private fun replaceCustomPackages(
        source: String,
        currentPath: String,
        visited: MutableSet<String>,
    ): String {
        return USE_PACKAGE_PATTERN.replace(source) { match ->
            val options = match.groups[1]?.value.orEmpty()
            val packageNames = match.groups[2]?.value
                ?.split(',')
                ?.map { it.trim() }
                ?.filter { it.isNotBlank() }
                .orEmpty()
            if (packageNames.isEmpty()) return@replace match.value

            var changed = false
            val rewritten = packageNames.map { packageName ->
                val resolved = resolveExisting(currentPath, packageName, setOf("sty"))
                    ?: return@map packageName
                changed = true
                materialize(resolved, visited)
                localReference(resolved).removeSuffix(".sty")
            }
            if (!changed) return@replace match.value

            val optionPart = if (options.isBlank()) "" else "[$options]"
            "\\usepackage$optionPart{${rewritten.joinToString(",")}}"
        }
    }

    private fun replaceCustomDocumentClass(
        source: String,
        currentPath: String,
        visited: MutableSet<String>,
    ): String {
        return DOCUMENT_CLASS_PATTERN.replace(source) { match ->
            val options = match.groups[1]?.value.orEmpty()
            val className = match.groups[2]?.value.orEmpty().trim()
            val resolved = resolveExisting(currentPath, className, setOf("cls"))
                ?: return@replace match.value

            materialize(resolved, visited)
            val optionPart = if (options.isBlank()) "" else "[$options]"
            "\\documentclass$optionPart{${localReference(resolved).removeSuffix(".cls")}}"
        }
    }

    private fun replaceBibliographyStyle(
        source: String,
        currentPath: String,
        visited: MutableSet<String>,
    ): String {
        return BIBLIOGRAPHY_STYLE_PATTERN.replace(source) { match ->
            val rawPath = match.groups[1]?.value.orEmpty().trim()
            val resolved = resolveExisting(currentPath, rawPath, setOf("bst"))
                ?: return@replace match.value

            materialize(resolved, visited)
            "\\bibliographystyle{${localReference(resolved).removeSuffix(".bst")}}"
        }
    }

    private fun replaceSinglePathCommand(
        source: String,
        currentPath: String,
        pattern: Regex,
        extensions: Set<String>,
        visited: MutableSet<String>,
        replacement: (String, String) -> String,
    ): String {
        return pattern.replace(source) { match ->
            val command = match.groups[1]?.value.orEmpty()
            val rawPath = match.groups[2]?.value.orEmpty()
            val resolved = resolveExisting(currentPath, rawPath, extensions)
                ?: return@replace match.value

            materialize(resolved, visited)
            replacement(command, localReference(resolved))
        }
    }

    private fun materialize(
        relativePath: String,
        visited: MutableSet<String>,
    ) {
        if (!visited.add(relativePath)) return

        val target = targetFile(relativePath)
        target.parentFile?.mkdirs()

        val suffix = relativePath.substringAfterLast('.', "").lowercase()
        if (suffix in TRANSFORMED_TEXT_EXTENSIONS) {
            val source = workspace.readTextContent(relativePath)
            target.writeText(transformText(relativePath, source, visited))
            return
        }

        workspace.inputStream(relativePath).use { input ->
            target.outputStream().use { output ->
                input.copyTo(output)
            }
        }
    }

    private fun targetFile(relativePath: String): File {
        val root = File(runtimeDirectory, WORKSPACE_DIRECTORY_NAME).canonicalFile
        val target = File(root, relativePath).canonicalFile
        require(
            target.path == root.path ||
                target.path.startsWith(root.path + File.separator)
        ) {
            "Compile dependency escaped the private workspace."
        }
        return target
    }

    private fun localReference(relativePath: String): String {
        return "$WORKSPACE_DIRECTORY_NAME/$relativePath"
    }

    private fun resolveExisting(
        currentPath: String,
        rawPath: String,
        extensions: Set<String>,
    ): String? {
        val normalizedRaw = rawPath.trim()
        if (
            normalizedRaw.isBlank() ||
            normalizedRaw.startsWith("\\") ||
            "://" in normalizedRaw
        ) {
            return null
        }

        val basePath = if (normalizedRaw.startsWith('/')) {
            workspaceRelativeAbsolutePath(normalizedRaw)
        } else {
            normalizeRelative(
                currentPath.substringBeforeLast('/', ""),
                normalizedRaw,
            )
        } ?: return null

        val fileName = basePath.substringAfterLast('/')
        val suffix = fileName.substringAfterLast('.', "")
        val candidates = if (extensions.isEmpty() || suffix.isNotBlank()) {
            listOf(basePath)
        } else {
            listOf(basePath) + extensions.map { extension -> "$basePath.$extension" }
        }

        return candidates.firstOrNull { workspace.fileExists(it) }
    }

    private fun workspaceRelativeAbsolutePath(path: String): String? {
        val normalized = path.replace('\\', '/')
        val marker = "/repo/"
        val markerIndex = normalized.indexOf(marker)
        if (markerIndex < 0) return null
        return normalizeRelative("", normalized.substring(markerIndex + marker.length))
    }

    private fun normalizeRelative(parent: String, child: String): String? {
        val parts = mutableListOf<String>()
        val combined = if (parent.isBlank()) child else "$parent/$child"

        for (part in combined.replace('\\', '/').split('/')) {
            when {
                part.isBlank() || part == "." -> Unit
                part == ".." -> {
                    if (parts.isEmpty()) return null
                    parts.removeAt(parts.lastIndex)
                }
                else -> parts += part
            }
        }
        return parts.joinToString("/")
    }

    private companion object {
        const val WORKSPACE_DIRECTORY_NAME = "workspace"

        val OUTPUT_FILE_NAMES = setOf(
            "document.pdf",
            "document.log",
            "document.synctex.gz",
            "document.aux",
            "document.bbl",
            "document.blg",
            "document.toc",
            "document.out",
        )

        val TRANSFORMED_TEXT_EXTENSIONS = setOf(
            "tex",
            "ltx",
            "tikz",
            "sty",
            "cls",
            "bib",
            "bst",
            "def",
            "cfg",
            "txt",
            "csv",
            "py",
            "md",
        )

        val GRAPHIC_EXTENSIONS = setOf(
            "pdf",
            "png",
            "jpg",
            "jpeg",
            "webp",
            "bmp",
            "eps",
        )

        val INPUT_PATTERN = Regex(
            """\\(input|include)\s*\{([^{}]+)\}"""
        )
        val GRAPHICS_PATTERN = Regex(
            """\\includegraphics\s*(?:\[([^\]]*)\])?\s*\{([^{}]+)\}"""
        )
        val BIBLIOGRAPHY_PATTERN = Regex(
            """\\bibliography\s*\{([^{}]+)\}"""
        )
        val ADD_BIB_RESOURCE_PATTERN = Regex(
            """\\addbibresource\s*(?:\[([^\]]*)\])?\s*\{([^{}]+)\}"""
        )
        val LISTING_PATTERN = Regex(
            """\\lstinputlisting\s*(?:\[([^\]]*)\])?\s*\{([^{}]+)\}"""
        )
        val INPUT_MINTED_PATTERN = Regex(
            """\\inputminted\s*(?:\[([^\]]*)\])?\s*\{([^{}]+)\}\s*\{([^{}]+)\}"""
        )
        val USE_PACKAGE_PATTERN = Regex(
            """\\usepackage\s*(?:\[([^\]]*)\])?\s*\{([^{}]+)\}"""
        )
        val DOCUMENT_CLASS_PATTERN = Regex(
            """\\documentclass\s*(?:\[([^\]]*)\])?\s*\{([^{}]+)\}"""
        )
        val BIBLIOGRAPHY_STYLE_PATTERN = Regex(
            """\\bibliographystyle\s*\{([^{}]+)\}"""
        )
    }
}
