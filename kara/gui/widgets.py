from typing import Optional, List, ClassVar, Dict, Any, Literal

import numpy as np
from PySide6 import QtCore
from PySide6.QtCore import Signal, QPointF, QRectF, QSignalBlocker, QPoint, QRect, QSize, QObject
from PySide6.QtGui import QColor, QPixmap, QPainter, QFont, QCursor, QBrush, QPen
from PySide6.QtWidgets import QGraphicsScene, QGraphicsPixmapItem, QRubberBand, QGraphicsRectItem, QMenu

from kara.gui.qt_hints import QGraphicsView, Qt, QImage, QGraphicsItem

MIN_BOX_SIZE = 10

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


class PanelViewer(QGraphicsView):
    """
    A zoomable, pannable graphics view that displays an image and
    allows the user to draw, select and crop rectangular annotations
    """
    zoom_changed  = Signal(int)
    rect_created  = Signal(MoveableRectItem)
    rect_selected = Signal(MoveableRectItem)
    rect_deselected = Signal()

    ZOOM_IN_FACTOR  = 1.25
    ZOOM_OUT_FACTOR = 0.8
    PAN_STEP_RATIO  = 0.1  # pan 10% of view
    MIN_SCALE = 0.1  # 10%
    MAX_SCALE = 5.0  # 500%

    def __init__(self, parent=None):
        super().__init__(parent)
        self._orig_cv = None  # type: Optional[np.ndarray]
        self._pixmap_cache: Optional[QPixmap] = None
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        # The pixmap item that shows the loaded image
        self._photo_item: QGraphicsPixmapItem = QGraphicsPixmapItem()
        self._scene.addItem(self._photo_item)

        # Transformation state
        self._current_scale: float = 1.0
        self._zoom_percent: int = 100
        self.current_tool: Optional[str] = None

        # Drawing state
        self._drawing_rect: bool = False
        self._start_pos: QPointF = QPointF()
        self._cur_rects: List[MoveableRectItem] = []
        self._current_rect: Optional[MoveableRectItem] = None
        self._selected_rect: Optional[MoveableRectItem] = None

        # Panning state
        self._panning: bool = False
        self._pan_start: QPointF = QPointF()

        # rubber-band for box tool
        self._rubber_band = QRubberBand(QRubberBand.Rectangle, self)
        self._rubber_origin = QPoint()

        self.setDragMode(QGraphicsView.ScrollHandDrag)

    # --- Public API ---
    def set_tool(self, tool: str) -> None:
        """
            Switch the interaction tool.

        :param tool: "pan" or "box"
        """
        self.current_tool = tool
        if tool == 'pan':
            self.setDragMode(QGraphicsView.ScrollHandDrag)
            self.viewport().setCursor(Qt.OpenHandCursor)
        elif tool == 'box':
            self.setDragMode(QGraphicsView.NoDrag)
            self.viewport().setCursor(Qt.CrossCursor)

    @property
    def photo(self) -> QGraphicsPixmapItem:
        return self._photo_item

    def has_photo(self) -> bool:
        """Returns True if an image is currently loaded."""
        return not self._photo_item.pixmap().isNull()

    def load_cv2_image(self, cv_img):
        """Load a BGR‐format OpenCV image into the viewer, with HiDPI support and pixmap caching."""
        # Keep the raw for cropping
        self._orig_cv = cv_img.copy()

        h, w, _ = cv_img.shape
        bytes_per_line = 3 * w
        # Create QImage; note we do *not* scale it here
        q_img = QImage(cv_img.data, w, h, bytes_per_line, QImage.Format_BGR888)

        # Apply device‐pixel ratio so that on Retina displays it renders crisply
        dpr = self.devicePixelRatioF()
        q_img.setDevicePixelRatio(dpr)

        # Convert and cache
        pix = QPixmap.fromImage(q_img)
        pix.setDevicePixelRatio(dpr)
        self._pixmap_cache = pix

        # Display
        self._photo_item.setPixmap(pix)
        self._scene.setSceneRect(QRectF(pix.rect()))

        # Reset any transforms
        super().fitInView(self._photo_item, Qt.KeepAspectRatio)
        self._current_scale = 1.0
        self._zoom_percent = 100
        self.zoom_changed.emit(self._zoom_percent)

    def clear(self) -> None:
        """Clear the image and all drawn rectangles"""
        for item in self._scene.items():
            if isinstance(item, MoveableRectItem):
                self._scene.removeItem(item)
        self._zoom_percent = 100

    def crop_region(self, rect: QRectF) -> Optional[np.ndarray]:
        """Returns the sub-image under 'rect' from the original CV image."""
        # guard: no raw image loaded
        if self._orig_cv is None:
            return None

        # guard: no pixmap
        if self._photo_item.pixmap().isNull():
            return None

        # clamp & convert to ints
        x = max(0, int(rect.x()))
        y = max(0, int(rect.y()))
        w = max(0, int(rect.width()))
        h = max(0, int(rect.height()))

        # further clamp to image bounds
        h0, w0, _ = self._orig_cv.shape
        x = min(x, w0)
        y = min(y, h0)
        w = min(w, w0 - x)
        h = min(h, h0 - y)

        if w <= 0 or h <= 0:
            return None

        return self._orig_cv[y: y + h, x: x + w]

    def get_selected_rectangle(self) -> Optional[MoveableRectItem]:
        """Returns the currently selected rectangle, if any"""
        return self._selected_rect

    def add_graphics_item(self, item: MoveableRectItem) -> None:
        """Adds an existing graphics item to the scene and start tracking it."""
        item.setZValue(1)
        self._scene.addItem(item)
        if isinstance(item, MoveableRectItem):
            self._cur_rects.append(item)

    # --- View controls & zooming
    def fit_to_window(self) -> None:
        """Reset zoom so the image fits the view exactly"""
        if self._photo_item.pixmap().isNull():
            return
        if not self._pixmap_cache:
            return
        super().fitInView(self._photo_item, Qt.KeepAspectRatio)
        self._current_scale = 1.0
        self._zoom_percent = 100
        self.zoom_changed.emit(self._zoom_percent)

    def wheelEvent(self, ev) -> None:
        """Zoom or pan horizontally with mouse wheel + modifier"""

        angle = ev.angleDelta().y()
        ctrl = bool(ev.modifiers() & Qt.ControlModifier)
        shift = bool(ev.modifiers() & Qt.ShiftModifier)

        # Ctrl + wheel -> zoom
        if self.has_photo() and ctrl:
            factor = (self.ZOOM_IN_FACTOR if angle > 0 else self.ZOOM_OUT_FACTOR)
            self._apply_zoom(factor)
            ev.accept()

        # Shift + wheel -> horizontal pan
        elif self.has_photo() and shift:
            notches = angle / 120  # 1 notch = 120 units
            step = int(self.viewport().width() * self.PAN_STEP_RATIO * notches)
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - step
            )
            ev.accept()
        # Default: vertical scroll
        else:
            super().wheelEvent(ev)

    def _apply_zoom(self, factor: float) -> None:
        """
            Apply a relative zoom to the view, keeping the total scale within allowed bounds

        :param factor: Multiplicative zoom factor (e.g. 1.25 to zoom in 25%, 0.8 to zoom out 20%).
        """
        new_scale = self._current_scale * factor
        if not (self.MIN_SCALE <= new_scale <= self.MAX_SCALE):
            return

        # Just scale the view
        self.scale(factor, factor)
        self._scale = new_scale
        self._zoom = round(self._scale * 100)
        self.zoom_changed.emit(self._zoom)

    # --- Mouse event handlers ---
    def mousePressEvent(self, event):
        """Handles initiation of panning or box-drawing"""
        clicked_item = self.itemAt(event.pos())
        scene_pos = self.mapToScene(event.position().toPoint())

        if isinstance(clicked_item, QGraphicsPixmapItem):
            self.deselect_all()
        else:
            for item in self._scene.items():
                if isinstance(item, MoveableRectItem) and item != clicked_item:
                    item.setSelected(False)

        if event.button() == Qt.MiddleButton or (self.current_tool == 'pan' and event.button() == Qt.LeftButton):
            self._panning = True
            self._pan_start = event.pos()
            self.viewport().setCursor(Qt.ClosedHandCursor)
            event.accept()
            return

        if self.current_tool == 'box' and self.has_photo():
            if self._photo_item.sceneBoundingRect().contains(scene_pos):
                if isinstance(clicked_item, MoveableRectItem):
                    self.select_rectangle(clicked_item)
                    super().mousePressEvent(event)
                else:
                    self._drawing_rect = True
                    self._rubber_origin = event.pos()
                    self._rubber_band.setGeometry(QRect(self._rubber_origin, QSize()))
                    self._rubber_band.show()
            self.viewport().setCursor(Qt.CrossCursor)

    def mouseMoveEvent(self, event):
        """Update panning or the rubber-band rectangle."""
        if self._panning:
            delta = event.pos().toPointF() - self._pan_start
            self._pan_start = event.pos()
            self.horizontalScrollBar().setValue(int(self.horizontalScrollBar().value() - delta.x()))
            self.verticalScrollBar().setValue(int(self.verticalScrollBar().value() - delta.y()))
            return

        if self._rubber_band and self._rubber_band.isVisible():
            rect = QRect(self._rubber_origin, event.pos()).normalized()
            self._rubber_band.setGeometry(rect)
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Complete panning or finalize a new box"""
        # Finish panning
        if self._panning and (
                event.button() == Qt.MiddleButton or
                (self.current_tool == 'pan' and event.button() == Qt.LeftButton)
        ):
            self._panning = False
            # restore cursor
            if self.current_tool == 'pan':
                self.viewport().setCursor(Qt.OpenHandCursor)
            elif self.current_tool == 'box':
                self.viewport().setCursor(Qt.CrossCursor)
            else:
                self.viewport().setCursor(Qt.ArrowCursor)
            event.accept()
            return

        # Finish drawing a new box
        if self._rubber_band.isVisible():
            rb_geo = self._rubber_band.geometry()
            self._rubber_band.hide()

            p1 = self.mapToScene(rb_geo.topLeft())
            p2 = self.mapToScene(rb_geo.bottomRight())
            x, y = p1.x(), p1.y()
            w, h = p2.x() - p1.x(), p2.y() - p1.y()

            if w >= MIN_BOX_SIZE and h >= MIN_BOX_SIZE:
                rect_item = MoveableRectItem(QRectF(0, 0, w, h))
                rect_item.setPos(QPointF(x, y))
                rect_item.setZValue(1)
                self._scene.addItem(rect_item)
                self._cur_rects.append(rect_item)
                self.rect_created.emit(rect_item)

            return

        # Fallback to default behavior (selection, etc.)
        super().mouseReleaseEvent(event)

    # --- Helpers ---
    def select_rectangle(self, rect: MoveableRectItem) -> None:
        """Mark 'rect' as selected, emit its scene-cords"""
        if rect:
            blocker = QSignalBlocker(self)
            rect.setSelected(True)
            self._selected_rect = rect
            blocker.unblock()

            self.rect_selected.emit(rect)

    def deselect_all(self) -> None:
        """Clear selection on all rectangles"""
        for item in self._scene.items():
            if isinstance(item, MoveableRectItem):
                item.setSelected(False)
        self._selected_rect = None
        self.rect_deselected.emit()

    def constrain_point(self, point: QtCore.QPointF) -> QPointF:
        """Clamp 'point' to the photo's bounds"""
        w, h = self._photo_item.pixmap().width(), self._photo_item.pixmap().height()
        return QPointF(max(0, int(min(point.x(), w))), max(0, int(min(point.y(), h))))

    # --- Custom
    def drawForeground(self, painter: QPainter, rect: QRectF):
        """Show a placeholder message if no image is loaded."""
        super().drawForeground(painter, rect)
        if not self.has_photo():
            painter.save()
            painter.resetTransform()

            painter.setPen(QColor(200, 200, 200))
            font = QFont()
            font.setPointSize(14)
            painter.setFont(font)

            vp = self.viewport().rect()
            painter.drawText(vp, Qt.AlignCenter, "No page loaded")

            painter.restore()

    # --- Properties ---
    @property
    def zoom(self) -> int:
        """Current zoom level as a percentage"""
        return self._zoom_percent
