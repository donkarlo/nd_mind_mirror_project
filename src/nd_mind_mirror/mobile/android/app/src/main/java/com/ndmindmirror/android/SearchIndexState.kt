package com.ndmindmirror.android

/**
 * Describes the current state of the persistent search index for one workspace root.
 */
data class SearchIndexState(
    val indexing: Boolean,
    val indexedFiles: Int,
    val complete: Boolean,
)
