import sys

from Freqlog.Freqlog import Freqlog

if __name__ == "__main__":
    freqlog = Freqlog()
    try:
        freqlog.start_logging()
    except KeyboardInterrupt:
        freqlog.stop_logging()
        sys.exit(0)
