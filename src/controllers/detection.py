import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, TYPE_CHECKING, Union

if TYPE_CHECKING:
    from ultralytics import YOLO


@dataclass
class Detection:
    cls: int
    conf: float
    xyxy: tuple[float, float, float, float]
    xywh: tuple[float, float, float, float]


class SpeechBubbleDetector:
    def __init__(self, model_path: Path) -> None:
        self.model_path = model_path
        self._model: Optional["YOLO"] = None
        self._ready = threading.Event()

        thread = threading.Thread(target=self._load_model, daemon=True)
        thread.start()

    def _load_model(self) -> None:
        # dynamic import so module-load doesn't stall
        from ultralytics import YOLO
        self._model = YOLO(self.model_path)
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

    def detect(self, image_path: Union[Path, str], *, min_conf: float = 0.0):
        if not self.ready():
            raise RuntimeError("SpeechBubbleDetector: Model not ready")

        results = self._model(str(image_path))[0]

        detections: List[Detection] = []
        for box in results.boxes:
            conf = float(box.conf.cpu().item())
            if conf < min_conf:
                continue

            cls_idx = int(box.cls.cpu().item())

            # convert torch→numpy→Python floats
            xyxy = box.xyxy.cpu().numpy().reshape(4).tolist()
            xywh = box.xywh.cpu().numpy().reshape(4).tolist()

            detections.append(
                Detection(
                    cls=cls_idx,
                    conf=conf,
                    xyxy=(xyxy[0], xyxy[1], xyxy[2], xyxy[3]),
                    xywh=(xywh[0], xywh[1], xywh[2], xywh[3]),
                )
            )

        return detections


if __name__ == '__main__':
    img_path = Path.cwd().parent.parent / "example.jpg"
    mdl_path = Path.cwd().parent.parent / "model" / "comic-speech-bubble-detector.pt"

    detector = SpeechBubbleDetector(mdl_path)
    detector.wait_until_ready()
    result = detector.detect(img_path)
    for bbox in result:
        print(bbox)
