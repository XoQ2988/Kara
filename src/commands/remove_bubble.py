from PySide6.QtGui import QUndoCommand

from src.utils.qt_hints import Qt


class RemoveBubbleCommand(QUndoCommand):
    def __init__(self, main_win, rect_item, *, description="Remove Bubble"):
        super().__init__(description)
        self._main_win   = main_win
        self._rect_item  = rect_item
        # capture enough state that undo() can restore
        # e.g. the list‐row where it was, and its bubble‐text
        for row in range(main_win.bubble_list.count()):
            li = main_win.bubble_list.item(row)
            if li.data(Qt.UserRole) is rect_item:
                self._row      = row
                self._listitem = li
                break

    def redo(self):
        self._main_win._remove_bubble_for(self._rect_item)

    def undo(self):
        self._main_win._rect_list.insert(self._row, (self._listitem, self._rect_item))
        self._main_win.bubble_list.insertItem(self._row, self._listitem)
        self._main_win.viewer.add_graphics_item(self._rect_item)

        self._main_win._mark_dirty()
