from datetime import datetime
from enum import Enum
from pynput import keyboard, mouse
import logging
from queue import Queue, Empty as EmptyException

# Allowed keys in chord output: a-z, A-Z, 0-9, apostrophe, dash, underscore, slash, backslash, tilde
ALLOWED_KEYS_IN_CHORD = [chr(i) for i in range(97, 123)] + [chr(i) for i in range(65, 91)] + \
                        [chr(i) for i in range(48, 58)] + ["'", "-", "_", "/", "\\", "~"]
MODIFIER_KEYS = [keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r, keyboard.Key.alt, keyboard.Key.alt_l,
                 keyboard.Key.alt_r, keyboard.Key.alt_gr, keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r]
NEW_WORD_THRESHOLD = 5  # seconds after which character input is considered a new word

logging.basicConfig(filename="log.txt", level=logging.DEBUG, format="%(asctime)s - %(message)s")
q = Queue()


class ActionType(Enum):
    """Enum for key action type"""
    PRESS = 1
    RELEASE = 2


def on_press(key):
    """Store PRESS, key and current time in queue"""
    q.put((ActionType.PRESS, key, datetime.now()))


def on_release(key):
    """"Store RELEASE, key and current time in queue"""
    q.put((ActionType.RELEASE, key, datetime.now()))


def on_click(x, y, button, pressed):
    """Store PRESS, key and current time in queue"""
    q.put((ActionType.PRESS, button, datetime.now()))


def log_word(word, start_time, end_time):
    """Log word to file"""
    logging.debug(f"{word} - {start_time} - {end_time}")


def main():
    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()
    mouse_listener = mouse.Listener(on_click=on_click)
    mouse_listener.start()

    word = ""  # word to be logged, reset on non-chord keys
    word_start_time = None
    word_end_time = None

    modifier_keys = set()

    def log_and_reset_word():
        """Log word to file and reset word metadata"""
        nonlocal word, word_start_time, word_end_time
        if word:
            if len(word) > 1:  # only log words with more than one character
                log_word(word, word_start_time, word_end_time)
            word = ""
            word_start_time = None
            word_end_time = None

    while True:
        try:
            action, key, time = q.get(block=False)

            # Update modifier keys
            if action == ActionType.PRESS and key in MODIFIER_KEYS:
                modifier_keys.add(key)
            elif action == ActionType.RELEASE and key in MODIFIER_KEYS:
                modifier_keys.remove(key)

            # Ignore non-modifier release events
            if action == ActionType.RELEASE:
                q.task_done()
                continue

            # On backspace, remove last char from word if word is not empty
            if key == keyboard.Key.backspace and word:
                word = word[:-1]
                q.task_done()
                continue

            # On non-chord key, log and reset word if it exists
            if not (isinstance(key, keyboard.KeyCode) and key.char in ALLOWED_KEYS_IN_CHORD):
                if word:
                    log_and_reset_word()
                q.task_done()
                continue

            # Add new char to word and update word timing if no modifier keys are pressed
            if not modifier_keys:
                word += key.char
                if not word_start_time:
                    word_start_time = time
                word_end_time = time
                q.task_done()
        except EmptyException:  # queue is empty
            # If word is older than NEW_WORD_THRESHOLD seconds, log and reset word
            if word and (datetime.now() - word_end_time).total_seconds() > NEW_WORD_THRESHOLD:
                log_and_reset_word()


if __name__ == '__main__':
    main()
