package com.ndmindmirror.android

import android.content.Context
import android.net.Uri
import android.provider.DocumentsContract
import org.json.JSONArray
import org.json.JSONObject
import java.io.FileNotFoundException
import java.io.InputStream

/**
 * Reads and writes the user-selected Android document tree without requiring Ubuntu.
 */
class AndroidWorkspaceService(
    private val context: Context,
    private val preferences: WorkspacePreferenceStore,
) {
    private val resolver
        get() = context.contentResolver

    private val ignoredDirectoryNames = setOf(
        ".git",
        ".gradle",
        "__pycache__",
        "build",
        "node_modules",
    )

    private val textSuffixes = setOf(
        "tex", "ltx", "tikz", "txt", "md", "yaml", "yml", "json", "py", "kt", "java",
        "c", "cc", "cpp", "h", "hpp", "sh", "xml", "html", "css", "js", "ts", "csv",
        "bib", "sty", "cls", "ini", "toml",
    )

    fun hasWorkspace(): Boolean = preferences.rootUri() != null

    fun workspaceInfo(): JSONObject {
        val active = preferences.activeLocation()
        return workspaceLocationInfo(active)
            .put("active_location", active.key)
    }

    fun workspaceSettings(): JSONObject {
        val active = preferences.activeLocation()
        return JSONObject()
            .put("active_location", active.key)
            .put("local", workspaceLocationInfo(WorkspaceLocation.LOCAL))
            .put("dropbox", workspaceLocationInfo(WorkspaceLocation.DROPBOX))
    }

    private fun workspaceLocationInfo(location: WorkspaceLocation): JSONObject {
        val root = preferences.rootUri(location)
            ?: return JSONObject()
                .put("configured", false)
                .put("location", location.key)

        val documentUri = rootDocumentUri(root)
        return JSONObject()
            .put("configured", true)
            .put("location", location.key)
            .put("name", documentName(documentUri).ifBlank { "Selected folder" })
            .put("uri", root.toString())
    }

    fun listDirectory(relativePath: String): JSONObject {
        val normalized = normalize(relativePath)
        val directory = resolve(normalized)
        val entries = JSONArray()
        children(directory).sortedWith(
            compareBy<ChildDocument> { !it.isDirectory }
                .thenBy { it.name.lowercase() }
        ).forEach { child ->
            val childPath = joinPath(normalized, child.name)
            entries.put(
                JSONObject()
                    .put("name", child.name)
                    .put("path", childPath)
                    .put("is_directory", child.isDirectory)
                    .put("suffix", child.name.substringAfterLast('.', "").lowercase())
            )
        }
        return JSONObject()
            .put("path", normalized)
            .put("entries", entries)
    }

    fun readText(relativePath: String): JSONObject {
        val normalized = normalize(relativePath)
        val uri = resolve(normalized)
        val text = resolver.openInputStream(uri)?.bufferedReader(Charsets.UTF_8)?.use { it.readText() }
            ?: throw FileNotFoundException(normalized)
        return JSONObject()
            .put("path", normalized)
            .put("content", text)
    }

    fun writeText(relativePath: String, content: String): JSONObject {
        val normalized = normalize(relativePath)
        val uri = resolve(normalized)
        resolver.openOutputStream(uri, "rwt")?.bufferedWriter(Charsets.UTF_8)?.use {
            it.write(content)
        } ?: throw FileNotFoundException(normalized)
        return JSONObject().put("path", normalized)
    }

    fun activeRootKey(): String {
        return preferences.rootUri()?.toString()
            ?: throw IllegalStateException("No root folder selected.")
    }

    fun walkWorkspaceFiles(
        shouldStop: () -> Boolean,
        onFile: (WorkspaceFileRecord) -> Unit,
    ) {
        walkDirectory(
            directoryUri = rootDocumentUri(),
            relativeDirectory = "",
            shouldStop = shouldStop,
            onFile = onFile,
        )
    }

    fun readIndexText(file: WorkspaceFileRecord): String? {
        if (!file.isTextSearchable) return null
        return try {
            resolver.openInputStream(file.uri)
                ?.bufferedReader(Charsets.UTF_8)
                ?.use { it.readText() }
        } catch (_: Exception) {
            null
        }
    }

    fun inputStream(relativePath: String): InputStream {
        return resolver.openInputStream(resolve(normalize(relativePath)))
            ?: throw FileNotFoundException(relativePath)
    }

    fun fileExists(relativePath: String): Boolean {
        return runCatching { resolve(normalize(relativePath)) }.isSuccess
    }

    private fun walkDirectory(
        directoryUri: Uri,
        relativeDirectory: String,
        shouldStop: () -> Boolean,
        onFile: (WorkspaceFileRecord) -> Unit,
    ) {
        if (shouldStop()) return

        for (child in children(directoryUri)) {
            if (shouldStop()) return
            val path = joinPath(relativeDirectory, child.name)

            if (child.isDirectory) {
                if (child.name !in ignoredDirectoryNames) {
                    walkDirectory(
                        directoryUri = child.uri,
                        relativeDirectory = path,
                        shouldStop = shouldStop,
                        onFile = onFile,
                    )
                }
                continue
            }

            val suffix = child.name.substringAfterLast('.', "").lowercase()
            onFile(
                WorkspaceFileRecord(
                    path = path,
                    name = child.name,
                    uri = child.uri,
                    size = child.size,
                    modifiedAt = child.modifiedAt,
                    isTextSearchable =
                        suffix in textSuffixes && child.size <= MAX_TEXT_FILE_SIZE_BYTES,
                )
            )
        }
    }

    private fun resolve(relativePath: String): Uri {
        var current = rootDocumentUri()
        if (relativePath.isBlank()) return current
        for (part in relativePath.split('/').filter { it.isNotBlank() }) {
            current = children(current).firstOrNull { it.name == part }?.uri
                ?: throw FileNotFoundException(relativePath)
        }
        return current
    }

    private fun children(directoryUri: Uri): List<ChildDocument> {
        val root = preferences.rootUri() ?: throw IllegalStateException("No root folder selected.")
        val documentId = DocumentsContract.getDocumentId(directoryUri)
        val childrenUri = DocumentsContract.buildChildDocumentsUriUsingTree(root, documentId)
        val projection = arrayOf(
            DocumentsContract.Document.COLUMN_DOCUMENT_ID,
            DocumentsContract.Document.COLUMN_DISPLAY_NAME,
            DocumentsContract.Document.COLUMN_MIME_TYPE,
            DocumentsContract.Document.COLUMN_SIZE,
            DocumentsContract.Document.COLUMN_LAST_MODIFIED,
        )
        val result = mutableListOf<ChildDocument>()
        resolver.query(childrenUri, projection, null, null, null)?.use { cursor ->
            val idColumn = cursor.getColumnIndexOrThrow(DocumentsContract.Document.COLUMN_DOCUMENT_ID)
            val nameColumn = cursor.getColumnIndexOrThrow(DocumentsContract.Document.COLUMN_DISPLAY_NAME)
            val mimeColumn = cursor.getColumnIndexOrThrow(DocumentsContract.Document.COLUMN_MIME_TYPE)
            val sizeColumn = cursor.getColumnIndex(DocumentsContract.Document.COLUMN_SIZE)
            val modifiedColumn =
                cursor.getColumnIndex(DocumentsContract.Document.COLUMN_LAST_MODIFIED)
            while (cursor.moveToNext()) {
                val id = cursor.getString(idColumn)
                val name = cursor.getString(nameColumn) ?: continue
                val mime = cursor.getString(mimeColumn).orEmpty()
                val size = if (sizeColumn >= 0 && !cursor.isNull(sizeColumn)) {
                    cursor.getLong(sizeColumn)
                } else {
                    0L
                }
                val modifiedAt =
                    if (modifiedColumn >= 0 && !cursor.isNull(modifiedColumn)) {
                        cursor.getLong(modifiedColumn)
                    } else {
                        0L
                    }
                result += ChildDocument(
                    uri = DocumentsContract.buildDocumentUriUsingTree(root, id),
                    name = name,
                    isDirectory = mime == DocumentsContract.Document.MIME_TYPE_DIR,
                    size = size,
                    modifiedAt = modifiedAt,
                )
            }
        }
        return result
    }

    private fun rootDocumentUri(): Uri {
        val root = preferences.rootUri() ?: throw IllegalStateException("No root folder selected.")
        return rootDocumentUri(root)
    }

    private fun rootDocumentUri(root: Uri): Uri {
        return DocumentsContract.buildDocumentUriUsingTree(
            root,
            DocumentsContract.getTreeDocumentId(root),
        )
    }

    private fun documentName(uri: Uri): String {
        val projection = arrayOf(DocumentsContract.Document.COLUMN_DISPLAY_NAME)
        return resolver.query(uri, projection, null, null, null)?.use { cursor ->
            if (cursor.moveToFirst()) cursor.getString(0).orEmpty() else ""
        }.orEmpty()
    }

    private fun normalize(path: String): String {
        val components = path.replace('\\', '/').split('/').filter { it.isNotBlank() }
        if (components.any { it == "." || it == ".." }) {
            throw SecurityException("Path traversal is not allowed.")
        }
        return components.joinToString("/")
    }

    private fun joinPath(parent: String, child: String): String {
        return if (parent.isBlank()) child else "$parent/$child"
    }

    private data class ChildDocument(
        val uri: Uri,
        val name: String,
        val isDirectory: Boolean,
        val size: Long,
        val modifiedAt: Long,
    )

    private companion object {
        const val MAX_TEXT_FILE_SIZE_BYTES = 5L * 1024L * 1024L
    }
}
