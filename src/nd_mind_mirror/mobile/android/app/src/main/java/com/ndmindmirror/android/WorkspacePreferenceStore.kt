package com.ndmindmirror.android

import android.content.Context
import android.net.Uri

/**
 * Persists local and Dropbox workspace roots plus the currently active location.
 */
class WorkspacePreferenceStore(context: Context) {
    private val preferences =
        context.getSharedPreferences("mind_mirror_android_workspace", Context.MODE_PRIVATE)

    init {
        migrateLegacyRoot()
    }

    fun rootUri(): Uri? = rootUri(activeLocation())

    fun rootUri(location: WorkspaceLocation): Uri? {
        val value = preferences.getString(uriKey(location), null)?.trim().orEmpty()
        return value.takeIf { it.isNotBlank() }?.let(Uri::parse)
    }

    fun saveRootUri(location: WorkspaceLocation, uri: Uri) {
        preferences.edit()
            .putString(uriKey(location), uri.toString())
            .putString(KEY_ACTIVE_LOCATION, location.key)
            .apply()
    }

    fun activeLocation(): WorkspaceLocation {
        return WorkspaceLocation.fromKey(
            preferences.getString(KEY_ACTIVE_LOCATION, WorkspaceLocation.LOCAL.key)
        )
    }

    fun setActiveLocation(location: WorkspaceLocation): Boolean {
        if (rootUri(location) == null) return false
        preferences.edit()
            .putString(KEY_ACTIVE_LOCATION, location.key)
            .apply()
        return true
    }

    private fun migrateLegacyRoot() {
        if (
            preferences.contains(KEY_LOCAL_ROOT_URI) ||
            preferences.contains(KEY_DROPBOX_ROOT_URI)
        ) {
            return
        }

        val legacy = preferences.getString(KEY_LEGACY_ROOT_URI, null)?.trim().orEmpty()
        if (legacy.isBlank()) return

        preferences.edit()
            .putString(KEY_LOCAL_ROOT_URI, legacy)
            .putString(KEY_ACTIVE_LOCATION, WorkspaceLocation.LOCAL.key)
            .remove(KEY_LEGACY_ROOT_URI)
            .apply()
    }

    private fun uriKey(location: WorkspaceLocation): String {
        return when (location) {
            WorkspaceLocation.LOCAL -> KEY_LOCAL_ROOT_URI
            WorkspaceLocation.DROPBOX -> KEY_DROPBOX_ROOT_URI
        }
    }

    private companion object {
        const val KEY_LOCAL_ROOT_URI = "local_root_uri"
        const val KEY_DROPBOX_ROOT_URI = "dropbox_root_uri"
        const val KEY_ACTIVE_LOCATION = "active_location"
        const val KEY_LEGACY_ROOT_URI = "root_uri"
    }
}
