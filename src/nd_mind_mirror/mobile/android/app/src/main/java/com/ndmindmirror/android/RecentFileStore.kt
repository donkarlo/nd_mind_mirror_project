package com.ndmindmirror.android

import android.content.Context
import org.json.JSONArray
import java.security.MessageDigest

/**
 * Persists recently opened Source files separately for each workspace root.
 */
class RecentFileStore(
    context: Context,
    private val preferences: WorkspacePreferenceStore,
) {
    private val storage =
        context.getSharedPreferences("mind_mirror_android_recent_files", Context.MODE_PRIVATE)

    fun remember(path: String) {
        val normalized = normalize(path) ?: return
        val updated = buildList {
            add(normalized)
            addAll(paths().filterNot { it == normalized })
        }.take(MAX_RECENT_FILES)
        writePaths(updated)
    }

    fun paths(): List<String> {
        val raw = storage.getString(storageKey(), "[]").orEmpty()
        return runCatching {
            val values = JSONArray(raw)
            buildList {
                for (index in 0 until values.length()) {
                    normalize(values.optString(index))?.let(::add)
                }
            }
        }.getOrDefault(emptyList())
    }

    fun replace(paths: List<String>) {
        writePaths(
            paths.mapNotNull(::normalize)
                .distinct()
                .take(MAX_RECENT_FILES)
        )
    }

    private fun writePaths(paths: List<String>) {
        val values = JSONArray()
        paths.forEach(values::put)
        storage.edit().putString(storageKey(), values.toString()).apply()
    }

    private fun storageKey(): String {
        val root = preferences.rootUri()?.toString().orEmpty()
        val digest = MessageDigest.getInstance("SHA-256")
            .digest(root.toByteArray(Charsets.UTF_8))
            .joinToString("") { byte -> "%02x".format(byte.toInt() and 0xff) }
        return "root_$digest"
    }

    private fun normalize(path: String): String? {
        val parts = path.replace('\\', '/')
            .split('/')
            .filter { it.isNotBlank() }
        if (parts.isEmpty() || parts.any { it == "." || it == ".." }) {
            return null
        }
        return parts.joinToString("/")
    }

    private companion object {
        const val MAX_RECENT_FILES = 30
    }
}
