"""Small ctypes helpers for Win32 window styles and DPI awareness.

No pywin32 dependency needed - everything here is plain user32/shcore calls.
"""
import ctypes

user32 = ctypes.windll.user32
shcore = ctypes.windll.shcore

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080

HWND_TOPMOST = -1
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOACTIVATE = 0x0010


def enable_dpi_awareness():
    try:
        shcore.SetProcessDpiAwareness(2)  # PER_MONITOR_AWARE
    except Exception:
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass


def _get_ex_style(hwnd) -> int:
    return user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)


def _set_ex_style(hwnd, style: int):
    user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, style)


def make_click_through(hwnd, click_through: bool):
    style = _get_ex_style(hwnd) | WS_EX_LAYERED | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW
    if click_through:
        style |= WS_EX_TRANSPARENT
    else:
        style &= ~WS_EX_TRANSPARENT
    _set_ex_style(hwnd, style)


def make_noactivate_tool_window(hwnd):
    style = _get_ex_style(hwnd) | WS_EX_LAYERED | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW
    _set_ex_style(hwnd, style)


def force_topmost(hwnd):
    user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
