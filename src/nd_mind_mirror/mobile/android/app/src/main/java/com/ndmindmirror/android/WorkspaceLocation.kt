package com.ndmindmirror.android

/**
 * Identifies one persisted Android workspace location.
 */
enum class WorkspaceLocation(val key: String) {
    LOCAL("local"),
    DROPBOX("dropbox");

    companion object {
        fun fromKey(value: String?): WorkspaceLocation {
            return entries.firstOrNull { it.key == value } ?: LOCAL
        }
    }
}
