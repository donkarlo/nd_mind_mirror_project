package com.ndmindmirror.android

import android.net.Uri

/**
 * Describes one file discovered while scanning the active Android document tree.
 */
data class WorkspaceFileRecord(
    val path: String,
    val name: String,
    val uri: Uri,
    val size: Long,
    val modifiedAt: Long,
    val isTextSearchable: Boolean,
)
