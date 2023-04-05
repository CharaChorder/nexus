import argparse
import logging
import signal

from pynput import keyboard

import Freqlog
from Freqlog.Definitions import BanlistAttr, ChordMetadataAttr, Defaults, WordMetadataAttr

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Freqlog chentered words")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    parser.add_argument("-l", "--log-level", default="INFO", help="Log level",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR", "NONE"])

    # Common arguments
    path_arg = argparse.ArgumentParser(add_help=False)
    path_arg.add_argument("--freq-log-path", default=f"{Defaults.DEFAULT_DB_PATH}", help="Backend to use")
    case_arg = argparse.ArgumentParser(add_help=False)
    case_arg.add_argument("-c", "--case", default="firstchar", help="Case sensitivity",
                          choices=["sensitive", "insensitive", "firstchar"])
    num_arg = argparse.ArgumentParser(add_help=False)
    num_arg.add_argument("-n", "--num", default=10, help="Number of words to return")
    reverse_arg = argparse.ArgumentParser(add_help=False)
    reverse_arg.add_argument("-r", "--reverse", action="store_true", help="Reverse order of words")

    # Start freqlogging
    parser_start = subparsers.add_parser("startlog", help="Start logging", parents=[path_arg])
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

    # Word frequency
    parser_get = subparsers.add_parser("word", help="Get words' frequency", parents=[path_arg, case_arg])
    parser_get.add_argument("word", help="Word(s) to get frequency of", nargs="+")

    # Chord frequency
    parser_get = subparsers.add_parser("chord", help="Get chords' frequency", parents=[path_arg])
    parser_get.add_argument("chord", help="Chord(s) to get frequency of", nargs="+")

    # Check ban
    parser_check = subparsers.add_parser("checkword", help="Check if a word is banned", parents=[path_arg, case_arg])
    parser_check.add_argument("word", help="Word(s) to check", nargs="+")

    # Ban
    parser_ban = subparsers.add_parser("banword", help="Ban a word", parents=[path_arg, case_arg])
    parser_ban.add_argument("word", help="Word(s) to ban", nargs="+")

    # Unban
    parser_unban = subparsers.add_parser("unbanword", help="Unban a word", parents=[path_arg, case_arg])
    parser_unban.add_argument("word", help="Word(s) to unban", nargs="+")

    # Get words
    parser_words = subparsers.add_parser("words", help="Get list of stored words",
                                         parents=[path_arg, case_arg, num_arg, reverse_arg])
    parser_words.add_argument("-s", "--sort-by", default="frequency", help="Sort by",
                              choices={attr.name for attr in WordMetadataAttr})

    # Get chords
    parser_chords = subparsers.add_parser("chords", help="Get list of stored chords",
                                          parents=[path_arg, case_arg, num_arg, reverse_arg])
    parser_chords.add_argument("-s", "--sort-by", default="frequency", help="Sort by",
                               choices={attr.name for attr in ChordMetadataAttr})

    # Get banned words
    parser_banned = subparsers.add_parser("bannedwords", help="Get banned words",
                                          parents=[path_arg, num_arg, reverse_arg])
    parser_banned.add_argument("-s", "--sort-by", default="dateadded", help="Sort by",
                               choices={attr.name for attr in BanlistAttr})
    parser_stop = subparsers.add_parser("stoplog", help="Stop logging")
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
        exit(0)

    # Validate arguments
    if args.command == "startlog":
        try:  # ensure that path is writable
            with open(args.freq_log_path, "w") as f:
                pass
        except OSError as e:
            print(f"Error: {e}")
            exit(1)
        if args.new_word_threshold <= 0:
            print("Error: New word threshold must be greater than 0")
            exit(1)
        if args.chord_char_threshold <= 0:
            print("Error: Chord character threshold must be greater than 0")
            exit(1)
        if len(args.allowed_keys_in_chord) == 0:
            print("Error: Must allow at least one key in chord")
            exit(1)

    # Parse commands
    if args.command == "stoplog":  # stop freqlogging
        # Kill freqlogging process
        raise NotImplementedError  # TODO implement

    freqlog = Freqlog.Freqlog(args.freq_log_path)
    if args.command == "startlog":  # start freqlogging
        signal.signal(signal.SIGINT, lambda *_: freqlog.stop_logging())
        freqlog.start_logging(args.new_word_threshold, args.chord_char_threshold, args.allowed_keys_in_chord,
                              Defaults.DEFAULT_MODIFIER_KEYS - set(args.remove_modifier_key) | set(
                                  args.add_modifier_key))
    elif args.command == "word":  # get word frequency
        print(freqlog.get_word_metadata(args.word, args.case))
    elif args.command == "chord":  # get chord frequency
        print(freqlog.get_chord_metadata(args.chord))
    elif args.command == "checkword":  # check if word is banned
        print(freqlog.check_banned(args.word, args.case))
    elif args.command == "banword":  # ban word
        freqlog.ban_word(args.word, args.case)
    elif args.command == "unbanword":  # unban word
        freqlog.unban_word(args.word, args.case)
    elif args.command == "words":  # get words
        print(freqlog.list_words(args.number, args.case, args.reverse, args.sort_by))
        # TODO pretty print
    elif args.command == "chords":  # get chords
        print(freqlog.list_chords(args.number, args.case, args.reverse, args.sort_by))
        # TODO pretty print
    elif args.command == "bannedwords":  # get banned words
        print(freqlog.list_banned_words(args.number, args.reverse, args.sort_by))
        # TODO pretty print
