# Range bookmarks

Mind Mirror bookmarks are canonical half-open character ranges `[start_char, end_char)`.

The same `RangeBookmarkEditorMixin` is used by both `SelectionLatexEditor` and
`SelectionLargeLatexEditor`. Large Source virtualization only translates the
visible-window edit position to the canonical source offset; it does not own a
second bookmark model.

Behavior:
- Select text and right-click it: **Add Bookmark**.
- Right-click anywhere inside a bookmarked range: **Remove Bookmark**.
- The Bookmarks menu exposes the same contextual Add/Remove operation.
- Bookmarked text is shown with a yellow background in Source and Visual.
- Manage Bookmarks reads the live repository and supports Go To, Remove, and
  Remove All.
- Persisted entries contain `id`, `start_char`, `end_char`, `text`, and `name`.
- Existing selection bookmarks are migrated to character ranges. Old line-only
  bookmarks are intentionally not imported into the range-only model.
