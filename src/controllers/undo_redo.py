from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QUndoStack, QUndoCommand


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
