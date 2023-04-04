import signal

from Freqlog import Freqlog

if __name__ == "__main__":
    freqlog = Freqlog()
    signal.signal(signal.SIGINT, lambda *_: freqlog.stop_logging())
    freqlog.start_logging()
