import os.path,sys,logging
from .config import LastFM_Config
from .medialibrary import MediaLibrary

def main(argv=None):
    config = LastFM_Config(argv)

    if (config.getboolean('delcache') and os.path.exists(config.get('cachefile'))):
        if (config.getboolean('verbose')):
            print('Removing existing cachefile')
        os.remove(config.get('cacheFile'))
    
    logFile = config.get('logFile')
    if (logFile is 'None'):
        logFile = None
    debuglvl = logging.INFO
    if config.getboolean('verbose'):
        debuglvl = logging.DEBUG
    logging.basicConfig(filename=logFile, encoding='utf-8', level=debuglvl)

    logging.info(f"Launching [{os.path.basename(sys.argv[0]) }]")

    library = MediaLibrary(config)
    if (not config.getboolean('skipscan')):
        library.readMedia()
        library.writeCache()

    if (not config.getboolean('skipfetch')):
        try:
            library.fetchTags()
        except:
            library.writeCache()
            raise
        library.writeCache()

    if (not config.getboolean('skipupdate')):
        library.updateTags()
        library.writeCache()

    logging.info('DONE')
