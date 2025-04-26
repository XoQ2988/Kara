import threading
from pathlib import Path
from typing import Optional, Union, TYPE_CHECKING

import numpy as np
from PIL import Image

if TYPE_CHECKING:
    from manga_ocr import MangaOcr


class OCREngine:
    def __init__(self) -> None:
        self._ocr: Optional["MangaOcr"] = None
        self._ready = threading.Event()
        threading.Thread(target=self._load, daemon=True).start()

    def _load(self) -> None:
        # dynamic import so module-load doesn't stall
        from manga_ocr import MangaOcr
        self._ocr = MangaOcr()
        self._ready.set()

    def ready(self) -> bool:
        """True once the OCR model has finished loading"""
        return self._ready.is_set()

    def wait_until_ready(self, timeout: Optional[float] = None) -> bool:
        """
            Block until the model loads (or until timeout)

        :param timeout: If present, waits time
        :return: True if loaded.
        """
        return self._ready.wait(timeout)

    def recognize(self, img_or_path: Union[np.ndarray, Image.Image, Path, str]) -> str:
        """
            Perform OCR on the given input

        :param img_or_path: a numpy array, a PIL.Image, a pathlib.Path or a file path.
        :return: the recognized text
        :raises RuntimeError: if called before model is ready.
        :raises ValueError: if input type is unsupported.
        """
        if not self.ready():
            raise RuntimeError("OCREngine: model not ready")

        # load from disk
        if isinstance(img_or_path, str) or isinstance(img_or_path, Path):
            image = Image.open(str(img_or_path))

        # numpy to PIL
        elif isinstance(img_or_path, np.ndarray):
            rgb = img_or_path[..., ::-1]
            image = Image.fromarray(rgb)

        # already a PIL.Image
        elif isinstance(img_or_path, Image.Image):
            image = img_or_path
        else:
            raise ValueError(f"Unsupported type for OCR: {type(img_or_path)}")

        return self._ocr(image)


if __name__ == '__main__':
    img_path = Path.cwd().parent.parent / "example.jpg"

    detector = OCREngine()
    detector.wait_until_ready()
    result = detector.recognize(img_path)

    print(f"Detected text: \"{result}\"")
