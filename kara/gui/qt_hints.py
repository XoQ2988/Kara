from PySide6.QtCore import Qt as _Qt
from PySide6.QtGui import QImage as _QImage
from PySide6.QtWidgets import QFrame as _QFrame, QGraphicsItem as _QGraphicsItem
from PySide6.QtWidgets import QGraphicsView as _QGraphicsView
from PySide6.QtWidgets import QSizePolicy as _QSizePolicy


class Qt(_Qt):
    # Orientation
    Horizontal: _Qt.Orientation
    Vertical: _Qt.Orientation

    # Alignment
    AlignLeft: _Qt.AlignmentFlag
    AlignRight: _Qt.AlignmentFlag
    AlignTop: _Qt.AlignmentFlag
    AlignBottom: _Qt.AlignmentFlag
    AlignCenter: _Qt.AlignmentFlag

    # Layout Direction
    LeftToRight: _Qt.LayoutDirection
    RightToLeft: _Qt.LayoutDirection

    # ToolButtonStyle
    ToolButtonIconOnly: _Qt.ToolButtonStyle
    ToolButtonTextOnly: _Qt.ToolButtonStyle
    ToolButtonTextBesideIcon: _Qt.ToolButtonStyle
    ToolButtonTextUnderIcon: _Qt.ToolButtonStyle
    ToolButtonFollowStyle: _Qt.ToolButtonStyle

    # CursorShape
    ArrowCursor: _Qt.CursorShape
    UpArrowCursor: _Qt.CursorShape
    CrossCursor: _Qt.CursorShape
    WaitCursor: _Qt.CursorShape
    IBeamCursor: _Qt.CursorShape
    SizeVerCursor: _Qt.CursorShape
    SizeHorCursor: _Qt.CursorShape
    SizeBDiagCursor: _Qt.CursorShape
    SizeFDiagCursor: _Qt.CursorShape
    SizeAllCursor: _Qt.CursorShape
    BlankCursor: _Qt.CursorShape
    SplitVCursor: _Qt.CursorShape
    SplitHCursor: _Qt.CursorShape
    PointingHandCursor: _Qt.CursorShape
    ForbiddenCursor: _Qt.CursorShape
    WhatsThisCursor: _Qt.CursorShape
    BusyCursor: _Qt.CursorShape
    OpenHandCursor: _Qt.CursorShape
    ClosedHandCursor: _Qt.CursorShape
    DragCopyCursor: _Qt.CursorShape
    DragMoveCursor: _Qt.CursorShape
    DragLinkCursor: _Qt.CursorShape

    # MouseButton
    NoButton: _Qt.MouseButton
    LeftButton: _Qt.MouseButton
    RightButton: _Qt.MouseButton
    MiddleButton: _Qt.MouseButton
    BackButton: _Qt.MouseButton
    ForwardButton: _Qt.MouseButton
    TaskButton: _Qt.MouseButton
    ExtraButton4: _Qt.MouseButton
    ExtraButton5: _Qt.MouseButton
    ExtraButton6: _Qt.MouseButton
    ExtraButton7: _Qt.MouseButton
    ExtraButton8: _Qt.MouseButton
    ExtraButton9: _Qt.MouseButton
    ExtraButton10: _Qt.MouseButton
    ExtraButton11: _Qt.MouseButton
    ExtraButton12: _Qt.MouseButton
    ExtraButton13: _Qt.MouseButton
    ExtraButton14: _Qt.MouseButton
    ExtraButton15: _Qt.MouseButton
    ExtraButton16: _Qt.MouseButton
    ExtraButton17: _Qt.MouseButton
    ExtraButton18: _Qt.MouseButton
    ExtraButton19: _Qt.MouseButton
    ExtraButton20: _Qt.MouseButton
    ExtraButton21: _Qt.MouseButton
    ExtraButton22: _Qt.MouseButton
    ExtraButton23: _Qt.MouseButton
    ExtraButton24: _Qt.MouseButton

    # KeyboardModifier
    NoModifier: _Qt.KeyboardModifier
    ShiftModifier: _Qt.KeyboardModifier
    ControlModifier: _Qt.KeyboardModifier
    AltModifier: _Qt.KeyboardModifier
    MetaModifier: _Qt.KeyboardModifier
    KeypadModifier: _Qt.KeyboardModifier
    GroupSwitchModifier: _Qt.KeyboardModifier

    # AspectRatioMode
    IgnoreAspectRatio: _Qt.AspectRatioMode
    KeepAspectRatio: _Qt.AspectRatioMode
    KeepAspectRatioByExpanding: _Qt.AspectRatioMode

    # PenStyle
    NoPen: _Qt.PenStyle
    SolidLine: _Qt.PenStyle
    DashLine: _Qt.PenStyle
    DotLine: _Qt.PenStyle
    DashDotLine: _Qt.PenStyle
    DashDotDotLine: _Qt.PenStyle
    CustomDashLine: _Qt.PenStyle

    # User Role for models
    UserRole: _Qt.ItemDataRole

    # ItemFlags
    ItemIsUserCheckable: _Qt.ItemFlag

    # CheckState
    Checked: _Qt.CheckState
    Unchecked: _Qt.CheckState



class QImage(_QImage):
    Format_Invalid: _QImage.Format
    Format_Mono: _QImage.Format
    Format_MonoLSB: _QImage.Format
    Format_Indexed8: _QImage.Format
    Format_RGB32: _QImage.Format
    Format_ARGB32: _QImage.Format
    Format_ARGB32_Premultiplied: _QImage.Format
    Format_RGB16: _QImage.Format
    Format_ARGB8565_Premultiplied: _QImage.Format
    Format_BGR888: _QImage.Format
    Format_RGB888: _QImage.Format
    Format_Grayscale8: _QImage.Format


class QFrame(_QFrame):
    NoFrame: _QFrame.Shape
    Box: _QFrame.Shape
    Panel: _QFrame.Shape
    StyledPanel: _QFrame.Shape
    HLine: _QFrame.Shape
    VLine: _QFrame.Shape
    WinPanel: _QFrame.Shape
    Plain: _QFrame.Shadow
    Raised: _QFrame.Shadow
    Sunken: _QFrame.Shadow

class QGraphicsView(_QGraphicsView):
    NoDrag: _QGraphicsView.DragMode
    ScrollHandDrag: _QGraphicsView.DragMode
    RubberBandDrag: _QGraphicsView.DragMode

class QSizePolicy(_QSizePolicy):
    Fixed: _QSizePolicy.Policy
    Minimum: _QSizePolicy.Policy
    Maximum: _QSizePolicy.Policy
    Preferred: _QSizePolicy.Policy
    Expanding: _QSizePolicy.Policy
    MinimumExpanding: _QSizePolicy.Policy
    Ignored: _QSizePolicy.Policy

class QGraphicsItem(_QGraphicsItem):
    ItemIsMovable: _QGraphicsItem.GraphicsItemFlag
    ItemIsSelectable: _QGraphicsItem.GraphicsItemFlag
    ItemIsFocusable: _QGraphicsItem.GraphicsItemFlag
    ItemClipsToShape: _QGraphicsItem.GraphicsItemFlag
    ItemClipsChildrenToShape: _QGraphicsItem.GraphicsItemFlag
    ItemIgnoresTransformations: _QGraphicsItem.GraphicsItemFlag
    ItemIgnoresParentOpacity: _QGraphicsItem.GraphicsItemFlag
    ItemDoesntPropagateOpacityToChildren: _QGraphicsItem.GraphicsItemFlag
    ItemStacksBehindParent: _QGraphicsItem.GraphicsItemFlag
    ItemUsesExtendedStyleOption: _QGraphicsItem.GraphicsItemFlag
    ItemHasNoContents: _QGraphicsItem.GraphicsItemFlag
    ItemSendsGeometryChanges: _QGraphicsItem.GraphicsItemFlag
    ItemAcceptsInputMethod: _QGraphicsItem.GraphicsItemFlag

