package com.ndmindmirror.android

import android.content.ContentValues
import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import org.json.JSONArray
import org.json.JSONObject

/**
 * Stores searchable workspace metadata and text locally so searches never rescan Dropbox.
 */
class SearchIndexDatabase(context: Context) :
    SQLiteOpenHelper(context, DATABASE_NAME, null, DATABASE_VERSION) {

    override fun onConfigure(database: SQLiteDatabase) {
        super.onConfigure(database)
        database.setForeignKeyConstraintsEnabled(true)
        database.enableWriteAheadLogging()
    }

    override fun onCreate(database: SQLiteDatabase) {
        database.execSQL(
            """
            CREATE TABLE indexed_files (
                root_key TEXT NOT NULL,
                path TEXT NOT NULL,
                name TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                modified_at INTEGER NOT NULL,
                content TEXT,
                build_id INTEGER NOT NULL,
                PRIMARY KEY (root_key, path)
            )
            """.trimIndent()
        )
        database.execSQL(
            """
            CREATE INDEX indexed_files_name_idx
            ON indexed_files(root_key, name COLLATE NOCASE)
            """.trimIndent()
        )
        database.execSQL(
            """
            CREATE TABLE index_roots (
                root_key TEXT PRIMARY KEY,
                complete INTEGER NOT NULL DEFAULT 0,
                indexed_files INTEGER NOT NULL DEFAULT 0,
                updated_at INTEGER NOT NULL DEFAULT 0
            )
            """.trimIndent()
        )
    }

    override fun onUpgrade(database: SQLiteDatabase, oldVersion: Int, newVersion: Int) {
        database.execSQL("DROP TABLE IF EXISTS indexed_files")
        database.execSQL("DROP TABLE IF EXISTS index_roots")
        onCreate(database)
    }

    fun beginBuild(rootKey: String) {
        writableDatabase.insertWithOnConflict(
            "index_roots",
            null,
            ContentValues().apply {
                put("root_key", rootKey)
                put("complete", 0)
                put("indexed_files", indexedCount(rootKey))
                put("updated_at", System.currentTimeMillis())
            },
            SQLiteDatabase.CONFLICT_REPLACE,
        )
    }

    fun existingFingerprint(rootKey: String, path: String): Pair<Long, Long>? {
        readableDatabase.query(
            "indexed_files",
            arrayOf("size_bytes", "modified_at"),
            "root_key = ? AND path = ?",
            arrayOf(rootKey, path),
            null,
            null,
            null,
            "1",
        ).use { cursor ->
            if (!cursor.moveToFirst()) return null
            return cursor.getLong(0) to cursor.getLong(1)
        }
    }

    fun hasContent(rootKey: String, path: String): Boolean {
        readableDatabase.query(
            "indexed_files",
            arrayOf("content"),
            "root_key = ? AND path = ?",
            arrayOf(rootKey, path),
            null,
            null,
            null,
            "1",
        ).use { cursor ->
            return cursor.moveToFirst() && !cursor.isNull(0)
        }
    }

    fun upsertMetadata(rootKey: String, file: WorkspaceFileRecord, buildId: Long) {
        writableDatabase.insertWithOnConflict(
            "indexed_files",
            null,
            ContentValues().apply {
                put("root_key", rootKey)
                put("path", file.path)
                put("name", file.name)
                put("size_bytes", file.size)
                put("modified_at", file.modifiedAt)
                put("build_id", buildId)
            },
            SQLiteDatabase.CONFLICT_IGNORE,
        )
        writableDatabase.update(
            "indexed_files",
            ContentValues().apply {
                put("name", file.name)
                put("size_bytes", file.size)
                put("modified_at", file.modifiedAt)
                put("build_id", buildId)
            },
            "root_key = ? AND path = ?",
            arrayOf(rootKey, file.path),
        )
    }

    fun updateContent(rootKey: String, file: WorkspaceFileRecord, content: String?) {
        writableDatabase.update(
            "indexed_files",
            ContentValues().apply {
                if (content == null) putNull("content") else put("content", content)
            },
            "root_key = ? AND path = ?",
            arrayOf(rootKey, file.path),
        )
    }

    fun finishBuild(rootKey: String, buildId: Long, indexedFiles: Int) {
        writableDatabase.beginTransaction()
        try {
            writableDatabase.delete(
                "indexed_files",
                "root_key = ? AND build_id <> ?",
                arrayOf(rootKey, buildId.toString()),
            )
            writableDatabase.insertWithOnConflict(
                "index_roots",
                null,
                ContentValues().apply {
                    put("root_key", rootKey)
                    put("complete", 1)
                    put("indexed_files", indexedFiles)
                    put("updated_at", System.currentTimeMillis())
                },
                SQLiteDatabase.CONFLICT_REPLACE,
            )
            writableDatabase.setTransactionSuccessful()
        } finally {
            writableDatabase.endTransaction()
        }
    }

    fun markProgress(rootKey: String, indexedFiles: Int) {
        writableDatabase.update(
            "index_roots",
            ContentValues().apply {
                put("indexed_files", indexedFiles)
                put("updated_at", System.currentTimeMillis())
            },
            "root_key = ?",
            arrayOf(rootKey),
        )
    }

    fun state(rootKey: String): SearchIndexState {
        readableDatabase.query(
            "index_roots",
            arrayOf("complete", "indexed_files"),
            "root_key = ?",
            arrayOf(rootKey),
            null,
            null,
            null,
            "1",
        ).use { cursor ->
            if (!cursor.moveToFirst()) {
                return SearchIndexState(indexing = false, indexedFiles = 0, complete = false)
            }
            val complete = cursor.getInt(0) != 0
            return SearchIndexState(
                indexing = !complete,
                indexedFiles = cursor.getInt(1),
                complete = complete,
            )
        }
    }

    fun searchFiles(rootKey: String, query: String, maxResults: Int): JSONArray {
        val results = JSONArray()
        val pattern = "%" + escapeLike(query) + "%"
        readableDatabase.query(
            "indexed_files",
            arrayOf("path", "name"),
            "root_key = ? AND name LIKE ? ESCAPE '\\' COLLATE NOCASE",
            arrayOf(rootKey, pattern),
            null,
            null,
            "name COLLATE NOCASE, path COLLATE NOCASE",
            maxResults.toString(),
        ).use { cursor ->
            while (cursor.moveToNext()) {
                results.put(
                    JSONObject()
                        .put("path", cursor.getString(0))
                        .put("snippet", cursor.getString(1))
                )
            }
        }
        return results
    }

    fun searchText(rootKey: String, query: String, maxResults: Int): JSONArray {
        val results = JSONArray()
        val pattern = "%" + escapeLike(query) + "%"
        readableDatabase.query(
            "indexed_files",
            arrayOf("path", "content"),
            "root_key = ? AND content IS NOT NULL AND content LIKE ? ESCAPE '\\' COLLATE NOCASE",
            arrayOf(rootKey, pattern),
            null,
            null,
            "path COLLATE NOCASE",
        ).use { cursor ->
            while (cursor.moveToNext() && results.length() < maxResults) {
                val path = cursor.getString(0)
                val content = cursor.getString(1).orEmpty()
                content.lineSequence().forEachIndexed { index, line ->
                    if (
                        results.length() < maxResults &&
                        line.contains(query, ignoreCase = true)
                    ) {
                        results.put(
                            JSONObject()
                                .put("path", path)
                                .put("line", index + 1)
                                .put("snippet", line.trim().take(240))
                        )
                    }
                }
            }
        }
        return results
    }

    private fun indexedCount(rootKey: String): Int {
        readableDatabase.rawQuery(
            "SELECT COUNT(*) FROM indexed_files WHERE root_key = ?",
            arrayOf(rootKey),
        ).use { cursor ->
            return if (cursor.moveToFirst()) cursor.getInt(0) else 0
        }
    }

    private fun escapeLike(value: String): String {
        return value
            .replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
    }

    private companion object {
        const val DATABASE_NAME = "mind_mirror_search_index.sqlite3"
        const val DATABASE_VERSION = 1
    }
}
