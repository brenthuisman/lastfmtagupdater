import os,time,logging
from mutagen.flac import FLAC
from mutagen.id3 import ID3, TIT1, COMM, TCON, TPE1, TPE2, TIT2, TALB
from mutagen.mp4 import MP4
from mutagen.oggvorbis import OggVorbis
from mutagen.oggopus import OggOpus
from mutagen import File
from . import common

class MediaHelper:
    config = None
    maxTags = None
    tagSkipCounts = None
    overwriteFields = None
    forceOverwriteFields = None
    id3v2DupeHeaderFix = False
    useBothArtistFields = False
    artistFieldPref = []

    formatFieldMap = dict(
          id3=dict(genre='TCON', grouping='TIT1', comment="COMM::eng", artist='TPE1', albumartist='TPE2', album='TALB', track='TIT2'),
          mp4=dict(genre='\xa9gen', grouping='\xa9grp', comment='\xa9cmt', artist='\xa9ART', albumartist='aART', album='\xa9alb', track='\xa9nam'),
          oggvorbis=dict(genre='genre', grouping='grouping', comment='comment', artist='artist', albumartist='album artist', album='album', track='title'),
          oggopus=dict(genre='genre', grouping='grouping', comment='comment', artist='artist', albumartist='album artist', album='album', track='title'),
          flac=dict(genre='genre', grouping='grouping', comment='comment', artist='artist', albumartist='album artist', album='album', track='title')
    )

    id3FuncMap = dict(
        genre=lambda val: TCON(encoding=3, text=val),
        grouping=lambda val: TIT1(encoding=3, text=val),
        comment=lambda val: COMM(encoding=3, lang='eng', desc='', text=val),
        artist=lambda val: TPE1(encoding=3, text=val),
        albumartist=lambda val: TPE2(encoding=3, text=val),
        album=lambda val: TALB(encoding=3, text=val),
        track=lambda val: TIT2(encoding=3, text=val)
    )

    meaninglessArtists = frozenset(['various artists', 'soundtrack', 'soundtracks', 'original soundtrack', 'ost', 'compilation'])


    def __init__(self, config):
        self.config = config
        self.maxTags = dict(genre=self.config.getint('genreMaxTags'),
                            grouping=self.config.getint('groupingMaxTags'),
                            comment=self.config.getint('commentMaxTags'))
        self.tagSkipCounts = dict(genre=self.config.getint('genreTagSkipCount'),
                                  grouping=self.config.getint('groupingTagSkipCount'),
                                  comment=self.config.getint('commentTagSkipCount'))
        self.overwriteFields = set(map(str.strip, self.config.get('overwriteFields').lower().split(',')))
        self.forceOverwriteFields = set(map(str.strip, self.config.get('forceOverwriteFields').lower().split(',')))
        self.ignoreCase = self.config.getboolean('ignoreCase')
        self.id3v2DupeHeaderFix = self.config.getboolean('id3v2DupeHeaderFix')

        self.artistFieldPref = ['albumartist', 'artist']
        if (self.config.get('artistField').lower() == 'both'):
            self.useBothArtistFields = True
        elif (self.config.get('artistField').lower() == 'artist'):
            self.artistFieldPref.reverse()


    def getMediawrapper(self, filename):
        root, ext = os.path.splitext(filename.lower())
        if (ext == '.mp3'):     mediawrapper = ID3(filename)
        elif (ext == '.m4a'):   mediawrapper = MP4(filename)
        elif (ext == '.ogg'):   mediawrapper = OggVorbis(filename)
        elif (ext == '.opus'):  mediawrapper = OggOpus(filename)
        elif (ext == '.flac'):  mediawrapper = FLAC(filename)
        else:                   mediawrapper = File(filename)
        return mediawrapper


    def extractMetadata(self, filename):
        try:
            mediawrapper = self.getMediawrapper(filename)

            if (isinstance(mediawrapper, ID3)):         return self.extractMetadataHelper(mediawrapper, self.formatFieldMap['id3'], filename)
            elif (isinstance(mediawrapper, MP4)):       return self.extractMetadataHelper(mediawrapper, self.formatFieldMap['mp4'], filename)
            elif (isinstance(mediawrapper, OggVorbis)): return self.extractMetadataHelper(mediawrapper, self.formatFieldMap['oggvorbis'], filename)
            elif (isinstance(mediawrapper, OggOpus)): return self.extractMetadataHelper(mediawrapper, self.formatFieldMap['oggopus'], filename)
            elif (isinstance(mediawrapper, FLAC)):      return self.extractMetadataHelper(mediawrapper, self.formatFieldMap['flac'], filename)
            else:
                logging.warning('\tSkipping unknown/incompatible media file type [' + filename + ']')
        except Exception as err:
            logging.error('Error seen during media reading: ' + str(err))
        return None


    def extractMetadataHelper(self, mediawrapper, fieldMap, filename):
        ''' Retrieves artist, album, and track data, forcing it to unicode '''
        artists = []
        for artistField in self.artistFieldPref:
            if (fieldMap[artistField] in mediawrapper):
                tmpartist = mediawrapper[fieldMap[artistField]][0]
                if (not common.isempty(tmpartist)):
                    if (self.ignoreCase):
                        tmpartist = tmpartist.lower()
                    artists.append(str(tmpartist))
                if (self.useBothArtistFields):
                    continue
                break
        artists = set(artists).difference(self.meaninglessArtists)
        if (len(artists) == 0):
            logging.error('No artist info found for [' + filename + ']')
            return None

        # album
        album = '-unknown-'
        if (fieldMap['album'] in mediawrapper):
            tmpalbum = mediawrapper[fieldMap['album']][0]
            if (not common.isempty(tmpalbum)):
                if (self.ignoreCase):
                    tmpalbum = tmpalbum.lower()
                album = str(tmpalbum)

        # track
        track = None
        if (fieldMap['track'] in mediawrapper):
            tmptrack = mediawrapper[fieldMap['track']][0]
            if (not common.isempty(tmptrack)):
                if (self.ignoreCase):
                    tmptrack = tmptrack.lower()
                track = str(tmptrack)
        if (track is None):
            logging.warning('No track title found for [' + filename + ']')
            return None
        return {'artists':artists, 'album':album, 'track':track}


    def updateTags(self, filename, tagPayload):
        try:
            mediawrapper = self.getMediawrapper(filename)

            for bucket in tagPayload:
                tagPayload[bucket] = tagPayload[bucket][self.tagSkipCounts[bucket]:self.tagSkipCounts[bucket] + self.maxTags[bucket]]

            if (isinstance(mediawrapper, ID3)):         return self.updateTagsHelperID3(mediawrapper, tagPayload, self.formatFieldMap['id3'])
            elif (isinstance(mediawrapper, MP4)):       return self.updateTagsHelper(mediawrapper, tagPayload, self.formatFieldMap['mp4'])
            elif (isinstance(mediawrapper, OggVorbis)): return self.updateTagsHelper(mediawrapper, tagPayload, self.formatFieldMap['oggvorbis'])
            elif (isinstance(mediawrapper, OggOpus)): return self.updateTagsHelper(mediawrapper, tagPayload, self.formatFieldMap['oggopus'])
            elif (isinstance(mediawrapper, FLAC)):      return self.updateTagsHelper(mediawrapper, tagPayload, self.formatFieldMap['flac'])
            else:                                       logging.warning('Skipping unknown/incompatible media file type [' + filename + ']')
        except Exception as err:
            logging.error('Error seen during update processing: ' + str(err))
        return False


    def updateTagsHelper(self, mediawrapper, tagPayload, fieldMap):
        ''' This version saves the tag data in Unicode encoding '''
        retVal = False
        for bucket in tagPayload:
            if (bucket not in fieldMap): raise Exception('Unknown field type requested [' + bucket + ']')
            curField = fieldMap[bucket]
            # If we're not required to overwrite, check if we actually need to and should
            if (bucket not in self.forceOverwriteFields):
                # Is the payload empty? Don't update.
                if (len(tagPayload[bucket]) == 0):
                    continue
                # Is there an existing value? Don't update if this isn't an overwritable field or if the current value is the same as the update value
                elif (curField in mediawrapper and not common.isempty(mediawrapper[curField][0])):
                    if (bucket not in self.overwriteFields or str(mediawrapper[curField][0]) == str(tagPayload[bucket])):
                        continue
            if isinstance(tagPayload[bucket], list):
                if 1==len(tagPayload[bucket]):
                    mediawrapper[curField] = tagPayload[bucket][0]
                else:
                    mediawrapper[curField] = tagPayload[bucket]
            else:
                exit("Weird tags found!")
            retVal = True
        if (retVal == True):
            retryCount = 0
            while True:
                try:
                    if (isinstance(mediawrapper, ID3)):
                        logging.error("This is not an MP3 file, yet an ID3 tag was found.")
                    else:
                        mediawrapper.save()
                    break
                except Exception as err:
                    retryCount += 1
                    if (retryCount > 2):
                        raise
                    logging.error('Problem updating media file - retrying (' + str(err) + ')')
                    time.sleep(1)
        return retVal


    def updateTagsHelperID3(self, mediawrapper, tagPayload, fieldMap):
        '''
        ID3 requires uniquely encoded values, so this custom method is necessary to properly save the updated tags.
        If the comments field is used, values will be saved with an empty description and lang=eng.
        '''
        retVal = False
        for bucket in tagPayload:
            if (bucket not in fieldMap): raise Exception('Unknown field type requested [' + bucket + ']')
            curField = fieldMap[bucket]

            # If we're not required to overwrite, check if we actually need to and should
            if (bucket not in self.forceOverwriteFields):
                # Is the payload empty? Don't update.
                if (len(tagPayload[bucket]) == 0):
                    continue
                # Is there an existing value? Don't update if this isn't an overwritable field or if the current value is the same as the update value
                elif (curField in mediawrapper and not common.isempty(mediawrapper[curField][0])):
                    if (bucket not in self.overwriteFields or str(mediawrapper[curField][0]) == str(tagPayload[bucket])):
                        continue
            mediawrapper[curField] = self.id3FuncMap[bucket](tagPayload[bucket])
            retVal = True
        if (retVal == True):
            # There's an odd bug somewhere in the interaction between some set of Mutagen, iTunes, and/or WMP that causes
            # duplicate ID3v2 headers. This tends to break playback at least in iTunes. The following pre-save block makes a
            # copy of whatever the 'current' header is, deletes 'all' v2 headers, and then re-adds the current header frames.
            # We seem to end up with some unnecessary blank padding between the frames and content, though.
            if (self.id3v2DupeHeaderFix):
                curFrames = {}
                for key in list(mediawrapper.keys()):
                    curFrames[key] = mediawrapper[key]
                retryCount = 0
                while True:
                    try:
                        mediawrapper.delete(delete_v2=True)
                        break
                    except Exception as err:
                        retryCount += 1
                        if (retryCount > 2):
                            raise
                        logging.error('Problem updating media file - retrying (' + str(err) + ')')
                        time.sleep(1)
                for key in curFrames:
                    mediawrapper[key] = curFrames[key]
            retryCount = 0
            while True:
                try:
                    mediawrapper.save(v1=0)
                    break
                except Exception as err:
                    retryCount += 1
                    if (retryCount > 2):
                        raise
                    logging.error('Problem updating media file - retrying (' + str(err) + ')')
                    time.sleep(1)
        return retVal
