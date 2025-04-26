from PySide6.QtGui import QUndoCommand

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
