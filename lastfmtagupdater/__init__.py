import os.path,sys
from .config import LastFM_Config
from .medialibrary import MediaLibrary
from .outputwrapper import OutputWrapper

def main(argv=None):
    config = LastFM_Config(argv)

    if (config.getboolean('delcache') and os.path.exists(config.get('cachefile'))):
        if (config.getboolean('verbose')):
            print('Removing existing cachefile')
        os.remove(config.get('cacheFile'))

    print(('Launching [' + os.path.basename(sys.argv[0]) + ']'))

    outputWrapper = OutputWrapper(config)

    try:
        library = MediaLibrary(config, outputWrapper)
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

        outputWrapper.logNormal('DONE')

    except:
        pass
    finally:
        outputWrapper.close()