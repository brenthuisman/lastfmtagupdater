import sys,pylast,time,logging

# Fetch tags from LastFM and convert them into a list of (tag, weight) pairs
class LastFM_Wrapper:

    def __init__(self, config):
        self.config = config
        self.api_key = config.get('lastFMAPI_key')
        self.api_secret = config.get('lastFMAPI_secret')
        pyver = sys.version_info
        logging.getLogger(pylast.__name__).setLevel(logging.ERROR)


    def fetchArtistTags(self, artist, maxTagsToFetch, minWeight, retries=2):
        '''
        Retrieve artist tags from LastFM, filtering out those tags that appear bunky (below the specified
        weight, longer than the maximum allowable distance, self-referential, etc.
        '''
        try:
            lastfm = pylast.LastFMNetwork(api_key=self.api_key, api_secret=self.api_secret)
            tags = self.processSeenTags(lastfm.get_artist(artist).get_top_tags(limit=maxTagsToFetch), minWeight)
            return [pair for pair in tags if pair[0].lower().replace('the', '').strip() != artist.lower().replace('the', '').strip()]
        except Exception as err:
            if ('not found' in str(err).lower() or 'not be found' in str(err).lower()): return []
            if (retries > 0):
                logging.error('Problem retrieving artist tag information for [' + str(artist) + '], ' + str(retries) + ' retries left: ' + str(err))
                time.sleep(5)
                return self.fetchArtistTags(artist, maxTagsToFetch, minWeight, retries - 1)
            else:
                logging.error('Problem retrieving artist tag information for [' + str(artist) + '], skipping: ' + str(err))
        return None


    def fetchTrackTags(self, artist, track, maxTagsToFetch, minWeight, retries=2):
        '''
        Retrieve track tags from LastFM, filtering out those tags that appear bunky (below the specified
        weight, longer than the maximum allowable distance, self-referential, etc.
        '''
        try:
            lastfm = pylast.LastFMNetwork(api_key=self.api_key, api_secret=self.api_secret)
            tags = self.processSeenTags(lastfm.get_track(artist, track).get_top_tags(limit=maxTagsToFetch), minWeight)
            return [pair for pair in tags if pair[0].lower().replace('the', '').strip() != artist.lower().replace('the', '').strip() and pair[0].lower() != track]
        except Exception as err:
            if ('not found' in str(err).lower() or 'not be found' in str(err).lower()): return []
            if (retries > 0):
                logging.error('Problem retrieving track tag information for [' + str(artist) + ':' + str(track) + '], ' + str(retries) + ' retries left: ' + str(err))
                time.sleep(5)
                return self.fetchTrackTags(artist, track, maxTagsToFetch, minWeight, retries - 1)
            else:
                logging.error('Problem retrieving track tag information for [' + str(artist) + ':' + str(track) + '], skipping: ' + str(err))
        return None


    def processSeenTags(self, tags, minWeight):
        '''
        This method converts a lastFM tag stream into our internal format (a list of (tag, weight) pairs), while
        also filtering based on minimum weight. We convert the tag to a unicode type.
        '''
        if (tags is None or len(tags) == 0):
            return []

        newtags = []
        for rawtag in tags:
            if type(rawtag) == pylast.TopItem:
                tag = str(rawtag.item.get_name())
                weight = int(rawtag.weight)
            else:
                tag = str(rawtag['item'].name)
                weight = int(rawtag['weight'])
            # results are pre-sorted, so we can abort on this condition
            if (weight < minWeight): break
            if (len(tag) > self.config.getint('maxTagLength')): continue
            newtags.append((tag, weight))
        return newtags


    def fetchTopTagStats(self, retries=2):
        '''
        LastFM provides a unified list tags/counts, for the top tags. By fetching these in one call, we can
        typically avoid a ton of unnecessary network calls for individual tags.
        '''
        tags = {}
        try:
            lastfm = pylast.LastFMNetwork(api_key=self.api_key, api_secret=self.api_secret)
            lastTopTags = lastfm.get_top_tags(10000)
            for lastTopTag in lastTopTags:
                if type(lastTopTag) == pylast.TopItem:
                    key = str(lastTopTag.item.get_name()).lower()
                    count = int(lastTopTag.weight)
                else:
                    key = str(lastTopTag['item'].name).lower()
                    count = int(lastTopTag['weight'])
                if (key in tags):
                    logging.error('Duplicate tag retrieved from lastFM, merging counts: ' + lastTopTag)
                    tags[key] += count
                else:
                    tags[key] = count
            return tags
        except Exception as err:
            if (retries > 0):
                logging.error('Problem retrieving top tag information, ' + str(retries) + ' retries left: ' + str(err))
                time.sleep(5)
                return self.fetchTopTagStats(retries - 1)
            else:
                logging.error('Problem retrieving top tag information, ' + str(retries) + ' skipping: ' + str(err))
        return None
