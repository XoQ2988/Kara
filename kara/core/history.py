from PySide6.QtCore import QObject, Signal, QRectF, QPointF
from PySide6.QtGui import QUndoStack, QUndoCommand

from kara.gui.qt_hints import Qt


# region subclasses of QtGui.QUndoCommand
class AddBubbleCommand(QUndoCommand):
    def __init__(self, main_win, rect_item, *, description="Add Bubble"):
        super().__init__(description)
        self.main = main_win
        self.rect = rect_item
        self.list_item = None

    def redo(self):
        # 1) put the rect back into the scene
        self.main.viewer.scene().addItem(self.rect)
        # 2) add the side-panel entry (and remember it)
        self.list_item = self.main._add_bubble(self.rect)

    def undo(self):
        # remove the exact same rect & list entry
        self.main._remove_bubble_for(self.rect)


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


class MoveBubbleCommand(QUndoCommand):
    def __init__(self, main_win, rect_item, old_geom: QRectF, new_geom: QRectF,
                 *, description="Move/Resize Bubble"):
        super().__init__(description)
        self._main = main_win
        self._item = rect_item
        # scene‐coordinates at undo/redo time
        self._old = old_geom
        self._new = new_geom

    def undo(self):
        self._apply(self._old)

    def redo(self):
        self._apply(self._new)

    def _apply(self, scene_rect: QRectF):
        # scene_rect is absolute x,y,width,height
        # our MoveableRectItem always stores its rect at (0,0)->(w,h) and its pos = top-left
        self._item.setPos(QPointF(scene_rect.x(), scene_rect.y()))
        self._item.setRect(0, 0, scene_rect.width(), scene_rect.height())
        # make sure the list→properties panel stays in sync:
        self._main._on_programmatic_move(self._item, scene_rect)
# endregion


class UndoRedoController(QObject):
    can_undo_changed = Signal(bool)
    can_redo_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stack = QUndoStack(self)

        # relay the stack's "can undo/redo" signals
        self._stack.canUndoChanged.connect(self.can_undo_changed)
        self._stack.canRedoChanged.connect(self.can_redo_changed)

    def push(self, cmd: QUndoCommand):
        """Push a QUndoCommand onto the stack."""
        self._stack.push(cmd)

    def undo(self) -> None:
        """Undo one command, if possible"""
        if self._stack.canUndo():
            self._stack.undo()

    def redo(self) -> None:
        """Redo one command, if possible"""
        if self._stack.canRedo():
            self._stack.redo()

    def clear(self) -> None:
        """Remove all commands from the stack"""
        self._stack.clear()
