import argparse
import logging
import signal
import sys

from pynput import keyboard

import Freqlog
from Freqlog.Definitions import BanlistAttr, ChordMetadataAttr, Defaults, WordMetadataAttr

if __name__ == "__main__":
    log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "NONE"]

    # Common arguments
    log_arg = argparse.ArgumentParser(add_help=False)
    log_arg.add_argument("-l", "--log-level", default="INFO", help=f"One of {log_levels}",
                         metavar="level", choices=log_levels)
    path_arg = argparse.ArgumentParser(add_help=False)
    path_arg.add_argument("--freq-log-path", default=f"{Defaults.DEFAULT_DB_PATH}", help="Backend to use")
    case_arg = argparse.ArgumentParser(add_help=False)
    case_arg.add_argument("-c", "--case", default="firstchar", help="Case sensitivity",
                          choices=["sensitive", "insensitive", "firstchar"])
    num_arg = argparse.ArgumentParser(add_help=False)
    num_arg.add_argument("-n", "--num", default=10, help="Number of words to return")
    reverse_arg = argparse.ArgumentParser(add_help=False)
    reverse_arg.add_argument("-r", "--reverse", action="store_true", help="Reverse order of words")

    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Freqlog chentered words", parents=[log_arg])
    subparsers = parser.add_subparsers(dest="command", title="Commands")

    # Start freqlogging
    parser_start = subparsers.add_parser("startlog", help="Start logging", parents=[log_arg, path_arg])
    parser_start.add_argument("--new-word-threshold", default=f"{Defaults.DEFAULT_NEW_WORD_THRESHOLD}", type=float,
                              help="Time in seconds after which character input is considered a new word")
    parser_start.add_argument("--chord-char-threshold", default=f"{Defaults.DEFAULT_CHORD_CHAR_THRESHOLD}", type=int,
                              help="Time in milliseconds between characters in a chord to be considered a chord")
    parser_start.add_argument("--allowed-keys-in-chord", default=f"{Defaults.DEFAULT_ALLOWED_KEYS_IN_CHORD}",
                              help="Allowed keys in chord output")
    parser_start.add_argument("--add-modifier-key", action="append", default=[],
                              help="Add a modifier key to the default set",
                              choices={key.name for key in set(keyboard.Key) - Defaults.DEFAULT_MODIFIER_KEYS})
    parser_start.add_argument("--remove-modifier-key", action="append", default=[],
                              help="Remove a modifier key from the default set",
                              choices={key.name for key in Defaults.DEFAULT_MODIFIER_KEYS})

    # Get words
    parser_words = subparsers.add_parser("words", help="Get list of freqlogged words",
                                         parents=[log_arg, path_arg, case_arg, num_arg, reverse_arg])
    parser_words.add_argument("word", help="Word(s) to get data of", nargs="*")
    parser_words.add_argument("-s", "--sort-by", default="frequency", help="Sort by",
                              choices={attr.name for attr in WordMetadataAttr})

    # Get chords
    parser_chords = subparsers.add_parser("chords", help="Get list of stored freqlogged",
                                          parents=[log_arg, path_arg, num_arg, reverse_arg])
    parser_chords.add_argument("chord", help="Chord(s) to get data of", nargs="*")
    parser_chords.add_argument("-s", "--sort-by", default="frequency", help="Sort by",
                               choices={attr.name for attr in ChordMetadataAttr})

    # Get banned words
    parser_banned = subparsers.add_parser("banlist", help="Get list of banned words",
                                          parents=[log_arg, path_arg, num_arg, reverse_arg])
    parser_banned.add_argument("-s", "--sort-by", default="dateadded", help="Sort by",
                               choices={attr.name for attr in BanlistAttr})

    # Check ban
    parser_check = subparsers.add_parser("checkword", help="Check if a word is banned",
                                         parents=[log_arg, path_arg, case_arg])
    parser_check.add_argument("word", help="Word(s) to check", nargs="+")

    # Ban
    parser_ban = subparsers.add_parser("banword", help="Ban a word", parents=[log_arg, path_arg, case_arg])
    parser_ban.add_argument("word", help="Word(s) to ban", nargs="+")

    # Unban
    parser_unban = subparsers.add_parser("unbanword", help="Unban a word", parents=[log_arg, path_arg, case_arg])
    parser_unban.add_argument("word", help="Word(s) to unban", nargs="+")

    # Stop freqlogging
    parser_stop = subparsers.add_parser("stoplog", help="Stop logging", parents=[log_arg])
    # parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args()

    # Set up console logging
    if args.log_level == "NONE":
        logging.disable(logging.CRITICAL)
    else:
        logging.basicConfig(level=args.log_level, format="%(asctime)s - %(message)s")

    # Print help if no command is given
    if args.command is None:
        parser.print_help()
        sys.exit(0)

    # Validate arguments
    if args.command == "startlog":
        try:  # ensure that path is writable
            with open(args.freq_log_path, "w") as f:
                pass
        except OSError as e:
            print(f"Error: {e}")
            sys.exit(1)
        if args.new_word_threshold <= 0:
            print("Error: New word threshold must be greater than 0")
            sys.exit(1)
        if args.chord_char_threshold <= 0:
            print("Error: Chord character threshold must be greater than 0")
            sys.exit(1)
        if len(args.allowed_keys_in_chord) == 0:
            print("Error: Must allow at least one key in chord")
            sys.exit(1)

    # Parse commands
    if args.command == "stoplog":  # stop freqlogging
        # Kill freqlogging process
        raise NotImplementedError  # TODO: implement

    freqlog = Freqlog.Freqlog(args.freq_log_path)
    if args.command == "startlog":  # start freqlogging
        signal.signal(signal.SIGINT, lambda *_: freqlog.stop_logging())
        freqlog.start_logging(args.new_word_threshold, args.chord_char_threshold, args.allowed_keys_in_chord,
                              Defaults.DEFAULT_MODIFIER_KEYS - set(args.remove_modifier_key) | set(
                                  args.add_modifier_key))
    elif args.command == "checkword":  # check if word is banned
        print(freqlog.check_banned(args.word, args.case))
    elif args.command == "banword":  # ban word
        freqlog.ban_word(args.word, args.case)
    elif args.command == "unbanword":  # unban word
        freqlog.unban_word(args.word, args.case)
    # TODO: pretty print
    # TODO: implement sort/num/reverse for specific words and chords
    elif args.command == "words":  # get words
        if len(args.word) == 0:
            print(freqlog.list_words(args.num, args.reverse, args.case, args.sort_by))
        else:
            for word in args.word:
                res = freqlog.get_word_metadata(word, args.case)
                if res is None:
                    print(f"Word '{word}' not found")
                else:
                    print(res)
    elif args.command == "chords":  # get chords
        if len(args.chord) == 0:
            print(freqlog.list_chords(args.num, args.reverse, args.case, args.sort_by))
        else:
            for chord in args.chord:
                res = freqlog.get_chord_metadata(chord)
                if res is None:
                    print(f"Chord '{chord}' not found")
                else:
                    print(res)
    elif args.command == "banlist":  # get banned words
        print(freqlog.list_banned_words(args.num, args.reverse, args.sort_by))
