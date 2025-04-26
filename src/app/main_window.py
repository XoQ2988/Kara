import functools
import json
import sys
import threading
import time
from pathlib import Path
from threading import Thread
from typing import Optional

import cv2
from PySide6.QtCore import QSettings, QRectF, QPointF, Signal, QSignalBlocker
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QMainWindow, QListWidgetItem, QSplitter, QFileSystemModel, QTreeView, QListWidget, \
    QTextEdit, QGroupBox, QFormLayout, QHBoxLayout, QButtonGroup, QToolButton, QStatusBar, QLabel, \
    QFileDialog, QMessageBox, QApplication, QComboBox, QSpinBox, QProgressBar, QWidget

from src.commands.add_bubble import AddBubbleCommand
from src.commands.move_bubble import MoveBubbleCommand
from src.commands.remove_bubble import RemoveBubbleCommand
from src.controllers.annotation import AnnotationController, AnnotationData
from src.controllers.detection import SpeechBubbleDetector, Detection
from src.controllers.ocr import OCREngine
from src.controllers.undo_redo import UndoRedoController
from src.gui.item.moveable_rect_item import MoveableRectItem
from src.gui.viewer.panel_viewer import PanelViewer
from src.utils.qt_hints import Qt, QFrame, QSizePolicy, QGraphicsItem


class MainWindow(QMainWindow):
    detection_done = Signal(list)
    ocr_done = Signal(object, str)

    # region Constructor & UI setup
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Kara")
        self.resize(1200, 800)

        self.model_start = time.time()
        self.detector = SpeechBubbleDetector(Path.cwd().parent.parent / "model" / "comic-speech-bubble-detector.pt")
        self.detector_thread: Thread = threading.Thread(target=self._wait_model_ready, daemon=True)
        self.ocr_engine = OCREngine()
        self.ocr_thread: Thread = threading.Thread(target=self._wait_model_ready, daemon=True)

        self.undo_ctrl = UndoRedoController(self)
        self.annotations = AnnotationController(self)
        self._last_geom: dict[MoveableRectItem, QRectF] = {}

        self.project_root: Optional[Path] = None
        self.cur_img_path: Optional[Path] = None
        self._rect_list: list[tuple[QListWidgetItem, MoveableRectItem]] = []
        self.pages: list[Path] = []
        self.current_page_idx = -1
        self._dirty: bool = False

        self._init_ui()
        self.register_shortcuts()
        self._post_init()

        self._load_settings()

    def _init_ui(self):
        # --- Menu Bar ---
        mb = self.menuBar()

        # - File Menu -
        file_menu = mb.addMenu("File")
        self.action_new_project = file_menu.addAction("New Project")
        self.action_open_project = file_menu.addAction("Open Project...")
        file_menu.addSeparator()
        self.action_save = file_menu.addAction("Save")
        self.action_save_as = file_menu.addAction("Save As...")
        file_menu.addSeparator()
        self.action_export_json = file_menu.addAction("Export JSON")
        file_menu.addSeparator()
        self.action_exit = file_menu.addAction("Exit")

        # - Edit Menu -
        edit_menu = mb.addMenu("Edit")
        self.action_delete_bubble = edit_menu.addAction("Delete Bubble")
        self.action_delete_all_bubbles = edit_menu.addAction("Delete all Bubbles")
        edit_menu.addSeparator()
        self.action_undo = edit_menu.addAction("Undo")
        self.action_redo = edit_menu.addAction("Redo")

        # - View Menu -
        view_menu = mb.addMenu("View")
        self.action_prev_page = view_menu.addAction("Previous Page")
        self.action_next_page = view_menu.addAction("Next Page")
        self.action_fit_to_window = view_menu.addAction("Fit to Window")

        # - Tools Menu -
        tools_menu = mb.addMenu("Tools")
        self.action_detect_bubbles = tools_menu.addAction("Detect Bubbles (YOLO)")  #
        view_menu.addSeparator()
        self.action_run_ocr = tools_menu.addAction("Run OCR")
        self.action_run_ocr_sel = tools_menu.addAction("Run OCR on Selection")

        # --- Central Splitter ---
        self.splitter = QSplitter(Qt.Horizontal, self)

        # Left: filesystem tree
        root = Path.home() / "Documents" / "Mangas"
        self.fs_model = QFileSystemModel(self)
        self.fs_model.setRootPath(str(root))
        self.fs_model.setNameFilters(["*.jpg"])
        self.fs_model.setNameFilterDisables(False)

        self.tree = QTreeView()
        self.tree.setModel(self.fs_model)
        self.tree.setRootIndex(self.fs_model.index(str(root)))
        self.tree.setMinimumWidth(150)
        for col in (1, 2, 3):
            self.tree.hideColumn(col)
        self.splitter.addWidget(self.tree)

        # Center: image viewer
        self.viewer = PanelViewer()
        self.splitter.addWidget(self.viewer)

        # Right: vertical annotation splitter
        self.ann_split = QSplitter(Qt.Vertical)
        self.bubble_list = QListWidget()
        self.ann_split.addWidget(self.bubble_list)

        self.ocr_output = QTextEdit()
        self.ocr_output.setPlaceholderText("OCR output will appear here")
        self.ann_split.addWidget(self.ocr_output)

        self.trans_edit = QTextEdit()
        self.trans_edit.setPlaceholderText("Enter translation here")
        self.ann_split.addWidget(self.trans_edit)

        props = QGroupBox("Bubble Properties")
        form = QFormLayout(props)
        self.kind_combo = QComboBox()
        self.kind_combo.addItems(["bubble", "free-text"]); form.addRow("Kind:", self.kind_combo)

        self.x_spin = QSpinBox(); self.x_spin.setRange(0, 10000); form.addRow("X:", self.x_spin)
        self.y_spin = QSpinBox(); self.y_spin.setRange(0, 10000); form.addRow("Y:", self.y_spin)
        self.w_spin = QSpinBox(); self.w_spin.setRange(1, 10000); form.addRow("Width:", self.w_spin)
        self.h_spin = QSpinBox(); self.h_spin.setRange(1, 10000); form.addRow("Height:", self.h_spin)

        self.ann_split.addWidget(props)
        self.ann_split.setMinimumWidth(150)
        self.ann_split.setMaximumWidth(300)
        self.ann_split.setStretchFactor(0, 0)  # bubble list
        self.ann_split.setStretchFactor(1, 0)  # ocr output
        self.ann_split.setStretchFactor(2, 1)  # translation editor
        self.ann_split.setStretchFactor(3, 0)  # properties

        self.splitter.addWidget(self.ann_split)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 4)
        self.splitter.setStretchFactor(2, 1)
        self.splitter.setSizes([200, 800, 200])

        self.setCentralWidget(self.splitter)

        # --- Floating Toolbar ---
        tb = QFrame(self)
        tb.setFrameShape(QFrame.StyledPanel)
        tb.setStyleSheet("background: rgba(50,50,50,200); border-radius: 8px;")
        tb_layout = QHBoxLayout(tb)
        tb_layout.setContentsMargins(5, 5, 5, 5)
        tb_layout.setSpacing(10)

        self.tool_group = QButtonGroup(self)
        self.tool_group.setExclusive(True)
        for name in ("Pan", "Box"):
            btn = QToolButton()
            btn.setText(name)
            btn.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            btn.setCheckable(True)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            self.tool_group.addButton(btn)
            tb_layout.addWidget(btn)

        self.toolbar_frame = tb

        # --- Status Bar ---
        status = QStatusBar()
        self.status_message = QLabel("Ready")
        self.zoom_label = QLabel("Zoom: 100%")
        self.page_label = QLabel("")
        self.progress = QProgressBar()
        self.progress.setMinimum(0)
        self.progress.setMaximum(1)
        self.progress.setValue(0)
        self.progress.setFormat("Done: %v/%m (%p%)")
        self.progress.setFixedWidth(180)
        status.addPermanentWidget(self.progress)

        status.addWidget(self.status_message)
        status.addPermanentWidget(self.page_label)
        status.addPermanentWidget(self.zoom_label)
        # remove the built-in separator
        status.setStyleSheet("QStatusBar::item { border: none; }")
        self.setStatusBar(status)
    # endregion
    # region Shortcut registration
    def register_shortcuts(self):
        # - File Menu -
        self.action_new_project.setShortcut(QKeySequence("Ctrl+N"))
        # self.action_open_project.setShortcut(QKeySequence(""))
        self.action_save.setShortcut(QKeySequence("Ctrl+S"))
        self.action_save_as.setShortcut(QKeySequence("Ctrl+Shift+S"))
        # self.action_export_json.setShortcut(QKeySequence(""))
        self.action_exit.setShortcut(QKeySequence("Ctrl+Q"))

        # - Edit Menu -
        self.action_undo.setShortcut(QKeySequence("Ctrl+Z"))
        self.action_redo.setShortcut(QKeySequence("Ctrl+Y"))
        self.action_delete_bubble.setShortcut(QKeySequence("Del"))
        # self.action_clear_annotations.setShortcut(QKeySequence(""))

        # - View Menu -
        self.action_prev_page.setShortcut(QKeySequence("Left"))
        self.action_next_page.setShortcut(QKeySequence("Right"))
        self.action_fit_to_window.setShortcut(QKeySequence("Ctrl+F"))

        # - Tool shortcuts -
        QShortcut(QKeySequence("V"), self).activated.connect(lambda: self._select_tool("Pan"))
        QShortcut(QKeySequence("M"), self).activated.connect(lambda: self._select_tool("Box"))

        # Toggle done on the current bubble
        QShortcut(QKeySequence("Space"), self).activated.connect(self._toggle_done_selected)
    # endregion
    # region Signal-wiring / post-init
    def _post_init(self):
        def _connect_signals(slot, *signals):
            """Helper: connect each Qt signal in `signals` to the same slot."""
            for sig in signals:
                sig.connect(slot)

        # — Model Loading —
        self.detector_thread.start()
        self.ocr_thread.start()
        self.detection_done.connect(self._apply_detections)
        self.ocr_done.connect(self._on_ocr_done)
        self.action_detect_bubbles.setEnabled(False)

        # — File Menu —
        self.action_new_project.triggered.connect(self.new_project)
        self.action_open_project.triggered.connect(self.open_project)
        self.action_save.triggered.connect(self._on_save_clicked)
        self.action_save_as.triggered.connect(self.save_as)
        # self.action_export_json.triggered.connect(self.export_json)
        self.action_exit.triggered.connect(self.close)

        # — Edit Menu —
        self.action_delete_bubble.triggered.connect(self.delete_selected_bubble)
        self.action_delete_all_bubbles.triggered.connect(self.clear_bubbles)
        self.action_undo.triggered.connect(self.undo_ctrl.undo)
        self.action_redo.triggered.connect(self.undo_ctrl.redo)
        self.undo_ctrl.can_undo_changed.connect(self.action_undo.setEnabled)
        self.undo_ctrl.can_redo_changed.connect(self.action_redo.setEnabled)
        self.action_undo.setEnabled(False)
        self.action_redo.setEnabled(False)

        # — View Menu —
        self.action_prev_page.triggered.connect(self.prev_page)
        self.action_next_page.triggered.connect(self.next_page)
        self.action_fit_to_window.triggered.connect(self.viewer.fit_to_window)

        # — Tools Menu —
        self.action_detect_bubbles.triggered.connect(self.on_detect_bubbles)
        self.action_run_ocr.triggered.connect(self.on_run_ocr_all)
        self.action_run_ocr_sel.triggered.connect(self.on_run_ocr)

        # — Tree View —
        self.tree.clicked.connect(self.on_tree_clicked)

        # — List & Properties Sync —
        self.bubble_list.itemChanged.connect(self._on_bubble_done_changed)
        self.bubble_list.currentItemChanged.connect(self.on_bubble_selected)
        self.kind_combo.currentTextChanged.connect(self.on_kind_changed)

        # wire up spinboxes → on_spin_changed
        _connect_signals(
            self.on_spin_changed,
            self.x_spin.valueChanged, self.y_spin.valueChanged,
            self.w_spin.valueChanged, self.h_spin.valueChanged,
        )

        # mark document dirty on any field change
        _connect_signals(
            self._mark_dirty,
            self.x_spin.valueChanged, self.y_spin.valueChanged,
            self.w_spin.valueChanged, self.h_spin.valueChanged,
            self.kind_combo.currentTextChanged,
            self.ocr_output.textChanged, self.trans_edit.textChanged,
        )

        # disable fields until a bubble is selected
        self._set_property_fields_enabled(False)

        # — Viewer Signals —
        self.viewer.zoom_changed.connect(lambda z: self.zoom_label.setText(f"Zoom: {z}%"))
        self.viewer.rect_created.connect(self._on_new_rect)
        self.viewer.rect_selected.connect(self.on_viewer_rect_selected)
        self.viewer.rect_deselected.connect(self.on_viewer_rect_cleared)

        # — Floating Toolbar —
        self.tool_group.buttonClicked.connect(self.on_tool_selected)
        # default to Box
        for btn in self.tool_group.buttons():
            if btn.text() == "Box":
                btn.setChecked(True)
                self.on_tool_selected(btn)
                break

        self.annotations.annotations_loaded.connect(self.on_annotations_loaded)
        self.annotations.annotations_saved.connect(self.on_annotations_saved)

    # endregion
    # region Project & File actions
    def new_project(self):
        """Pick (or create) an empty project folder."""
        dir_str = QFileDialog.getExistingDirectory(
            self, "Select or Create Project Folder",
            str(Path.home() / "Documents" / "Mangas")
        )
        if not dir_str:
            return

        dir_path = Path(dir_str)
        self.project_root = dir_path
        self.tree.setRootIndex(self.fs_model.setRootPath(dir_str))
        self.cur_img_path = None
        self.clear_bubbles()
        self.status_message.setText(f"New project: {dir_path.name}")

    def open_project(self):
        """Open an existing project folder."""
        dir_str = QFileDialog.getExistingDirectory(
            self, "Open Project Folder",
            str(Path.home() / "Documents" / "Mangas")
        )

        if not dir_str:
            return

        dir_path = Path(dir_str)
        self.project_root = dir_path
        self.tree.setRootIndex(self.fs_model.setRootPath(dir_str))
        self.cur_img_path = None
        self.clear_bubbles()
        self.status_message.setText(f"Project opened: {dir_path.name}")

    def save_as(self):
        """Save current page’s annotations to a user‐picked JSON file."""
        if not self.cur_img_path:
            QMessageBox.warning(self, "Save As", "No page loaded to save.")
            return
        default = self.cur_img_path.with_suffix(".json")
        path_str, _ = QFileDialog.getSaveFileName(
            self, "Save Annotations As...", str(default), "JSON files (*.json)"
        )
        if not path_str:
            return

        out_path = Path(path_str)
        ann = []
        for _, rect in self._rect_list:
            geo = rect.sceneBoundingRect()
            ann.append({
                "rect": [geo.x(), geo.y(), geo.width(), geo.height()],
                "kind": rect.kind,
                "ocr": getattr(rect, "ocr_text", ""),
                "translation": getattr(rect, "trans", "")
            })
        out_path.write_text(json.dumps({"bubbles": ann}, ensure_ascii=False, indent=2), encoding="utf-8")
        self.status_message.setText(f"Saved as {out_path.name}")
    # endregion
    # region Page Navigation
    def load_page(self, path: Path):
        if self._dirty:
            reply = QMessageBox.question(
                self,
                "Discard annotations?",
                "You have unsaved annotations on this page. Do you really want to discard them and load a new page?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return

        img = cv2.imread(str(path))
        if img is None:
            self.status_message.setText(f"Failed to load {path.name}")
            return

        self.cur_img_path = path
        self.clear_bubbles()
        self.annotations.load(self.cur_img_path)
        self.viewer.load_cv2_image(img)
        self.status_message.setText(f"Loaded: {path.name}")
        self.zoom_label.setText(f"Zoom: {self.viewer.zoom}%")

        # update navigation state
        self.pages = sorted(path.parent.glob("*.jpg"))
        self.current_page_idx = self.pages.index(path)
        has_prev = self.current_page_idx > 0
        has_next = self.current_page_idx < len(self.pages) - 1

        self.action_prev_page.setEnabled(has_prev)
        self.action_next_page.setEnabled(has_next)

        self._set_property_fields_enabled(False)

        self._update_title()
        self._update_page_label()

    def prev_page(self):
        if self.current_page_idx > 0:
            self.load_page(self.pages[self.current_page_idx - 1])

    def next_page(self):
        if self.current_page_idx < len(self.pages) - 1:
            self.load_page(self.pages[self.current_page_idx + 1])

    def _update_page_label(self):
        if self.pages and self.current_page_idx >= 0:
            self.page_label.setText(f"Page {self.current_page_idx + 1} of {len(self.pages)}")
        else:
            self.page_label.setText("")
    # endregion
    # region Panel callbacks
    def _on_save_clicked(self):
        # 1. Ensure there’s something to save
        if not self.cur_img_path:
            QMessageBox.warning(self, "Save", "No page loaded to save.")
            return

        # 2. Build a list of annotation dicts from the UI state
        ann_list = []
        for _, rect in self._rect_list:
            geo = rect.sceneBoundingRect()
            ann_list.append({
                "rect": [
                    float(geo.x()),
                    float(geo.y()),
                    float(geo.width()),
                    float(geo.height())
                ],
                "kind": rect.kind,
                "done": getattr(rect, "done", False),
                "ocr": getattr(rect, "ocr_text", ""),
                "translation": getattr(rect, "trans", "")
            })

        # 3. Delegate to controller
        try:
            self.annotations.save(self.cur_img_path, ann_list)
        except Exception as e:
            QMessageBox.critical(self, "Save Failed", f"Could not save annotations:\n{e}")
            return

        # 4. Mark clean and notify user
        self._dirty = False
        self.status_message.setText(f"Saved annotations to {self.cur_img_path.name}")
    def on_tree_clicked(self, index):
        path = Path(self.fs_model.filePath(index))

        if path.suffix.lower() == ".jpg":
            img = cv2.imread(str(path))
            self.cur_img_path = path

            # clear current bubbles & image
            self.clear_bubbles()
            self.viewer.clear()

            # ask controller to load json
            self.annotations.load(path)

            # load image
            if img is not None:
                self.viewer.load_cv2_image(img)
                self.status_message.setText(f"Loaded: {path.name}")
                self.zoom_label.setText(f"Zoom: {self.viewer.zoom}%")
            else:
                self.status_message.setText("Failed to load image")

            # - now that cur_img_path is set, wire up page navigation -
            chapter = path.parent
            self.pages = sorted(chapter.glob("*.jpg"))
            self.current_page_idx = self.pages.index(path)

            has_prev = self.current_page_idx > 0
            has_next = self.current_page_idx < len(self.pages) - 1

            self.action_prev_page.setEnabled(has_prev)
            self.action_next_page.setEnabled(has_next)

            self._update_page_label()

    def on_bubble_selected(self, current, previous):
        if not current:
            return

        self._set_property_fields_enabled(True)

        for li, rect in self._rect_list:
            if li is previous:
                rect.setSelected(False)

            if li is current:
                if rect.done:
                    self._set_property_fields_enabled(False)

                self.viewer.centerOn(rect)

                self.ocr_output.blockSignals(True)
                self.ocr_output.setPlainText(getattr(rect, "ocr_text", ""))
                self.ocr_output.blockSignals(False)
                self.trans_edit.blockSignals(True)
                self.trans_edit.setPlainText(getattr(rect, "trans", ""))
                self.trans_edit.blockSignals(False)

                self.kind_combo.blockSignals(True)
                self.kind_combo.setCurrentText(rect.kind)
                self.kind_combo.blockSignals(False)

                with QSignalBlocker(self.x_spin), QSignalBlocker(self.y_spin), \
                        QSignalBlocker(self.w_spin), QSignalBlocker(self.h_spin):
                    self.x_spin.setValue(int(rect.pos().x()))
                    self.y_spin.setValue(int(rect.pos().y()))
                    self.w_spin.setValue(int(rect.rect().width()))
                    self.h_spin.setValue(int(rect.rect().height()))

    def on_viewer_rect_selected(self, scene_rect: MoveableRectItem):
        for li, r in self._rect_list:
            if r is scene_rect:
                self.bubble_list.setCurrentItem(li)
                if not r.done:
                    self._set_property_fields_enabled(True)
                return

    def on_viewer_rect_cleared(self):
        self.bubble_list.clearSelection()
        self._set_property_fields_enabled(False)

    def on_tool_selected(self, button):
        name = button.text()
        tool_key = name.lower()

        self.viewer.set_tool(tool_key)

        self.status_message.setText(f"Tool: {name}")

    def _on_bubble_done_changed(self, item: QListWidgetItem):
        # find its rect
        for li, rect in self._rect_list:
            if li is item:
                rect.done = (item.checkState() == Qt.Checked)

                rect.setFlag(QGraphicsItem.ItemIsMovable, not rect.done)
                rect.setFlag(QGraphicsItem.ItemIsFocusable, not rect.done)
                break

        # if this is the currently selected bubble, re‐apply field enabling
        if self.bubble_list.currentItem() is item:
            self.on_bubble_selected(item, None)

        self._update_progress()

    def on_annotations_saved(self, image_path: Path):
        if image_path == self.cur_img_path:
            self._dirty = False
            self.status_message.setText(f"Annotations saved to {image_path.stem}.json")

    def on_annotations_loaded(self, image_path: Path, ann_list: list[AnnotationData]):
        # If this isn’t the page currently showing, ignore:
        if image_path != self.cur_img_path:
            return

        # clear any stray rectangles (we did already, but be safe)
        self.clear_bubbles()

        # rebuild from data
        for entry in ann_list:
            x, y, w, h = entry.rect
            rect = MoveableRectItem(QRectF(0, 0, w, h), kind=entry.kind)
            rect.setPos(QPointF(x, y))
            rect.done = entry.done
            rect.ocr_text = entry.ocr
            rect.trans = entry.translation

            self.viewer.add_graphics_item(rect)
            self._add_bubble(rect)

        # update any progress bars / dirty flags
        self._update_progress()
        self._dirty = False

    def _on_list_done_toggled(self, item: QListWidgetItem):
        for li, rect in self._rect_list:
            if li is item:
                rect.done = (item.checkState() == Qt.Checked)
                rect._apply_style()
                break

    def on_ocr_changed(self):
        li = self.bubble_list.currentItem()
        if not li:
            return
        txt = self.ocr_output.toPlainText()
        for item, rect in self._rect_list:
            if item is li:
                rect.ocr_text = txt
                break

    def on_spin_changed(self, _):
        li = self.bubble_list.currentItem()
        if not li:
            return

        for item, rect in self._rect_list:
            if item is li:
                old = self._last_geom.get(rect, QRectF(rect.pos(), rect.rect().size()))
                new = QRectF(self.x_spin.value(),
                             self.y_spin.value(),
                             self.w_spin.value(),
                             self.h_spin.value())

                # block the rectangle_changed signal while we update
                with QSignalBlocker(rect.signals):
                    rect.setPos(new.topLeft())
                    rect.setRect(0, 0, new.width(), new.height())
                # once we leave this block, no rectangle_changed will have fired

                # now manually push the undo command:
                self.undo_ctrl.push(MoveBubbleCommand(self, rect, old, new))
                self._last_geom[rect] = new
                break

    def on_kind_changed(self, new_kind: str):
        item = self.bubble_list.currentItem()
        if not item:
            return

        for li, rect in self._rect_list:
            if li is item:
                rect.kind = new_kind

                base = "Bubble" if new_kind == "bubble" else "Free-text"
                idx = len([r for _, r in self._rect_list if r.kind == new_kind])
                li.setText(f"{base} {idx}")
                break

    def on_translation_changed(self):
        li = self.bubble_list.currentItem()
        if not li:
            return
        txt = self.trans_edit.toPlainText()
        for item, rect in self._rect_list:
            if item is li:
                rect.trans = txt
                break
    # endregion
    # region Commands & Undo/Redo Hooks
    def _on_new_rect(self, scene_rect):
        self.undo_ctrl.push(AddBubbleCommand(self, scene_rect))

    def _on_rect_changed(self, item: MoveableRectItem, new_rect: QRectF):
        old_rect = self._last_geom.get(item, new_rect)

        if old_rect != new_rect:
            self.undo_ctrl.push(MoveBubbleCommand(self, item, old_rect, new_rect))
            self._last_geom[item] = new_rect

    def _on_programmatic_move(self, item: MoveableRectItem, scene_rect: QRectF):
        # find the QListWidgetItem for this rect and re‐select it:
        for li, r in self._rect_list:
            if r is item:
                self.bubble_list.setCurrentItem(li)
                break

        self.on_bubble_selected(self.bubble_list.currentItem(), None)

    def _on_rect_created(self, rect_item: MoveableRectItem):
        # Prevent double‐adding if somehow the same rect fires twice
        if any(existing is rect_item for _, existing in self._rect_list):
            return

        self._add_bubble(rect_item)

    def delete_selected_bubble(self):
        li = self.bubble_list.currentItem()
        if li is None:
            return

        for idx, (item, rect) in enumerate(self._rect_list):
            if item is li:
                self.undo_ctrl.push(RemoveBubbleCommand(self, rect, description="Delete Bubble"))
                self._mark_dirty()
                break
    # endregion
    # region OCR & Detection callbacks
    def _wait_model_ready(self):
        self.detector.wait_until_ready()

        # Notify user
        self.status_message.setText(f"Model loaded in {time.time() - self.model_start:.2f} seconds")

    def on_detect_bubbles(self):
        if not self.cur_img_path or not self.detector.ready():
            return

        # Warn if there are existing bubbles
        if self._rect_list:
            reply = QMessageBox.question(
                self,
                "Overwrite bubbles?",
                "There are already detected/annotated bubbles. Do you want to overwrite them?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                return

            self.clear_bubbles()

        self.status_message.setText("Detecting bubbles...")

        def worker():
            detections = self.detector.detect(self.cur_img_path)
            self.detection_done.emit(detections)

        threading.Thread(target=worker, daemon=True).start()

    def _apply_detections(self, detections: list[Detection]):
        self.status_message.setText(f"Found {len(detections)} regions")
        scene = self.viewer.scene()
        for det in detections:
            kind = "bubble" if det.cls == 0 else "free-text"
            width, height = det.xywh[2], det.xywh[3]

            rect = MoveableRectItem(QRectF(0, 0, width, height), kind=kind)
            rect.setPos(QPointF(det.xyxy[0], det.xyxy[1]))
            rect.setZValue(1)

            self.viewer.scene().addItem(rect)
            self._add_bubble(rect)

        scene.update()
        self.viewer.viewport().update()

    def _wait_ocr_ready(self):
        self.ocr_engine.wait_until_ready()

        # Notify user
        self.status_message.setText(f"OCR loaded in {time.time() - self.model_start:.2f} seconds")

    def on_run_ocr(self):
        li = self.bubble_list.currentItem()
        if not li:
            QMessageBox.warning(self, "OCR", "No bubble selected.")
            return

        # find the rect
        rect_item = next(r for (i, r) in self._rect_list if i is li)

        if not self.ocr_engine.ready():
            QMessageBox.information(self, "OCR", "Model still loading...")
            return

        # grab the crop
        scene_rect = rect_item.sceneBoundingRect()
        img_crop = self.viewer.crop_region(scene_rect)
        if img_crop is None or img_crop.size == 0:
            QMessageBox.warning(self, "OCR", "Failed to crop image.")
            return

        self.status_message.setText("Running OCR...")

        # run in background
        def worker():
            text = self.ocr_engine.recognize(img_crop)
            self.ocr_done.emit(rect_item, text)

        threading.Thread(target=worker, daemon=True).start()

    def on_run_ocr_all(self):
        if not self._rect_list:
            QMessageBox.information(self, "OCR All", "There are no bubbles to OCR.")
            return

        self.status_message.setText("Running OCR on all bubbles…")

        def worker():
            total = len(self._rect_list)
            for idx, (li, rect) in enumerate(self._rect_list, start=1):
                # crop the region and call OCR
                img_crop = self.viewer.crop_region(rect.sceneBoundingRect())
                if img_crop is None or img_crop.size == 0:
                    continue
                text = self.ocr_engine.recognize(img_crop)
                # send back to main thread
                self.ocr_done.emit(rect, text)
                # progress update
                self.status_message.setText(f"OCR all: {idx}/{total}")
            self.status_message.setText("OCR all complete")

        Thread(target=worker, daemon=True).start()

    def _on_ocr_done(self, rect_item, text):
        rect_item.ocr_text = text

        current = self.bubble_list.currentItem()
        if current:
            for li, r in self._rect_list:
                if li is current and r is rect_item:
                    self.ocr_output.setPlainText(text)
                    break
        self.status_message.setText("OCR complete")
    # endregion
    # region Helpers & Internals
    def _load_settings(self):
        settings = QSettings("MyCompany", "Kara")

        if settings.contains("geometry"):
            self.restoreGeometry(settings.value("geometry"))

        # Restore main splitter sizes
        if settings.contains("mainSplitterSizes"):
            sizes = settings.value("mainSplitterSizes")
            self.splitter.setSizes([int(s) for s in sizes])

        # Restore annotation splitter sizes
        if settings.contains("annSplitterSizes"):
            sizes = settings.value("annSplitterSizes")
            self.ann_split.setSizes([int(s) for s in sizes])

    def _save_settings(self):
        settings = QSettings("MyCompany", "Kara")

        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("mainSplitterSizes", self.splitter.sizes())
        settings.setValue("annSplitterSizes", self.ann_split.sizes())

    def _add_bubble(self, rect_item: MoveableRectItem) -> Optional[QListWidgetItem]:
        if not isinstance(rect_item, MoveableRectItem):
            return None

        # if this rect is registered already we ball
        if any(r is rect_item for _, r in self._rect_list):
            return None

        kind = rect_item.kind
        existing = [r for _, r in self._rect_list if r.kind == kind]
        label = "Bubble" if kind == "bubble" else "Free Text"
        text = f"{label} {len(existing) + 1}"

        li = QListWidgetItem(text)
        li.setFlags(li.flags() | Qt.ItemIsUserCheckable)
        li.setCheckState(Qt.Checked if rect_item.done else Qt.Unchecked)
        li.setData(Qt.UserRole, rect_item)
        self._rect_list.append((li, rect_item))

        scene_rect = rect_item.sceneBoundingRect()
        self._last_geom[rect_item] = scene_rect

        # connect geometry‐change signals
        rect_item.signals.rectangle_changed.connect(
            lambda new_rect, item=rect_item: self._on_rect_changed(item, new_rect)
        )

        self.bubble_list.addItem(li)
        self._update_progress()

        # connect done_changed
        rect_item.signals.done_changed.connect(
            lambda done, list_item=li: list_item.setCheckState(Qt.Checked if done else Qt.Unchecked)
        )
        # connect delete
        rect_item.signals.delete_block.connect(
            functools.partial(self._remove_bubble_for, rect_item)
        )
        self.bubble_list.itemChanged.connect(self._on_list_done_toggled)
        return li

    def _remove_bubble(self, idx: int):
        li, rect = self._rect_list.pop(idx)

        self.viewer.scene().removeItem(rect)
        self.bubble_list.takeItem(self.bubble_list.row(li))
        self._update_progress()

    def _remove_bubble_for(self, rect: MoveableRectItem):
        # find the index and remove it
        for idx, (li, r) in enumerate(self._rect_list):
            if r is rect:
                self._remove_bubble(idx)
                return

    def clear_bubbles(self):
        for _, rect in self._rect_list:
            self.viewer.scene().removeItem(rect)
        self.bubble_list.clear()
        self._rect_list.clear()

    def _renumber_bubbles(self):
        counts = {"bubble": 0, "free-text": 0}
        for i in range(self.bubble_list.count()):
            li = self.bubble_list.item(i)
            rect = li.data(Qt.UserRole)
            counts[rect.kind] += 1
            base = "Bubble" if rect.kind == "bubble" else "Free-text"
            li.setText(f"{base} {counts[rect.kind]}")

    def _toggle_done_selected(self):
        li = self.bubble_list.currentItem()
        if not li:
            return

        new_state = Qt.Unchecked if li.checkState() == Qt.Checked else Qt.Checked
        li.setCheckState(new_state)

    def _select_tool(self, tool_name: str):
        for btn in self.tool_group.buttons():
            if btn.text().lower() == tool_name.lower():
                btn.setChecked(True)
                self.on_tool_selected(btn)
                break

    @property
    def _property_widgets(self) -> list[QWidget]:
        return [
            self.kind_combo, self.x_spin, self.y_spin,
            self.w_spin, self.h_spin,
            self.ocr_output, self.trans_edit
        ]

    def _set_property_fields_enabled(self, enabled: bool):
        for w in self._property_widgets:
            w.setEnabled(enabled)

    def _mark_dirty(self):
        if not self._dirty:
            self._dirty = True
            self._update_title()
            self.status_message.setText("Modified, unsaved changes")

    def _update_title(self):
        base = "Kara " + self.cur_img_path.name if self.cur_img_path else ""
        star = "* " if self._dirty else ""
        self.setWindowTitle(f"{base}{star}")

    def _update_progress(self):
        total = len(self._rect_list)
        done = sum(1 for _, r in self._rect_list if r.done)
        # avoid zero-division
        if total == 0:
            self.progress.setMaximum(1)
            self.progress.setValue(0)
        else:
            self.progress.setMaximum(total)
            self.progress.setValue(done)
    # endregion
    # region Event overrides
    def resizeEvent(self, event):
        super().resizeEvent(event)
        tb = self.toolbar_frame
        x = (self.width() - tb.width()) // 2
        y = self.height() - tb.height() - self.statusBar().height() - 10
        tb.move(x, y)
        tb.raise_()

    def closeEvent(self, event):
        self._save_settings()
        super().closeEvent(event)
    # endregion


if __name__ == "__main__":
    app = QApplication(sys.argv)

    w = MainWindow()
    w.show()

    sys.exit(app.exec())
