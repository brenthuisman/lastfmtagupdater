def isempty(strng):
    ''' How is this not a part of the standard library? '''
    return strng is None or len(strng.strip()) == 0


def distinctTagSeq(tags):
    ''' This eliminates duplicate tags from the sequence (the highest weight version is kept). The returned list
    will be in sorted order, by weight. '''
    if (tags is None or len(tags) <= 1):
        return tags or []
    seen = set()
    result = []
    #for pair in sorted(tags, lambda pair1, pair2: cmp(pair2[1], pair1[1])):
    for pair in sorted(tags, key=lambda x: x[1]):
        key = pair[0].lower()
        if (key in seen): continue
        seen.add(key)
        result.append(pair)
    return result


def distinctSeq(seq):
    ''' This eliminates subsequent duplicate values from a list, in a case-insensitive fashion '''
    if (seq is None or len(seq) <= 1):
        return seq or []
    seen = set()
    result = []
    for val in seq:
        if (isinstance(val, str) or isinstance(val, str)):
            key = val.lower()
        else:
            key = val
        if (key in seen): continue
        seen.add(key)
        result.append(val)
    return result

def sortWeightedTagTuples(tagtuples):
    '''
    This method performs an inplace multi-field sort on the provided list of tag tuples, using the integer weights
    stored in each tuple at position [1:]. It is assumed that all tuples have the same length. Thus, if provided a list of
    3 item tuples, the result will be sorted first by the values in position 1 and then, where position 1 values are the same,
    by the values in position 2. Sort order is descending and this sort should be stable. Although the sort is inplace, we
    return a reference to the original (now sorted) list, as a convenience.
    '''
    if (tagtuples is None or len(tagtuples) == 0) :
        return None
    tagtuples.sort(key=lambda tag: [-sortval for sortval in tag[1:]])
    return tagtuples
