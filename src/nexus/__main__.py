import argparse
import logging
import signal
import sys

from pynput import keyboard

from nexus import __doc__, __version__, Freqlog
from nexus.Freqlog.Definitions import BanlistAttr, CaseSensitivity, ChordMetadata, ChordMetadataAttr, Defaults, Order, \
    WordMetadata, \
    WordMetadataAttr


def main():
    """
    nexus CLI
    Exit codes:
        0: Success (including graceful keyboard interrupt) / word is not banned
        1: Forceful keyboard interrupt / word is banned
        2: Invalid command or argument
        3: Invalid value for argument
        4: Could not access or write to database
        5: Requested word or chord not found
        11: Python version < 3.11
        100: Feature not yet implemented
    """
    # Error and exit on Python version < 3.11
    if sys.version_info < (3, 11):
        print("Python 3.11 or higher is required")
        sys.exit(11)

    log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "NONE"]

    # Common arguments
    log_arg = argparse.ArgumentParser(add_help=False)
    log_arg.add_argument("-l", "--log-level", default="INFO", help=f"One of {log_levels}",
                         metavar="level", choices=log_levels)
    path_arg = argparse.ArgumentParser(add_help=False)
    path_arg.add_argument("--freq-log-path", default=Defaults.DEFAULT_DB_PATH, help="Backend to use")
    case_arg = argparse.ArgumentParser(add_help=False)
    case_arg.add_argument("-c", "--case", default=CaseSensitivity.FIRST_CHAR.name, help="Case sensitivity",
                          choices={case for case in CaseSensitivity})
    num_arg = argparse.ArgumentParser(add_help=False)
    num_arg.add_argument("-n", "--num", default=10, help="Number of words to return (0 for all)")

    # Parse command line arguments
    parser = argparse.ArgumentParser(description=__doc__, parents=[log_arg],
                                     epilog="Made with love by CharaChorder, source code available at "
                                            "https://github.com/CharaChorder/nexus")
    subparsers = parser.add_subparsers(dest="command", title="Commands")

    # Start freqlogging
    parser_start = subparsers.add_parser("startlog", help="Start logging", parents=[log_arg, path_arg])
    parser_start.add_argument("--new-word-threshold", default=Defaults.DEFAULT_NEW_WORD_THRESHOLD, type=float,
                              help="Time in seconds after which character input is considered a new word")
    parser_start.add_argument("--chord-char-threshold", default=Defaults.DEFAULT_CHORD_CHAR_THRESHOLD, type=int,
                              help="Time in milliseconds between characters in a chord to be considered a chord")
    parser_start.add_argument("--allowed-keys-in-chord", default=Defaults.DEFAULT_ALLOWED_KEYS_IN_CHORD,
                              help="Allowed keys in chord output")
    parser_start.add_argument("--add-modifier-key", action="append", default=[],
                              help="Add a modifier key to the default set",
                              choices={key.name for key in set(keyboard.Key) - Defaults.DEFAULT_MODIFIER_KEYS})
    parser_start.add_argument("--remove-modifier-key", action="append", default=[],
                              help="Remove a modifier key from the default set",
                              choices={key.name for key in Defaults.DEFAULT_MODIFIER_KEYS})

    # Get words
    parser_words = subparsers.add_parser("words", help="Get list of freqlogged words",
                                         parents=[log_arg, path_arg, case_arg, num_arg])
    parser_words.add_argument("word", help="Word(s) to get data of", nargs="*")
    parser_words.add_argument("-s", "--sort-by", default=WordMetadataAttr.frequency.name,
                              help=f"Sort by (default: {WordMetadataAttr.frequency.name})",
                              choices={attr.name for attr in WordMetadataAttr})
    parser_words.add_argument("-o", "--order", default=Order.DESCENDING, help="Order (default: DESCENDING)",
                              choices={order.name for order in Order})

    # Get chords
    # parser_chords = subparsers.add_parser("chords", help="Get list of stored freqlogged chords",
    #                                       parents=[log_arg, path_arg, num_arg])
    # parser_chords.add_argument("chord", help="Chord(s) to get data of", nargs="*")
    # parser_chords.add_argument("-s", "--sort-by", default=ChordMetadataAttr.frequency.name,
    #                            help=f"Sort by (default: {ChordMetadataAttr.frequency.name})")
    #                            choices={attr.name for attr in ChordMetadataAttr})
    # parser_chords.add_argument("-o", "--order", default=Order.ASCENDING, help="Order (default: DESCENDING)",
    #                            choices={order.name for order in Order})

    # Get banned words
    parser_banned = subparsers.add_parser("banlist", help="Get list of banned words",
                                          parents=[log_arg, path_arg, num_arg])
    parser_banned.add_argument("-s", "--sort-by", default=WordMetadataAttr.frequency.name,
                               help="Sort by (default: DATE_ADDED)",
                               choices={attr.name for attr in BanlistAttr})
    parser_banned.add_argument("-o", "--order", default=Order.DESCENDING, help="Order (default: DESCENDING)",
                               choices={order.name for order in Order})

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
    # subparsers.add_parser("stoplog", help="Stop logging", parents=[log_arg])
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args()

    # Set up console logging
    if args.log_level == "NONE":
        logging.disable(logging.CRITICAL)
    else:
        logging.basicConfig(level=args.log_level, format="%(asctime)s - %(message)s")

    exit_code = 0

    # Print help if no command is given
    if not args.command:
        parser.print_help()
        sys.exit(exit_code)

    # Validate arguments before creating Freqlog object
    match args.command:
        case "startlog":
            try:  # ensure that path is writable (WARNING: Must use 'a' instead of 'w' mode to avoid erasing file!!!)
                with open(args.freq_log_path, "a"):
                    pass
            except OSError as e:
                print(f"Error: {e}")
                exit_code = 4
            if args.new_word_threshold <= 0:
                print("Error: New word threshold must be greater than 0")
                exit_code = 3
            if args.chord_char_threshold <= 0:
                print("Error: Chord character threshold must be greater than 0")
                exit_code = 3
            if len(args.allowed_keys_in_chord) == 0:
                print("Error: Must allow at least one key in chord")
                exit_code = 3
        case "words":
            if args.num < 0:
                print("Error: Number of words must be >= 0")
                exit_code = 3
        case "chords":
            if args.num < 0:
                print("Error: Number of chords must be >= 0")
                exit_code = 3
        case "banlist":
            if args.num < 0:
                print("Error: Number of words must be >= 0")
                exit_code = 3
    if exit_code != 0:
        sys.exit(exit_code)

    # Parse commands
    if args.command == "stoplog":  # stop freqlogging
        # Kill freqlogging process
        print("This feature hasn't been implemented. To stop freqlogging gracefully, simply kill the process (Ctrl-c)")
        exit_code = 100
        sys.exit(exit_code)
        # TODO: implement

    # Some features from this point on may not have been implemented
    try:
        freqlog = Freqlog.Freqlog(args.freq_log_path)
        match args.command:
            case "startlog":  # start freqlogging
                signal.signal(signal.SIGINT, lambda *_: freqlog.stop_logging())
                freqlog.start_logging(args.new_word_threshold, args.chord_char_threshold, args.allowed_keys_in_chord,
                                      Defaults.DEFAULT_MODIFIER_KEYS - set(args.remove_modifier_key) | set(
                                          args.add_modifier_key))
            case "checkword":  # check if word is banned
                if freqlog.check_banned(args.word, args.case):
                    print("Word is banned")
                    exit_code = 1
                else:
                    print("Word is not banned")
                    exit_code = 0
                sys.exit(exit_code)
            case "banword":  # ban word
                freqlog.ban_word(args.word, args.case)
            case "unbanword":  # unban word
                freqlog.unban_word(args.word, args.case)
            # TODO: pretty print
            case "words":  # get words
                if len(args.word) == 0:  # all words
                    res = freqlog.list_words(args.num, WordMetadataAttr[args.sort_by], args.order == Order.DESCENDING,
                                             CaseSensitivity[args.case])
                    if len(res) == 0:
                        print("No words in freqlog. Start typing!")
                    else:
                        for word in res:
                            print(word)
                else:  # specific words
                    if args.num:
                        print("Warning: -n/--num argument ignored when specific words are given")
                    words: list[WordMetadata] = []
                    for word in args.word:
                        res = freqlog.get_word_metadata(word, args.case)
                        if res is None:
                            print(f"Word '{word}' not found")
                            exit_code = 5
                        else:
                            words.append(res)
                    if len(words) > 0:
                        for word in sorted(words, key=lambda x: getattr(x, args.sort_by),
                                           reverse=(args.order == Order.DESCENDING)):
                            print(word)
            case "chords":  # get chords
                if len(args.chord) == 0:  # all chords
                    res = freqlog.list_chords(args.num, ChordMetadataAttr[args.sort_by], args.order == Order.DESCENDING,
                                              CaseSensitivity[args.case])
                    if len(res) == 0:
                        print("No chords in freqlog. Start chording!")
                    else:
                        for chord in res:
                            print(chord)
                else:  # specific chords
                    if args.num:
                        print("Warning: -n/--num argument ignored when specific chords are given")
                    chords: list[ChordMetadata] = []
                    for chord in args.chord:
                        res = freqlog.get_chord_metadata(chord)
                        if res is None:
                            print(f"Chord '{chord}' not found")
                            exit_code = 5
                        else:
                            chords.append(res)
                    if len(chords) > 0:
                        for chord in sorted(chords, key=lambda x: getattr(x, args.sort_by),
                                            reverse=(args.order == Order.DESCENDING)):
                            print(chord)
            case "banlist":  # get banned words
                res = freqlog.list_banned_words(args.num, BanlistAttr[args.sort_by], args.order == Order.DESCENDING)
                if len(res) == 0:
                    print("No banned words")
                else:
                    for word in sorted(res, key=lambda x: getattr(x, args.sort_by),
                                       reverse=(args.order == Order.DESCENDING)):
                        print(word)
    except NotImplementedError:
        print(f"Error: The '{args.command}' command has not been implemented yet")
        exit_code = 100
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
