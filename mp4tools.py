"""mp4v2 wrapper

https://github.com/TechSmith/mp4v2
"""

import subprocess
import typing

ACCEPTED_TAGS = {
    'A', 'album',
    'a', 'artist',
    'b', 'tempo',
    'c', 'comment',
    'C', 'copyright',
    'd', 'disk',
    'D', 'disks',
    'e', 'encodedby',
    'E', 'tool',
    'g', 'genre',
    'G', 'grouping',
    'H', 'hdvideo',
    'i', 'type',
    'I', 'contentid',
    'j', 'genreid',
    'l', 'longdesc',
    'L', 'lyrics',
    'm', 'description',
    'M', 'episode',
    'n', 'season',
    'N', 'network',
    'o', 'episodeid',
    'O', 'category',
    'p', 'playlistid',
    'P', 'picture',
    'B', 'podcast',
    'R', 'albumartist',
    's', 'song',
    'S', 'show',
    't', 'track',
    'T', 'tracks',
    'x', 'xid',
    'X', 'rating',
    'w', 'writer',
    'y', 'year',
    'z', 'artistid',
    'Z', 'composerid',
}


def write_tags(filename, tags: typing.Dict[str, typing.Any], wipe=True, ignore_unknown=False):
    # check tags
    tags_command = []
    for k, v in tags.items():
        if k in ACCEPTED_TAGS:
            tags_command.append(f'-{k}')
            tags_command.append(str(v))
        else:
            if not ignore_unknown:
                raise ValueError(f'Unknown tag: {k}')

    if wipe:
        p = subprocess.run(['mp4tags', '-r', 'AabcCdDeEgGHiIjlLmMnNoOpPBRsStTxXwyzZ', filename])
        # wipe can fail when no tags, ignore errors
        # p.check_returncode()
    p = subprocess.run(['mp4tags', *tags_command, filename])
    p.check_returncode()


def write_arts(filename, arts: typing.Union[str, typing.Iterable[str]], wipe=True):
    if isinstance(arts, str):
        arts = (arts,)
    if wipe:
        p = subprocess.run(['mp4art', '--remove', filename])
        # wipe can fail when no arts, ignore errors
        # p.check_returncode()
    for img in arts:
        p = subprocess.run(['mp4art', '--add', img, filename])
        p.check_returncode()


def optimize(filename):
    p = subprocess.run(['mp4file', '--optimize', filename])
    p.check_returncode()


if __name__ == '__main__':
    optimize('test.m4a')
