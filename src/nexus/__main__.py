import argparse
import logging
import signal
import sys

from pynput import keyboard

from nexus import __doc__, __version__, Freqlog
from nexus.Freqlog.Definitions import Age, BanlistAttr, CaseSensitivity, ChordMetadata, ChordMetadataAttr, Defaults, \
    Order, WordMetadata, WordMetadataAttr
from nexus.Freqlog.backends.SQLite import SQLiteBackend
from nexus.GUI import GUI


def main():
    """
    nexus CLI
    Exit codes:
        0: Success (including graceful keyboard interrupt during startlog) / word is not banned
        1: Forceful keyboard interrupt during startlog / checkword result contains a banned word
        2: Invalid command or argument
        3: Invalid value for argument
        4: Could not access or write to database
        5: Requested word or chord not found
        6: Tried to ban already banned word or unban already unbanned word
        7: Merge db requirements not met
        11: Python version < 3.11
        100: Feature not yet implemented
    """
    # Error and exit on Python version < 3.11
    if sys.version_info < (3, 11):
        print("Python 3.11 or higher is required")
        sys.exit(11)

    log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "NONE"]

    # Common arguments
    # Log and path must be SUPPRESS for placement before and after command to work
    #   (see https://stackoverflow.com/a/62906328/9206488)
    log_arg = argparse.ArgumentParser(add_help=False)
    log_arg.add_argument("-l", "--log-level", default=argparse.SUPPRESS, help=f"One of {log_levels}",
                         metavar="level", choices=log_levels)
    path_arg = argparse.ArgumentParser(add_help=False)
    path_arg.add_argument("--freqlog-db-path", default=argparse.SUPPRESS, help="Path to db backend to use")
    case_arg = argparse.ArgumentParser(add_help=False)
    case_arg.add_argument("-c", "--case", default=CaseSensitivity.INSENSITIVE.name, help="Case sensitivity",
                          choices={case.name for case in CaseSensitivity})
    num_arg = argparse.ArgumentParser(add_help=False)
    num_arg.add_argument("-n", "--num", type=int, required=False,
                         help=f"Number of words to return (0 for all), default {Defaults.DEFAULT_NUM_WORDS_CLI}")
    search_arg = argparse.ArgumentParser(add_help=False)
    search_arg.add_argument("-f", "--find", metavar="search", dest="search", help="Search for (part of) a word",
                            required=False)

    # Parse command line arguments
    parser = argparse.ArgumentParser(description=__doc__,
                                     epilog="Made with love by CharaChorder, source code available at "
                                            "https://github.com/CharaChorder/nexus")
    parser.add_argument("-l", "--log-level", default="INFO", help=f"One of {log_levels}",
                        metavar="level", choices=log_levels)
    parser.add_argument("--freqlog-db-path", default=Defaults.DEFAULT_DB_PATH, help="Path to db backend to use")
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
                              choices=sorted(key.name for key in set(keyboard.Key) - Defaults.DEFAULT_MODIFIER_KEYS))
    parser_start.add_argument("--remove-modifier-key", action="append", default=[],
                              help="Remove a modifier key from the default set",
                              choices=sorted(key.name for key in Defaults.DEFAULT_MODIFIER_KEYS))

    # Num words
    subparsers.add_parser("numwords", help="Get number of words in freqlog", parents=[log_arg, path_arg, case_arg])

    # Get words
    parser_words = subparsers.add_parser("words", help="Get list of freqlogged words",
                                         parents=[log_arg, path_arg, case_arg, num_arg, search_arg])
    parser_words.add_argument("word", help="Word(s) to get data of", nargs="*")
    parser_words.add_argument("-e", "--export", help="Export all freqlogged words as csv to file"
                                                     "(ignores word args)", required=False)
    parser_words.add_argument("-s", "--sort-by", default=WordMetadataAttr.frequency.name,
                              help=f"Sort by (default: {WordMetadataAttr.frequency.name})",
                              choices=[attr.name for attr in WordMetadataAttr])
    parser_words.add_argument("-o", "--order", default=Order.DESCENDING, help="Order (default: DESCENDING)",
                              choices=[order.name for order in Order])

    # Get chords
    # parser_chords = subparsers.add_parser("chords", help="Get list of stored freqlogged chords",
    #                                       parents=[log_arg, path_arg, num_arg])
    # parser_chords.add_argument("chord", help="Chord(s) to get data of", nargs="*")
    # parser_chords.add_argument("-e", "--export", help="Export freqlogged chords as csv to file"
    #                                                   "(ignores chord args)", required=False)
    # parser_chords.add_argument("-s", "--sort-by", default=ChordMetadataAttr.frequency.name,
    #                            help=f"Sort by (default: {ChordMetadataAttr.frequency.name})"),
    #                            choices=[attr.name for attr in ChordMetadataAttr])
    # parser_chords.add_argument("-o", "--order", default=Order.ASCENDING, help="Order (default: DESCENDING)",
    #                            choices=[order.name for order in Order])

    # Get banned words
    parser_banned = subparsers.add_parser("banlist", help="Get list of banned words",
                                          parents=[log_arg, path_arg, num_arg])
    parser_banned.add_argument("-s", "--sort-by", default=BanlistAttr.date_added.name,
                               help="Sort by (default: DATE_ADDED)",
                               choices=[attr.name for attr in BanlistAttr])
    parser_banned.add_argument("-o", "--order", default=Order.DESCENDING, help="Order (default: DESCENDING)",
                               choices=[order.name for order in Order])

    # Check ban
    parser_check = subparsers.add_parser("checkword", help="Check if a word is banned",
                                         parents=[log_arg, path_arg, case_arg])
    parser_check.add_argument("word", help="Word(s) to check", nargs="+")

    # Ban
    parser_ban = subparsers.add_parser("banword", help="Ban a word and delete any existing entries of it",
                                       parents=[log_arg, path_arg, case_arg])
    parser_ban.add_argument("word", help="Word(s) to ban", nargs="+")

    # Unban
    parser_unban = subparsers.add_parser("unbanword", help="Unban a word", parents=[log_arg, path_arg, case_arg])
    parser_unban.add_argument("word", help="Word(s) to unban", nargs="+")

    # Stop freqlogging
    # subparsers.add_parser("stoplog", help="Stop logging", parents=[log_arg])
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {__version__}")

    # Merge db
    parser_merge = subparsers.add_parser("mergedb", help="Merge two Freqlog databases", parents=[log_arg])
    parser_merge.add_argument("--ban-data-keep", default=Age.OLDER.name,
                              help=f"Which ban data to keep (default: {Age.OLDER.name})",
                              choices=[age.name for age in Age])
    parser_merge.add_argument("src1", help="Path to first source database")
    parser_merge.add_argument("src2", help="Path to second source database")
    parser_merge.add_argument("dst", help="Path to destination database")

    # Parse arguments
    args = parser.parse_args()

    # Set up console logging
    if args.log_level == "NONE":
        logging.disable(logging.CRITICAL)
    else:
        logging.basicConfig(level=args.log_level, format="%(asctime)s - %(message)s")
    logging.debug(f"Args: {args}")

    exit_code = 0

    # Show GUI if no command is given
    if not args.command:
        sys.exit(GUI(args).exec())

    # Validate arguments before creating Freqlog object
    match args.command:
        case "startlog":
            try:  # ensure that path is writable (WARNING: Must use 'a' instead of 'w' mode to avoid erasing file!!!)
                with open(args.freqlog_db_path, "a"):
                    pass
            except OSError as e:
                logging.error(e)
                exit_code = 4
            if args.new_word_threshold <= 0:
                logging.error("New word threshold must be greater than 0")
                exit_code = 3
            if args.chord_char_threshold <= 0:
                logging.error("Chord character threshold must be greater than 0")
                exit_code = 3
            if len(args.allowed_keys_in_chord) == 0:
                logging.error("Must allow at least one key in chord")
                exit_code = 3
        case "words":
            if args.num and args.num < 0:
                logging.error("Number of words must be >= 0")
                exit_code = 3
        case "chords":
            if args.num and args.num < 0:
                logging.error("Number of chords must be >= 0")
                exit_code = 3
        case "banlist":
            if args.num and args.num < 0:
                logging.error("Number of words must be >= 0")
                exit_code = 3

    # Parse commands
    if args.command == "mergedb":  # merge databases
        # Merge databases
        logging.warning("This feature has not been thoroughly tested and is not guaranteed to work. Manually verify"
                        f"(via an export) that the destination DB ({args.dst}) contains all your data after merging.")
        try:
            src1: SQLiteBackend = Freqlog.Freqlog(args.src1, loggable=False)
            src1.merge_backends(args.src2, args.dst, Age[args.ban_data_keep])
            sys.exit(0)
        except ValueError as e:
            logging.error(e)
            exit_code = 7

    if args.command == "stoplog":  # stop freqlogging
        # Kill freqlogging process
        logging.warning("This feature hasn't been implemented." +
                        "To stop freqlogging gracefully, simply kill the process (Ctrl-c)")
        exit_code = 100
        # TODO: implement

    # Exit before creating Freqlog object if checks failed
    if exit_code != 0:
        sys.exit(exit_code)

    # TODO: Some features from this point on may not have been implemented
    try:
        # All following commands require a freqlog object
        freqlog = Freqlog.Freqlog(args.freqlog_db_path, loggable=False)
        if args.command == "numwords":  # get number of words
            print(f"{freqlog.num_words(CaseSensitivity[args.case])} words in freqlog")
            sys.exit(0)

        # All following commands use a num argument
        try:
            num = args.num if args.num else Defaults.DEFAULT_NUM_WORDS_CLI
        except AttributeError:
            num = Defaults.DEFAULT_NUM_WORDS_CLI
        match args.command:
            case "startlog":  # start freqlogging
                freqlog = Freqlog.Freqlog(args.freqlog_db_path, loggable=True)
                signal.signal(signal.SIGINT, lambda: freqlog.stop_logging())
                freqlog.start_logging(args.new_word_threshold, args.chord_char_threshold, args.allowed_keys_in_chord,
                                      Defaults.DEFAULT_MODIFIER_KEYS - set(args.remove_modifier_key) | set(
                                          args.add_modifier_key))
            case "checkword":  # check if word is banned
                for word in args.word:
                    if freqlog.check_banned(word, CaseSensitivity[args.case]):
                        print(f"'{word}' is banned")
                        exit_code = 1
                    else:
                        print(f"'{word}' is not banned")
            case "banword":  # ban word
                for word in args.word:
                    if not freqlog.ban_word(word, CaseSensitivity[args.case]):
                        exit_code = 6
            case "unbanword":  # unban word
                for word in args.word:
                    if not freqlog.unban_word(word, CaseSensitivity[args.case]):
                        exit_code = 6
            # TODO: pretty print
            case "words":  # get words
                if args.export:  # export words
                    freqlog.export_words_to_csv(args.export, num, WordMetadataAttr[args.sort_by],
                                                args.order == Order.DESCENDING, CaseSensitivity[args.case])
                elif len(args.word) == 0:  # all words
                    res = freqlog.list_words(limit=num, sort_by=WordMetadataAttr[args.sort_by],
                                             reverse=args.order == Order.DESCENDING,
                                             case=CaseSensitivity[args.case], search=args.search if args.search else "")
                    if len(res) == 0:
                        print("No words in freqlog. Start typing!")
                    else:
                        for word in res:
                            print(word)
                else:  # specific words
                    if num:
                        logging.warning("-n/--num argument ignored when specific words are given")
                    words: list[WordMetadata] = []
                    for word in args.word:
                        res = freqlog.get_word_metadata(word, CaseSensitivity[args.case])
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
                if args.export:  # export chords
                    freqlog.export_chords_to_csv(args.export, num, ChordMetadataAttr[args.sort_by],
                                                 args.order == Order.DESCENDING, CaseSensitivity[args.case])
                elif len(args.chord) == 0:  # all chords
                    res = freqlog.list_logged_chords(num, ChordMetadataAttr[args.sort_by],
                                                     args.order == Order.DESCENDING)
                    if len(res) == 0:
                        print("No chords in freqlog. Start chording!")
                    else:
                        for chord in res:
                            print(chord)
                else:  # specific chords
                    if num:
                        logging.warning("-n/--num argument ignored when specific chords are given")
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
                banlist_case, banlist_caseless = freqlog.list_banned_words(limit=num, sort_by=BanlistAttr[args.sort_by],
                                                                           reverse=args.order == Order.DESCENDING)
                if len(banlist_case) == 0 and len(banlist_caseless) == 0:
                    print("No banned words")
                else:
                    for entry in banlist_caseless:
                        entry.word += "*"
                    print("Banned words (* denotes case-insensitive entries):")
                    for entry in sorted(banlist_case | banlist_caseless, key=lambda x: getattr(x, args.sort_by),
                                        reverse=(args.order == Order.DESCENDING)):
                        print(entry)
    except NotImplementedError:
        logging.error(f"The '{args.command}' command has not been implemented yet")
        exit_code = 100
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
