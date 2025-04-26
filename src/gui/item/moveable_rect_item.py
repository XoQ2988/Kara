from typing import Literal, ClassVar, Dict, Any, Optional

from PySide6.QtCore import QObject, Signal, QRectF, QPointF
from PySide6.QtGui import QCursor, QBrush, QColor, QPen
from PySide6.QtWidgets import QGraphicsRectItem, QMenu, QGraphicsItem

from src.utils.qt_hints import Qt


class RectSignals(QObject):
    rectangle_changed = Signal(QRectF)
    delete_block      = Signal()
    done_changed      = Signal(bool)

class MoveableRectItem(QGraphicsRectItem):
    _STYLE: ClassVar[Dict[str, Dict[str, Any]]] = {
      "bubble": {
        "normal":  {"brush": QColor(255,25,25,125),   "pen": (QColor(255,25,25,255),1)},
        "selected":{"brush": QColor(255,25,100,100),  "pen": (QColor(255,25,25,255),2)},
        "done":    {"brush_alpha": 15,                 "pen_alpha":50, "pen_w":2},
      },
      "free-text": {
        "normal":  {"brush": QColor(25,25,255,125),   "pen": (QColor(25,25,255,255),1)},
        "selected":{"brush": QColor(25,25,100,100),   "pen": (QColor(25,25,255,255),2)},
        "done":    {"brush_alpha": 15,                 "pen_alpha":50, "pen_w":2},
      },
    }
    def __init__(self, rect: QRectF = None, parent=None, kind: str = "bubble"):
        super().__init__(rect or QRectF(), parent)
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))

        self.signals = RectSignals()

        self.kind: str = kind
        self._done: bool = False

        self.selected: bool = False
        self.handle_size: int = 20

        self.resize_handle: Optional[str] = None
        self.resize_start: Optional[QPointF] = None
        self.min_size: int = 10

        self._apply_style()

    # --- done property ---
    @property
    def done(self):
        return self._done

    @done.setter
    def done(self, val: bool):
        if self._done == val:
            return
        self._done = val
        self._apply_style("done" if val else "normal")
        self.signals.done_changed.emit(val)

    # --- selection override ---
    def setSelected(self, selected: bool):
        super().setSelected(selected)
        self._apply_style("selected" if selected else ("done" if self.done else "normal"))

    # --- context menu ---
    def contextMenuEvent(self, event):
        menu = QMenu()
        action = menu.addAction("Mark Done" if not self.done else "Unmark Done")
        action.triggered.connect(lambda: setattr(self, "done", not self.done))
        menu.addSeparator()
        del_act = menu.addAction("Delete")
        del_act.triggered.connect(lambda: self.signals.delete_block.emit())
        menu.exec(event.screenPos())

    # --- mouse event handlers ---
    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if event.button() != Qt.LeftButton:
            return

        pos = event.pos()
        handle = self.get_handle_at_position(pos, self.rect())
        if handle:
            # start a resize
            self.resize_handle = handle
            self.resize_start = pos
        else:
            # regular move
            self.resize_handle = None
    def mouseMoveEvent(self, event):
        if self.resize_handle:
            old_rect = self.rect()
            new_rect = QRectF(old_rect)

            local = event.pos()
            dx = local.x() - self.resize_start.x()
            dy = local.y() - self.resize_start.y()

            if 'left' in self.resize_handle:
                new_rect.setLeft(old_rect.left() + dx)
            if 'right' in self.resize_handle:
                new_rect.setRight(old_rect.right() + dx)
            if 'top' in self.resize_handle:
                new_rect.setTop(old_rect.top() + dy)
            if 'bottom' in self.resize_handle:
                new_rect.setBottom(old_rect.bottom() + dy)

            # enforce minimum size
            if new_rect.width() < self.min_size:
                new_rect.setWidth(self.min_size)
                if 'left' in self.resize_handle:
                    new_rect.moveRight(old_rect.right())
            if new_rect.height() < self.min_size:
                new_rect.setHeight(self.min_size)
                if 'top' in self.resize_handle:
                    new_rect.moveBottom(old_rect.bottom())

            # apply it
            self.setRect(new_rect)
            self.resize_start = local
            # emit change
            self.signals.rectangle_changed.emit(self.sceneBoundingRect())
        else:
            super().mouseMoveEvent(event)
    def hoverMoveEvent(self, event):
        self.update_cursor(event.pos())
        super().hoverMoveEvent(event)
    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if self.resize_handle:
            self.resize_handle = None
            self.resize_start = None

        self.signals.rectangle_changed.emit(self.sceneBoundingRect())

    # --- cursor & handle logic ---
    def update_cursor(self, pos):
        cursor_shape = self.get_cursor_for_position(pos)
        self.setCursor(QCursor(cursor_shape))
    def get_cursor_for_position(self, pos):
        handle = self.get_handle_at_position(pos, self.rect())
        if handle:
            cursors = {
                'top_left': Qt.SizeFDiagCursor,
                'top_right': Qt.SizeBDiagCursor,
                'bottom_left': Qt.SizeBDiagCursor,
                'bottom_right': Qt.SizeFDiagCursor,
                'top': Qt.SizeVerCursor,
                'bottom': Qt.SizeVerCursor,
                'left': Qt.SizeHorCursor,
                'right': Qt.SizeHorCursor,
            }
            return cursors[handle]

        if self.rect().contains(pos):
            return Qt.SizeAllCursor

        return Qt.PointingHandCursor
    def get_handle_at_position(self, pos, rect):
        handle_size = self.handle_size
        rect_rect = rect.toRect()
        top_left = rect_rect.topLeft()
        bottom_right = rect_rect.bottomRight()

        handles = {
            'top_left': QRectF(top_left.x() - handle_size / 2, top_left.y() - handle_size / 2, handle_size,
                               handle_size),
            'top_right': QRectF(bottom_right.x() - handle_size / 2, top_left.y() - handle_size / 2, handle_size,
                                handle_size),
            'bottom_left': QRectF(top_left.x() - handle_size / 2, bottom_right.y() - handle_size / 2, handle_size,
                                  handle_size),
            'bottom_right': QRectF(bottom_right.x() - handle_size / 2, bottom_right.y() - handle_size / 2, handle_size,
                                   handle_size),
            'top': QRectF(top_left.x(), top_left.y() - handle_size / 2, rect_rect.width(), handle_size),
            'bottom': QRectF(top_left.x(), bottom_right.y() - handle_size / 2, rect_rect.width(), handle_size),
            'left': QRectF(top_left.x() - handle_size / 2, top_left.y(), handle_size, rect_rect.height()),
            'right': QRectF(bottom_right.x() - handle_size / 2, top_left.y(), handle_size, rect_rect.height()),
        }

        for handle, handle_rect in handles.items():
            if handle_rect.contains(pos):
                return handle

        return None

    # --- helpers ---
    def _apply_style(self, state: Literal["normal","selected","done"] = "normal"):
        entry = self._STYLE[self.kind][state]

        if state in ("normal","selected"):
            brush = entry["brush"]
            pen_color, pen_w = entry["pen"]
        else:  # done-state overrides only alpha+pen width
            base = self._STYLE[self.kind]["normal"]
            brush = QColor(base["brush"])
            brush.setAlpha(entry["brush_alpha"])
            pen_color = QColor(base["pen"][0])
            pen_color.setAlpha(entry["pen_alpha"])
            pen_w = entry["pen_w"]

        self.setBrush(QBrush(brush))
        self.setPen(QPen(pen_color, pen_w))

        # disable interactions when “done”
        movable = (state != "done")
        self.setFlag(QGraphicsItem.ItemIsMovable, movable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, movable)
    def _toggle_done(self):
        self.done = not self.done
        self._apply_style()
        self.signals.done_changed.emit(self.done)
    def _handle_delete(self):
        self.signals.delete_block.emit()
        scene = self.scene()
        if scene:
            scene.removeItem(self)
