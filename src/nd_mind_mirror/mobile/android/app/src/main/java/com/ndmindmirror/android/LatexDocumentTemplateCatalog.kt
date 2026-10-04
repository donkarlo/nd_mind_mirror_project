package com.ndmindmirror.android

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

/**
 * Provides the same LaTeX document templates currently offered by the Ubuntu editor.
 */
class LatexDocumentTemplateCatalog(
    private val context: Context,
) {
    private val templates = linkedMapOf(
        "article_standard" to (
            "Article (standard)" to "mobile/templates/article.tex"
        ),
        "beamer" to (
            "Beamer" to "mobile/templates/beamer.tex"
        ),
        "german_learning" to (
            "German learning" to "mobile/templates/german_learning.tex"
        ),
    )

    fun items(): JSONArray {
        val values = JSONArray()
        templates.forEach { (id, definition) ->
            values.put(
                JSONObject()
                    .put("id", id)
                    .put("label", definition.first)
            )
        }
        return values
    }

    fun content(templateId: String): String {
        val definition = templates[templateId]
            ?: throw IllegalArgumentException("Unknown LaTeX template.")
        return context.assets.open(definition.second)
            .bufferedReader(Charsets.UTF_8)
            .use { it.readText() }
    }
}
