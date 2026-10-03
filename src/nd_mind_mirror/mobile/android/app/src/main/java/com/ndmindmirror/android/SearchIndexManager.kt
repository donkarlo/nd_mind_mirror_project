package com.ndmindmirror.android

import android.content.Context
import org.json.JSONObject
import java.util.concurrent.Executors
import java.util.concurrent.Future

/**
 * Builds and queries a persistent local search index for the active workspace root.
 */
class SearchIndexManager(
    context: Context,
    private val workspace: AndroidWorkspaceService,
) {
    private val database = SearchIndexDatabase(context)
    private val indexExecutor = Executors.newSingleThreadExecutor()

    @Volatile
    private var activeBuild: Future<*>? = null

    @Volatile
    private var activeBuildRootKey: String? = null

    @Synchronized
    fun refreshActiveRoot() {
        val rootKey = runCatching { workspace.activeRootKey() }.getOrNull() ?: return
        val state = database.state(rootKey)
        if (state.indexedFiles == 0) {
            startBuild(rootKey, force = false)
        }
    }

    @Synchronized
    private fun ensureActiveRootIndex(rootKey: String) {
        val state = database.state(rootKey)
        if (!state.complete) {
            startBuild(rootKey, force = false)
        }
    }

    @Synchronized
    private fun startBuild(rootKey: String, force: Boolean) {
        if (
            activeBuildRootKey == rootKey &&
            activeBuild?.isDone == false
        ) {
            return
        }
        if (!force && database.state(rootKey).complete) {
            return
        }

        activeBuild?.cancel(true)
        activeBuildRootKey = rootKey
        activeBuild = indexExecutor.submit {
            buildIndex(rootKey)
        }
    }

    fun search(query: String, kind: String, maxResults: Int = 100): JSONObject {
        val rootKey = workspace.activeRootKey()
        val fileSearch = kind == "files"
        val stateBeforeSearch = database.state(rootKey)

        if (fileSearch) {
            if (stateBeforeSearch.indexedFiles == 0) {
                startBuild(rootKey, force = false)
            }
        } else {
            ensureActiveRootIndex(rootKey)
        }

        val trimmed = query.trim()
        val results = if (trimmed.isEmpty()) {
            org.json.JSONArray()
        } else if (fileSearch) {
            database.searchFiles(rootKey, trimmed, maxResults)
        } else {
            database.searchText(rootKey, trimmed, maxResults)
        }

        val state = database.state(rootKey)
        val activelyIndexing =
            activeBuildRootKey == rootKey && activeBuild?.isDone == false
        val indexingRelevantToSearch =
            if (fileSearch) {
                state.indexedFiles == 0 && activelyIndexing
            } else {
                activelyIndexing || state.indexing
            }

        return JSONObject()
            .put("results", results)
            .put("indexing", indexingRelevantToSearch)
            .put("indexed_files", state.indexedFiles)
            .put(
                "index_complete",
                if (fileSearch) state.indexedFiles > 0 else state.complete && !activelyIndexing
            )
    }

    @Synchronized
    fun close() {
        activeBuild?.cancel(true)
        activeBuild = null
        activeBuildRootKey = null
        indexExecutor.shutdownNow()
        database.close()
    }

    private fun buildIndex(rootKey: String) {
        val buildId = System.currentTimeMillis()
        val contentQueue = mutableListOf<WorkspaceFileRecord>()
        var indexedFiles = 0

        database.beginBuild(rootKey)

        workspace.walkWorkspaceFiles(
            shouldStop = {
                Thread.currentThread().isInterrupted ||
                    workspace.activeRootKey() != rootKey
            },
            onFile = { file ->
                if (Thread.currentThread().isInterrupted) return@walkWorkspaceFiles

                val oldFingerprint = database.existingFingerprint(rootKey, file.path)
                val currentFingerprint = file.size to file.modifiedAt
                val metadataReliable = file.modifiedAt > 0L
                val contentCurrent =
                    metadataReliable &&
                        oldFingerprint == currentFingerprint &&
                        database.hasContent(rootKey, file.path)

                database.upsertMetadata(rootKey, file, buildId)

                if (file.isTextSearchable) {
                    if (!contentCurrent) {
                        contentQueue += file
                    }
                } else {
                    database.updateContent(rootKey, file, null)
                }

                indexedFiles += 1
                if (indexedFiles % PROGRESS_INTERVAL == 0) {
                    database.markProgress(rootKey, indexedFiles)
                }
            },
        )

        if (
            Thread.currentThread().isInterrupted ||
            workspace.activeRootKey() != rootKey
        ) {
            return
        }

        database.markProgress(rootKey, indexedFiles)

        for (file in contentQueue) {
            if (
                Thread.currentThread().isInterrupted ||
                workspace.activeRootKey() != rootKey
            ) {
                return
            }
            val content = workspace.readIndexText(file)
            database.updateContent(rootKey, file, content)
        }

        if (
            Thread.currentThread().isInterrupted ||
            workspace.activeRootKey() != rootKey
        ) {
            return
        }

        database.finishBuild(rootKey, buildId, indexedFiles)
    }

    private companion object {
        const val PROGRESS_INTERVAL = 25
    }
}
