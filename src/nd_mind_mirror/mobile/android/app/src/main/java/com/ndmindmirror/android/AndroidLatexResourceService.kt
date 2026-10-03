package com.ndmindmirror.android

import android.util.Base64
import org.json.JSONObject

/**
 * Resolves LaTeX graphics inside the active Android workspace and exposes them
 * as local data URLs for Source and Visual projections.
 */
class AndroidLatexResourceService(
    private val workspace: AndroidWorkspaceService,
    private val pdfPreview: PdfPreviewService,
) {
    fun graphic(sourcePath: String, rawPath: String): JSONObject {
        val resolvedPath = resolveGraphicPath(sourcePath, rawPath)
            ?: return JSONObject()
                .put("available", false)
                .put("requested_path", rawPath)

        val suffix = resolvedPath.substringAfterLast('.', "").lowercase()
        val dataUrl = if (suffix == "pdf") {
            pdfPreview.pageDataUrlForPdfPath(resolvedPath, 1)
        } else {
            val bytes = workspace.inputStream(resolvedPath).use { input ->
                input.readBytes(MAX_RESOURCE_BYTES + 1)
            }
            require(bytes.size <= MAX_RESOURCE_BYTES) {
                "Graphic is too large for Android inline preview."
            }
            val mime = mimeType(suffix)
            "data:$mime;base64," + Base64.encodeToString(bytes, Base64.NO_WRAP)
        }

        return JSONObject()
            .put("available", true)
            .put("path", resolvedPath)
            .put("data_url", dataUrl)
            .put("suffix", suffix)
    }

    private fun resolveGraphicPath(sourcePath: String, rawPath: String): String? {
        val raw = rawPath.trim()
        if (raw.isBlank() || raw.startsWith("\\") || "://" in raw) return null

        val baseCandidate = when {
            raw.startsWith("/") -> workspaceRelativeAbsolutePath(raw) ?: return null
            else -> joinRelative(sourceDirectory(sourcePath), raw) ?: return null
        }

        val fileName = baseCandidate.substringAfterLast('/', "")
        val suffix = fileName.substringAfterLast('.', "").lowercase()
        val candidates = when {
            !fileName.contains('.') -> {
                GRAPHIC_SUFFIXES.map { graphicSuffix -> "$baseCandidate.$graphicSuffix" }
            }
            suffix in LATEX_SOURCE_SUFFIXES -> {
                val stem = baseCandidate.substringBeforeLast('.')
                GRAPHIC_SUFFIXES.map { graphicSuffix -> "$stem.$graphicSuffix" }
            }
            else -> listOf(baseCandidate)
        }

        return candidates.firstOrNull { candidate ->
            workspace.fileExists(candidate)
        }
    }

    private fun workspaceRelativeAbsolutePath(path: String): String? {
        val normalized = path.replace('\\', '/')
        val marker = "/repo/"
        val index = normalized.indexOf(marker)
        if (index < 0) return null
        return normalizeWithinRoot(normalized.substring(index + marker.length))
    }

    private fun sourceDirectory(path: String): String {
        return path.replace('\\', '/').substringBeforeLast('/', "")
    }

    private fun joinRelative(directory: String, rawPath: String): String? {
        val combined = if (directory.isBlank()) rawPath else "$directory/$rawPath"
        return normalizeWithinRoot(combined)
    }

    private fun normalizeWithinRoot(path: String): String? {
        val stack = mutableListOf<String>()
        for (part in path.replace('\\', '/').split('/')) {
            when {
                part.isBlank() || part == "." -> Unit
                part == ".." -> {
                    if (stack.isEmpty()) return null
                    stack.removeAt(stack.lastIndex)
                }
                else -> stack += part
            }
        }
        return stack.joinToString("/")
    }

    private fun mimeType(suffix: String): String {
        return when (suffix) {
            "png" -> "image/png"
            "jpg", "jpeg" -> "image/jpeg"
            "webp" -> "image/webp"
            "gif" -> "image/gif"
            "bmp" -> "image/bmp"
            "svg" -> "image/svg+xml"
            else -> "application/octet-stream"
        }
    }

    private companion object {
        val GRAPHIC_SUFFIXES = listOf(
            "png",
            "jpg",
            "jpeg",
            "webp",
            "gif",
            "bmp",
            "svg",
            "pdf",
        )
        val LATEX_SOURCE_SUFFIXES = setOf("tex", "ltx", "tikz")
        const val MAX_RESOURCE_BYTES = 20 * 1024 * 1024
    }
}
