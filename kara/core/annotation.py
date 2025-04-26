import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Tuple

from PySide6.QtCore import Signal, QObject


@dataclass
class AnnotationData:
    """
    Represents one speech‐bubble (or free‐text) annotation.
    """
    rect: Tuple[float, float, float, float]
    kind: str = "bubble"
    done: bool = False
    ocr: str = ""
    translation: str = ""

class AnnotationController(QObject):
    """
    Manages a collection of Annotation objects, handles load/save,
    and emits signals on any change so the UI can react.
    """

    annotations_loaded   = Signal(Path, list)         # emits List[Annotation]
    annotations_saved    = Signal(Path)         # emits the Path we just saved to
    bubble_added         = Signal(AnnotationData)   # emits the new Annotation
    bubble_removed       = Signal(int)          # emits the Annotation.id that was removed
    bubble_updated       = Signal(AnnotationData)   # emits the Annotation that changed
    annotations_cleared  = Signal()             # emits when we clear all

    def __init__(self, parent=None):
        super().__init__(parent)
        self.annotations: List[AnnotationData] = []
        self._path: Optional[Path] = None

    @staticmethod
    def _annotation_file_for(image_path: Path) -> Path:
        ann_dir = image_path.parent / ".kara"
        ann_dir.mkdir(exist_ok=True)
        return ann_dir / f"{image_path.stem}.json"

    def load(self, image_path: Path) -> None:
        """Load annotations from disk (or emit an empty list if none exist)."""
        ann_file = self._annotation_file_for(image_path)

        if not ann_file.exists():
            # no annotations yet → emit empty list
            self.annotations_loaded.emit(image_path, [])
            return

        try:
            raw = json.loads(ann_file.read_text(encoding="utf-8"))
            entries = raw.get("bubbles", [])
            ann_list = [
                AnnotationData(
                    rect=entry["rect"],
                    kind=entry.get("kind", "bubble"),
                    done=entry.get("done", False),
                    ocr=entry.get("ocr", ""),
                    translation=entry.get("translation", "")
                )
                for entry in entries
            ]
        except Exception as e:
            # if parsing fails, you might want to log & emit empty
            print(f"Failed to parse {ann_file}: {e}")
            ann_list = []

        self.annotations_loaded.emit(image_path, ann_list)

    def save(self,
             image_path: Path,
             annotations: List[AnnotationData]) -> None:
        """
        Persist the given list of AnnotationData to disk next to `image_path`.
        Emits `annotations_saved(image_path)` on success.
        """
        ann_file = self._annotation_file_for(image_path)
        payload = {
            "bubbles": [
                {
                    "rect":         ann.rect,
                    "kind":         ann.kind,
                    "done":         ann.done,
                    "ocr":          ann.ocr,
                    "translation":  ann.translation
                }
                for ann in annotations
            ]
        }

        try:
            ann_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                                encoding="utf-8")
            self.annotations_saved.emit(image_path)
        except Exception as e:
            print(f"Failed to save {ann_file}: {e}")

    def add(self, ann: AnnotationData) -> None:
        """Register a new bubble and emit its signal."""
        self.annotations.append(ann)
        self.bubble_added.emit(ann)

    def remove(self, bubble_id: int) -> None:
        """Remove by ID."""
        idx = next((i for i,a in enumerate(self.annotations) if a.id == bubble_id), None)
        if idx is not None:
            del self.annotations[idx]
            self.bubble_removed.emit(bubble_id)

    def update(self, ann: AnnotationData) -> None:
        """
        Called when a bubble’s geometry or metadata changes.
        """
        self.bubble_updated.emit(ann)

    def clear(self) -> None:
        """Discard all in-memory annotations."""
        self.annotations.clear()
        self.annotations_cleared.emit()
