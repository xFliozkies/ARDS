"""Private inverse stdin adapters for older structured reviewer fixtures.

Each result is checked against official samples and decode_stdin for every case.
These are encodings only, not learner solutions or public API data.
"""
def text(*parts):
    def row(v):
        if isinstance(v,(list,tuple)): return ' '.join(row(x) for x in v)
        return str(v)
    return '\n'.join(row(p) for p in parts)+'\n'


def encode(number, d):
    if number==22: return text(len(d).bit_length()-1,d)
    if number in (30,179,257,289): return text(len(d),d)
    if number==43: return text(len(d)+1,d)
    if number==31: return text([len(d[0][0]),len(d[1])],*d[0],*d[1])
    if number==46: return text([len(d['items']),d['b']],*d['items'])
    if number==50: return text([len(d['t']),d['l'],d['s'],len(d['acc'])],d['acc'],*d['t'])
    if number==60: return text([len(d[2]),d[0],d[1]],d[2])
    if number in (61,162,202,243,325,326): return text([len(d[0]),len(d[1])],d[0],*d[1])
    if number==73: return text([len(d[0]),len(d[1])],d[0],*[[x+1,y+1] for x,y in d[1]])
    if number==76: return text([len(d[0])+1,len(d[1])+1,len(d[2])],d[0],d[1],*d[2])
    if number==81: return text([len(d[1]),d[0]+1],*d[1])
    if number==83: return text(len(d[0]),d[0],*[[x+1,y+1] for x,y in d[1]])
    if number==86: return text([len(d[0]),len(d[1])],[x+1 for x in d[0][1:]],*[[x+1,y+1] for x,y in d[1]])
    if number==92: return text(len(d),*[[len(row),*row] for row in d])
    if number==134: return text(len(d)//2,*d)
    if number==145: return text([len(d[0]),len(d[0][0]),d[1]],*d[0])
    if number in (151,288): return text([d[0],len(d[1])],*d[1])
    if number==194: return text([d[0],d[1],len(d[3])],d[2],*d[3])
    if number==195: return text([d[0],d[1],len(d[2]),len(d[3])],*d[2],*d[3])
    if number==206: return text([d[0],len(d[1]),len(d[2])],*d[1],*d[2])
    if number==233: return text([d[0],len(d[1]),len(d[2])],*d[1],*d[2])
    if number==235: return text([len(d[2])+1,d[0],d[1]],d[2])
    if number==245: return text([len(d[1]),len(d[0])],*d[0],d[1])
    if number==264: return text([len(v) for v in d],*d)
    if number==302: return text([len(d[0][0]) if d[0] else len(d[1][0][0]),len(d[0]),len(d[1])],*d[0],*d[1])
    if number==306: return text([d[0],len(d[2]),d[1]],*d[2])
    if number==320: return text([len(d[0][0]),len(d)],*d)
    if number==324: return text([len(d[2]),d[0],d[1]],*zip(d[2],d[3]))
    if number==329: return text([d[0],len(d[2])],*d[1],*[[len(row),*row] for row in d[2]])
    if number==592: return text([len(d[3]),d[0],d[1],d[2]],*d[3])
    if number==597: return text([len(d[0]),len(d[0][0]),d[3]],*d[0],*d[1],*d[2])
    if number==598: return text([len(d[0]),len(d[2])],d[0],[x+1 for x in d[1][1:]],*[[x+1,y] for x,y in d[2]])
    if number==599: return text([len(d[0]),len(d[4]),d[1]+1,d[2]+1,d[3]],d[0],*[[x+1,y+1,w] for x,y,w in d[4]])
    raise KeyError(number)
