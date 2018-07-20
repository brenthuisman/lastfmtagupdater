import fileinput,os,time,sys
from xml.etree.ElementTree import Element, SubElement, ElementTree
from . import common
from .lastfmwrapper import LastFM_Wrapper
from .mediahelper import MediaHelper

class MediaLibrary:
    # Media Library object:
    #
    # dict(string (lowercase artist) -> dict)
    #    string ('scanned') -> true, if the entry was present during a filescan (undefined otherwise)
    #    string ('tags') -> list of lastfm tag pairs (name,weight)
    #    string ('albums') -> dict(string (lowercase album) -> dict)
    #        string ('scanned') -> true, if the entry was present during a filescan (undefined otherwise)
    #        string ('tracks') -> dict(string (lowercase track) -> dict)
    #            string ('scanned') -> true, if the entry was present during a filescan (undefined otherwise)
    #            string ('tags') -> list of lastfm tag pairs (name,weight)
    #
    # It's more than a little inelegant, but it's a quick hack. I don't fully distinguish between same-filenamed tracks or albums,
    # even when they may be different (e.g. by track number), as lastFM itself only uses simple artist/album/track filenames as keys.
    # In otherwords, the library is not intended to be a representation of file system objects so much as distinct lastFM entities. As
    # such, we don't persist other fields, like comments, genres, etc., which may differ from file to file (even with the same key metadata).
    # This probably isn't an important distinction for the vast majority of files.

    mediaLibrary = {}

    # LastFM Tag Library object:
    # dict(string (lowercase lastfm tag) -> int (number of hits/count reported by lastFM)
    lastTagLibrary = {}

    # Local Tag Library object:
    # dict(string (lowercase local tag) -> dict)
    #    string ('disp')      -> Canonical display form for the tag
    #    string ('lastfmkeys')-> LastFM version of the tag (the original, before synonym processing)
    #    string ('localhits') -> Number of times seen in the media library (post-processing)
    #    string ('lasthits')  -> Number of times seen on lastFM (summation of the union of lastfmkey key counts)
    localTagLibrary = {}

    mediaHelper = None
    outputWrapper = None
    config = None
    synonyms = {}
    cacheBackedUp = False
    artistSkipList = None


    def __init__(self, config, outputWrapper):
        self.config = config
        self.outputWrapper = outputWrapper
        self.mediaHelper = MediaHelper(config, outputWrapper)
        self.readCache()

        self.artistSkipList = self.loadSkipList(self.config.get('artistSkipListFile'))



    def readCache(self):
        cachefile = os.path.normpath(str(self.config.get('cacheFile')))
        if (not os.path.exists(cachefile)):
            return
        self.fromXml(ElementTree().parse(cachefile))


    def writeCache(self):
        self.outputWrapper.logNormal('Saving cache')
        cachefile = os.path.normpath(str(self.config.get('cacheFile')))
        ElementTree(self.toXml()).write(cachefile, 'UTF-8')


    def readMedia(self):
        mediadir = os.path.normpath(str(self.config.get('mediaDir')))
        verbose = self.config.getboolean('verbose')
        skipExtensions = ['.' + x.lower().strip() for x in self.config.get('skipExtensions').split(',')]

        self.outputWrapper.logNormal('Reading existing metadata from [' + mediadir + ']')
        numfiles = 0
        for root, dirs, files in os.walk(mediadir):
            for filename in files:
                fname, ext = os.path.splitext(filename)
                if (ext is not None and ext.lower() in skipExtensions):
                    continue
                metadata = self.mediaHelper.extractMetadata(os.path.join(root, filename))
                if (metadata is None or len(metadata['artists']) == 0 or metadata['album'] is None or metadata['track'] is None):
                    continue
                for artist in metadata['artists']:
                    self.addToMediaLibrary(artist, metadata['album'], metadata['track'], isInScanset=True)
                numfiles += 1
                if (verbose):
                    self.outputWrapper.logNormal('\tProcessed: ' + os.path.join(root, filename))
        self.outputWrapper.logNormal('Read [' + str(numfiles) + '] media files')


    def addToMediaLibrary(self, artist, album, track, artistTags=None, trackTags=None, isInScanset=False):
        if (common.isempty(artist)):
            raise Exception('No artist info provided')
        elif (common.isempty(track)):
            raise Exception('No track title provided')
        elif (common.isempty(album)):
            raise Exception('No album title provided')

        if (artist not in self.mediaLibrary):
            self.mediaLibrary[artist] = { 'albums':{}, 'tags':artistTags }

        if (album not in self.mediaLibrary[artist]['albums']):
            self.mediaLibrary[artist]['albums'][album] = { 'tracks':{} }

        if (track not in self.mediaLibrary[artist]['albums'][album]['tracks']):
            self.mediaLibrary[artist]['albums'][album]['tracks'][track] = { 'tags':trackTags }

        if (isInScanset):
            self.mediaLibrary[artist]['scanned'] = True
            self.mediaLibrary[artist]['albums'][album]['scanned'] = True
            self.mediaLibrary[artist]['albums'][album]['tracks'][track]['scanned'] = True


    def printLibrary(self):
        for artist in self.mediaLibrary:
            self.outputWrapper.logNormal(artist + ' (' + ', '.join([pair[0] for pair in self.mediaLibrary[artist]['tags'] or []]) + ')')
            for album in self.mediaLibrary[artist]['albums']:
                self.outputWrapper.logNormal('\t' + album)
                for track in self.mediaLibrary[artist]['albums'][album]['tracks']:
                    self.outputWrapper.logNormal('\t\t' + track + ' (' + ', '.join([pair[0] for pair in self.mediaLibrary[artist]['albums'][album]['tracks'][track]['tags'] or []]) + ')')


    def toXml(self):
        numartists = 0
        numalbums = 0
        numtracks = 0

        try:
            libraryElement = Element('library')
            artistsElement = SubElement(libraryElement, 'artists')
            for artist in sorted(self.mediaLibrary):
                artistDict = self.mediaLibrary[artist]
                artistElement = SubElement(artistsElement, 'artist')

                SubElement(artistElement, 'name').text = artist

                if (artistDict['tags'] is not None):
                    if (len(artistDict['tags']) == 0):
                        SubElement(artistElement, 'notags')
                    else:
                        for tagpair in sorted(artistDict['tags']):
                            SubElement(artistElement, 'tag', weight=str(tagpair[1])).text = tagpair[0]

                for album in sorted(artistDict['albums']):
                    albumDict = artistDict['albums'][album]
                    albumElement = SubElement(artistElement, 'album')

                    SubElement(albumElement, 'name').text = album

                    for track in sorted(albumDict['tracks']):
                        trackDict = albumDict['tracks'][track]
                        trackElement = SubElement(albumElement, 'track')

                        SubElement(trackElement, 'name').text = track

                        if (trackDict['tags'] is not None):
                            if (len(trackDict['tags']) == 0):
                                SubElement(trackElement, 'notags')
                            else:
                                for tagpair in sorted(trackDict['tags']):
                                    SubElement(trackElement, 'tag', weight=str(tagpair[1])).text = tagpair[0]

                        numtracks += 1
                    numalbums += 1
                numartists += 1
            self.outputWrapper.logNormal('Serialized [' + str(numartists) + '] artists, [' + str(numalbums) + '] albums, and [' + str(numtracks) + '] tracks to XML')

            localTagsElement = SubElement(libraryElement, 'localTags')
            for tagpair in sorted(list(self.localTagLibrary.items()), key=lambda x: x [1]['localhits'], reverse=True):
                tag = tagpair[0]
                tagdict = tagpair[1]
                SubElement(localTagsElement, 'tag',
                        hits=str(tagdict['localhits'] or 0),
                        lastFmHits=str(tagdict['lasthits'] or 0),
                        lastFmTags=str(','.join(tagdict['lastfmkeys'] if 'lastfmkeys' in tagdict else []))).text = tagdict['disp']

            lastTagsElement = SubElement(libraryElement, 'lastFmTags')
            numtags = 0
            for tag in sorted(self.lastTagLibrary):
                SubElement(lastTagsElement, 'tag', hits=str(self.lastTagLibrary[tag] or 0)).text = tag
                numtags += 1

            self.outputWrapper.logNormal('Serialized [' + str(numtags) + '] lastFM tags to XML')

            return libraryElement
        except Exception as err:
            raise Exception('Could not serialize the XML cache data: ' + str(err)).with_traceback(sys.exc_info()[2])


    def fromXml(self, rootElement):
        numartists = 0
        numalbums = 0
        numtracks = 0
        ignoreCase = self.config.getboolean('ignoreCase')

        try:
            artistsElement = rootElement.find('artists')
            for artistElement in artistsElement.findall('artist'):
                nameElement = artistElement.find('name')
                if (nameElement is None):
                    self.outputWrapper.logError('Missing name element on [' + artistElement.tag + ']')
                    continue
                artist = str(nameElement.text.lower() if ignoreCase else nameElement.text)

                # tags = None means there is no tag info, tags = [] means we know it's an empty list
                artistTags = None
                artistTagElements = artistElement.findall('tag')
                if (artistTagElements is not None and len(artistTagElements) > 0):
                    artistTags = []
                    for artistTagElement in artistTagElements:
                        artistTags.append((str(artistTagElement.text), int(artistTagElement.get('weight'))))
                elif (artistElement.find('notags') is not None):
                    artistTags = []

                for albumElement in artistElement.findall('album'):
                    nameElement = albumElement.find('name')
                    if (nameElement is None):
                        self.outputWrapper.logError('Missing name element on [' + albumElement.tag + ']')
                        continue
                    album = str(nameElement.text.lower() if ignoreCase else nameElement.text)

                    for trackElement in albumElement.findall('track'):
                        nameElement = trackElement.find('name')
                        if (nameElement is None):
                            self.outputWrapper.logError('Missing name element on [' + trackElement.tag + ']')
                            continue
                        track = str(nameElement.text.lower() if ignoreCase else nameElement.text)

                        # tags = None means there is no tag info, tags = [] means we know it's an empty list
                        trackTags = None
                        trackTagElements = trackElement.findall('tag')
                        if (trackTagElements is not None and len(trackTagElements) > 0):
                            trackTags = []
                            for trackTagElement in trackTagElements:
                                trackTags.append((str(trackTagElement.text), int(trackTagElement.get('weight'))))
                        elif (trackElement.find('notags') is not None):
                            trackTags = []

                        self.addToMediaLibrary(artist, album, track, artistTags, trackTags)

                        numtracks += 1
                    numalbums += 1
                numartists += 1
            self.outputWrapper.logNormal('Loaded [' + str(numartists) + '] artists, [' + str(numalbums) + '] albums, and [' + str(numtracks) + '] cached tracks')

            lastTagsElement = rootElement.find('lastFmTags')
            for lastTagElement in lastTagsElement.findall('tag'):
                self.addToLastFMTagLibrary(str(lastTagElement.text), int(lastTagElement.get('hits')))
        except Exception as err:
            raise Exception('Could not deserialize the XML cache data, possibly corrupted: ' + str(err)).with_traceback(sys.exc_info()[2])


    def fetchTags(self):
        lastfm = LastFM_Wrapper(self.config, self.outputWrapper)
        self.fetchArtistTags(lastfm)
        self.fetchTrackTags(lastfm)
        self.fetchTagStats(lastfm)
        #if (self.config.getboolean('verbose')):
        #    self.printDistinctLastTags()


    def fetchArtistTags(self, lastfm):
        verbose = self.config.getboolean('verbose')
        refetch = self.config.getboolean('refetchCachedTags')
        minWeight = self.config.getint('minArtistTagWeight')
        niceness = self.config.getint('niceness') / 1000
        maxTagsToSave = self.config.getint('getArtistTags')
        if (maxTagsToSave <= 0):
            return

        self.outputWrapper.logNormal('Fetching artist tags from LastFM')
        for artist in sorted(self.mediaLibrary):
            if (artist in self.artistSkipList):
                continue
            if ('scanned' not in self.mediaLibrary[artist]):
                continue
            tagpairs = self.mediaLibrary[artist]['tags']
            if (tagpairs is not None and refetch is False):
                continue
            self.mediaLibrary[artist]['tags'] = tagpairs = lastfm.fetchArtistTags(artist, maxTagsToSave, minWeight)
            if (tagpairs is not None):
                list(map(self.addToLastFMTagLibrary, [pair[0] for pair in tagpairs]))
            if (verbose):
                self.outputWrapper.logNormal('\tFetched [' + artist + '] (' + (', '.join([pair[0] for pair in tagpairs]) if tagpairs is not None else '') + ')')
            time.sleep(niceness)


    def fetchTrackTags(self, lastfm):
        verbose = self.config.getboolean('verbose')
        refetch = self.config.getboolean('refetchCachedTags')
        minWeight = self.config.getint('minTrackTagWeight')
        niceness = self.config.getint('niceness') / 1000
        maxTagsToSave = self.config.getint('getTrackTags')
        if (maxTagsToSave <= 0):
            return

        self.outputWrapper.logNormal('Fetching track tags from LastFM')
        for artist in sorted(self.mediaLibrary):
            if (artist in self.artistSkipList):
                continue
            for album in sorted(self.mediaLibrary[artist]['albums']):
                for track in sorted(self.mediaLibrary[artist]['albums'][album]['tracks']):
                    if ('scanned' not in self.mediaLibrary[artist]['albums'][album]['tracks'][track]):
                        continue
                    tagpairs = self.mediaLibrary[artist]['albums'][album]['tracks'][track]['tags']
                    if (tagpairs is not None and refetch is False):
                        continue
                    self.mediaLibrary[artist]['albums'][album]['tracks'][track]['tags'] = tagpairs = lastfm.fetchTrackTags(artist, track, maxTagsToSave, minWeight)
                    if (tagpairs is not None):
                        list(map(self.addToLastFMTagLibrary, [pair[0] for pair in tagpairs]))
                    if (verbose):
                        self.outputWrapper.logNormal('\tFetched [' + artist + ':' + track + '] (' + (', '.join([pair[0] for pair in tagpairs]) if tagpairs is not None else '') + ')')
                    time.sleep(niceness)


    def fetchTagStats(self, lastfm):
        ''' Fetch overall/LastFM-wide tag counts. Currently only works for LastFM's 'top tracks' (they don't syndicate counts for arbitrary tags) '''
        toptags = lastfm.fetchTopTagStats()
        if (toptags is None or len(toptags) == 0):
            self.outputWrapper.logError('Could not retrieve tag counts from lastFM')
            for lasttag in self.lastTagLibrary:
                self.lastTagLibrary[lasttag] = 0
            return
        for lasttag in self.lastTagLibrary:
            if (lasttag in toptags):
                self.lastTagLibrary[lasttag] = toptags[lasttag]


    def addToLastFMTagLibrary(self, lasttag, hits=0):
        '''
        This method ensures that the fetched tags are in the lastFM tag library. We use
        this later to handle stats. If the tag is already in the library, this does nothing.
        '''
        key = lasttag.lower()
        if (key not in self.lastTagLibrary):
            self.lastTagLibrary[key] = hits


    def updateTags(self):
        ''' This pushes the tags back into the underlying media files '''
        verbose = self.config.getboolean('verbose')
        ignoreCase = self.config.getboolean('ignoreCase')
        mediadir = os.path.normpath(str(self.config.get('mediaDir')))
        startDelim = self.config.get('tagStartDelim')
        endDelim = self.config.get('tagEndDelim')
        artistTagFields = set(map(str.strip, self.config.get('artistTagFields').lower().split(',')))
        trackTagFields = set(map(str.strip, self.config.get('trackTagFields').lower().split(',')))
        touchedFields = artistTagFields.union(trackTagFields)
        skipExtensions = ['.' + x.lower().strip() for x in self.config.get('skipExtensions').split(',')]
        writeUntaggedArtist = (self.config.get('writeUntaggedTag').lower() == 'artist' or self.config.get('writeUntaggedTag').lower() == 'both')
        writeUntaggedTrack = (self.config.get('writeUntaggedTag').lower() == 'track' or self.config.get('writeUntaggedTag').lower() == 'both')

        if (touchedFields is None or len(touchedFields) == 0):
            self.outputWrapper.logError('Perhaps you should configure a destination field...')
            return

        self.loadSynonyms()
        self.generateLocalTags()

        self.outputWrapper.logNormal('Updating tags in [' + mediadir + ']')
        numfiles = 0
        for root, dirs, files in os.walk(mediadir):
            for filename in files:
                try:
                    fname, ext = os.path.splitext(filename)
                    if (ext is not None and ext.lower() in skipExtensions):
                        continue

                    metadata = self.mediaHelper.extractMetadata(os.path.join(root, filename))
                    if (metadata is None or len(metadata['artists']) == 0 or metadata['album'] is None or metadata['track'] is None):
                        continue
                    album = metadata['album'].lower() if ignoreCase else metadata['album']
                    track = metadata['track'].lower() if ignoreCase else metadata['track']

                    artistTags = []
                    trackTags = []
                    for artist in list(map(str.lower, metadata['artists'])) if ignoreCase else metadata['artists']:
                        if (artist in self.artistSkipList):
                            continue
                        if (artist not in self.mediaLibrary or
                            album not in self.mediaLibrary[artist]['albums'] or
                            track not in self.mediaLibrary[artist]['albums'][album]['tracks']):
                            self.outputWrapper.logError('Entry not found in library: [' + artist + '][' + album + '][' + track + ']')
                            continue
                        artistTags.extend(self.mediaLibrary[artist]['tags'] or [])
                        trackTags.extend(self.mediaLibrary[artist]['albums'][album]['tracks'][track]['tags'] or [])

                    localArtistTags = self.lastTagsToLocalTags(artistTags)
                    localTrackTags = self.lastTagsToLocalTags(trackTags)

                    # Use untagged tags, if requested and appropriate
                    if (len(localArtistTags) == 0 and writeUntaggedArtist): localArtistTags = [('untagged artist', 0)]
                    if (len(localTrackTags) == 0 and writeUntaggedTrack):   localTrackTags = [('untagged track', 0)]

                    tagPayload = {}
                    for touchedField in touchedFields:
                        if (touchedField in artistTagFields and touchedField in trackTagFields):
                            fieldTags = common.distinctTagSeq(localArtistTags + localTrackTags)
                        elif (touchedField in artistTagFields):
                            fieldTags = localArtistTags
                        else:
                            fieldTags = localTrackTags

                        if (fieldTags is None or len(fieldTags) == 0) :
                            continue

                        # The following section is mostly to deal with multi-column sorting

                        # Store the record weights somewhere we can look them up (the list should already be distinct)
                        recordWeights = {}
                        for tagpair in fieldTags:
                            recordWeights[tagpair[0].lower()] = tagpair[1]

                        # Pull out just the tag names as singleton tuples, we'll tack on sort weights next
                        tagWeightsList = [(tuple[0],) for tuple in fieldTags]

                        # Pull out the list of sort rules (e.g. record, library) and append each appropriate weight to the tuple list, in succession
                        sortRules = list(map(str.strip, self.config.get(touchedField + 'Sort').lower().split(',')))
                        for sortRule in sortRules:
                            if (sortRule == 'record'):      tagWeightsList = [tagtuple + (recordWeights[tagtuple[0].lower()],) for tagtuple in tagWeightsList]
                            elif (sortRule == 'library'):   tagWeightsList = [tagtuple + (self.getLibraryWeight(tagtuple[0].lower()),) for tagtuple in tagWeightsList]
                            elif (sortRule == 'popularity'):tagWeightsList = [tagtuple + (self.getPopularityWeight(tagtuple[0].lower()),) for tagtuple in tagWeightsList]

                        common.sortWeightedTagTuples(tagWeightsList)

                        tagPayload[touchedField] = self.formattedTagList(tagWeightsList, startDelim, endDelim)

                    if (self.mediaHelper.updateTags(os.path.join(root, filename), tagPayload)):
                        numfiles += 1
                        if (verbose):
                            self.outputWrapper.logNormal('\tUpdated: ' + os.path.join(root, filename))
                    elif (verbose):
                        self.outputWrapper.logNormal('\tSkipped: ' + os.path.join(root, filename) + ' (nothing to update)')
                except Exception as err:
                    self.outputWrapper.logError('\tFailed to update: ' + os.path.join(root, filename) + ' (' + str(err) + ')')
                    pass
        self.outputWrapper.logNormal('Updated [' + str(numfiles) + '] media files')
        #if (verbose):
        #    self.printDistinctLocalTags()


    def loadSynonyms(self):
        synfile = self.config.get('tagSynonymsFile')
        if (common.isempty(synfile)):
            return
        if (not os.path.exists(synfile) or not os.access(synfile, os.R_OK)):
            self.outputWrapper.logError('Synonyms file either does not exist or cannot be accessed [' + synfile + ']')

        # Read the synonmyms file. The expected format is:
        # original token(tab)replacement token[,replacement token]...
        # e.g.
        # rnb    rhythm and blues, r&b
        # This would replace any instance of 'rnb' seen in the LastFM tag set with both 'rhythm and blues' and 'r&b'
        # We preserve order, for the replacement values (so you can order them as you would like them to be replaced)
        for line in fileinput.input(synfile):
            # Allow inline comments
            if ('#' in line):
                line = line.split('#')[0]
            line = line.strip()
            if (common.isempty(line)):
                continue
            if (isinstance(line, str)):
                pass#line = str(line, 'latin1')
            synline = line.split('\t')
            if (len(synline) < 2):
                self.outputWrapper.logError('Invalid synonym file line: ' + line)
                continue
            original = synline[0].lower()
            replacements = list(map(str.strip, synline[1].split(',')))
            if ('-none-' in [val.lower() for val in replacements]):
                self.synonyms[original] = []
            elif (original in self.synonyms):
                self.synonyms[original] = common.distinctSeq(self.synonyms[original] + replacements)
            else:
                self.synonyms[original] = common.distinctSeq(replacements)
        #for syn in sorted(self.synonyms):
        #    self.outputWrapper.logNormal(u'Synonyms: '+ syn + ' :: '+ ', '.join(sorted(self.synonyms[syn])))
        if (self.config.getboolean('verbose')):
            self.outputWrapper.logNormal('Loaded [' + str(len(list(self.synonyms.keys()))) + '] tag synonyms')


    def loadSkipList(self, strInFile):
        if (common.isempty(strInFile)):
            return set()
        if (not os.path.exists(strInFile) or not os.access(strInFile, os.R_OK)):
            self.outputWrapper.logError('SkipList file either does not exist or cannot be accessed [' + strInFile + ']')

        ignoreCase = self.config.getboolean('ignoreCase')
        tmpSet = set()
        for line in fileinput.input(strInFile):
            # Allow inline comments
            if ('#' in line):
                line = line.split('#')[0]
            line = line.strip()
            if (common.isempty(line)):
                continue
            if (isinstance(line, str)):
                pass#line = str(line, 'latin1')
            if (ignoreCase):
                line = line.lower()
            tmpSet.add(line)
        if (self.config.getboolean('verbose')):
            self.outputWrapper.logNormal('Loaded [' + str(len(tmpSet)) + '] skip list entries from [' + strInFile + ']')
        return tmpSet


    def generateLocalTags(self):
        '''
        This method goes through the media library and pulls out each distinct token, storing it in
        the localTagLibrary object. At the end of processing, this object will contain counters for the
        number of times each tag is referenced in the local library and a canonical (display) form of the tag
        '''

        # These are dummy tags which may optionally be used to indicate an absence of tags
        self.localTagLibrary['untagged artist'] = dict(disp='Untagged Artist', lastfmkeys=[], localhits=0, lasthits=0)
        self.localTagLibrary['untagged track'] = dict(disp='Untagged Track', lastfmkeys=[], localhits=0, lasthits=0)

        for artist in self.mediaLibrary:
            self.generateLocalTagsHelper(self.mediaLibrary[artist]['tags'], 'untagged artist')
            for album in self.mediaLibrary[artist]['albums']:
                for track in self.mediaLibrary[artist]['albums'][album]['tracks']:
                    self.generateLocalTagsHelper(self.mediaLibrary[artist]['albums'][album]['tracks'][track]['tags'], 'untagged track')

        # Move or merge the lastFM tag counts to the local tag object
        for localtag in self.localTagLibrary:
            lastcount = 0
            for lastkey in self.localTagLibrary[localtag]['lastfmkeys']:
                lastcount += self.lastTagLibrary[lastkey]
            self.localTagLibrary[localtag]['lasthits'] = lastcount


    def generateLocalTagsHelper(self, tagpairs, emptyTagKey):
        '''
        This method operates on each individual record (either a track or an artist), performing synonym
        expansion/contraction and finally incrementing tag counters for the distinct tags left after processing
        '''
        if (tagpairs is None or len(tagpairs) == 0):
            self.localTagLibrary[emptyTagKey]['localhits'] += 1
            return
        newtags = []
        for tagpair in tagpairs:
            synlist = self.lookupSynonyms(tagpair[0])
            if (synlist is not None):   tmplist = synlist       # an empty set is valid (means delete the tag)
            else:                       tmplist = [tagpair[0]]
            for tmptag in tmplist:
                self.addToLocalTagLibrary(tmptag, tagpair[0])
                newtags.append((tmptag.lower(), tagpair[1]))
        newtags = common.distinctTagSeq(newtags)
        if (len(newtags) > 0):
            # Keep track of distinct library hits for the local tags
            for newtag in newtags:
                self.localTagLibrary[newtag[0]]['localhits'] += 1
        else:
            self.localTagLibrary[emptyTagKey]['localhits'] += 1

    def addToLocalTagLibrary(self, localtag, lasttag):
        '''
        Ensures that the specified tag is in the local tag library, with a back reference to the original
        lastFM tag. We also seed the 'disp' value with a canonical tag representation. In general, this is the
        first case-form of the tag seen (so you don't end up with genres 'indie' and 'Indie'), but may optionally
        be forced to a cap-word form ('Punk Rock') via the config file
        '''
        localkey = localtag.lower()
        lastkey = lasttag.lower()
        if (localkey not in self.localTagLibrary):
            if (self.config.getboolean('capTagWords')): disptag = localtag.title()
            else:                                       disptag = localtag
            self.localTagLibrary[localkey] = dict(disp=disptag, lastfmkeys=set([lastkey]), localhits=0)
        elif (lastkey not in self.localTagLibrary[localkey]['lastfmkeys']):
            self.localTagLibrary[localkey]['lastfmkeys'].add(lastkey)


    def lastTagsToLocalTags(self, tagpairs):
        '''
        This method performs synonym expansion/contraction and duplicate removal, returning a 'local tag'
        version of the lastFM tag stream. It also optionally filters out low-count tags.
        '''
        if (tagpairs is None or len(tagpairs) == 0) :
            return []

        newtags = []
        for tagpair in tagpairs:
            synlist = self.lookupSynonyms(tagpair[0])
            if (synlist is not None):   tmplist = synlist       # an empty list is valid (means delete the tag)
            else:                       tmplist = [tagpair[0]]
            for tmptag in tmplist:
                key = tmptag.lower()
                if (self.localTagLibrary[key]['localhits'] < self.config.getint('minLibraryCount')): continue
                if (self.localTagLibrary[key]['lasthits'] < self.config.getint('minLastFMCount')): continue
                newtags.append((tmptag.lower(), tagpair[1]))
        return common.distinctTagSeq(newtags)


    def lookupSynonyms(self, tag):
        ''' Returns a set of synonyms for the given tag, or None if none exist '''
        if (common.isempty(tag)):
            return None
        key = tag.lower()
        try:
            if any(key in x for x in [x.lower().strip() for x in self.config.get('skipTags').split(',')]):
                return None
        except:
            # zero or one skiptag defined.
            pass
        if (key in self.synonyms):
            return self.synonyms[key]
        return None


    def printDistinctLocalTags(self):
        if (len(self.localTagLibrary) == 0):
            return
        disptags = []
        for localtag in self.localTagLibrary:
            disptags.append((self.localTagLibrary[localtag]['disp'], self.localTagLibrary[localtag]['localhits']))
        self.outputWrapper.logNormal('\nDistinct Update-stream Tags (most to least frequent, in your library): \n\t' + '\n\t'.join([pair[0] + ' (' + str(pair[1]) + ')' for pair in common.sortWeightedTagTuples(disptags)]))


    def printDistinctLastTags(self):
        if (len(self.lastTagLibrary) == 0):
            return
        disptags = []
        for lasttag in self.lastTagLibrary:
            disptags.append((lasttag, self.lastTagLibrary[lasttag]))
        self.outputWrapper.logNormal('\nDistinct In-library LastFM Tags (most to least popular, on LastFM): \n\t' + '\n\t'.join([pair[0] + ' (' + str(pair[1]) + ')' for pair in common.sortWeightedTagTuples(disptags)]))


    def formattedTagList(self, tagpairs, startDelim, endDelim):
        '''
        This method breaks apart the tag pairs, returning just a list of the canonical-form
        tags (optionally formatted with starting/ending delimiters)
        '''
        return common.distinctSeq([startDelim + self.localTagLibrary[pair[0]]['disp'] + endDelim for pair in tagpairs])


    def getLibraryWeight(self, tag):
        ''' Returns the library weight for the given tag, or 0 if the tag is empty or not present '''
        if (common.isempty(tag)):
            return 0
        key = tag.lower()
        if (self.localTagLibrary[key] is not None):
            return self.localTagLibrary[key]['localhits']
        return 0


    def getPopularityWeight(self, tag):
        ''' Returns the popularity weight for the given tag, or 0 if the tag is empty or not present '''
        if (common.isempty(tag)):
            return 0
        key = tag.lower()
        if (self.localTagLibrary[key] is not None):
            return self.localTagLibrary[key]['lasthits']
        return 0
