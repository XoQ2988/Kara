from PySide6.QtGui import QUndoCommand
from PySide6.QtCore import QRectF, QPointF


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
