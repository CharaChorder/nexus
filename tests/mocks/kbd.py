from enum import Enum


class Key(Enum):
    """Enum for key names"""
    alt = 0
    alt_l = 0
    alt_r = 0
    alt_gr = 0
    backspace = 0
    caps_lock = 0
    cmd = 0
    cmd_l = 0
    cmd_r = 0
    ctrl = 0
    ctrl_l = 0
    ctrl_r = 0
    delete = 0
    down = 0
    end = 0
    enter = 0
    esc = 0
    f1 = 0
    f2 = 0
    f3 = 0
    f4 = 0
    f5 = 0
    f6 = 0
    f7 = 0
    f8 = 0
    f9 = 0
    f10 = 0
    f11 = 0
    f12 = 0
    f13 = 0
    f14 = 0
    f15 = 0
    f16 = 0
    f17 = 0
    f18 = 0
    f19 = 0
    f20 = 0
    home = 0
    left = 0
    page_down = 0
    page_up = 0
    right = 0
    shift = 0
    shift_l = 0
    shift_r = 0
    space = 0
    tab = 0
    up = 0
    media_play_pause = 0
    media_volume_mute = 0
    media_volume_down = 0
    media_volume_up = 0
    media_previous = 0
    media_next = 0
    insert = 0
    menu = 0
    num_lock = 0
    pause = 0
    print_screen = 0
    scroll_lock = 0


class KeyCode:
    pass


class Listener:
    def __init__(self, *args, **kwargs):
        pass
