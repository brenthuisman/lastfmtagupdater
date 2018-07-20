import codecs,sys
from .config import LastFM_Config

'''
This helper class facilitates output to either the console or a GUI. If GUI mode is selected, the window will open
as a background thread.
'''
class OutputWrapper():

    def __init__(self, config):
        self.config = config

        logFile = self.config.get('logFile')
        if (logFile is not None):
            self.logFileHandle = codecs.open(logFile, 'w+', 'utf_8_sig')


    def logNormal(self, msg):
        self._logHelper(msg, sys.stdout)


    def logError(self, msg):
        self._logHelper(msg, sys.stderr)


    def _logHelper(self, msg, consoleStream):

        if (self.logFileHandle is not None):
            self.logFileHandle.write(msg + '\n')
            self.logFileHandle.flush()

        if (isinstance(msg, str)):
            pass#msg = msg.encode('latin1', 'replace')
        try:
            print(msg)#, file=consoleStream)
        except:
            print(file)#=consoleStream)
            pass
        consoleStream.flush()


    def close(self):
        if (self.logFileHandle is not None):
            self.logFileHandle.close()
