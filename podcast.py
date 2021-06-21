import dataclasses
from time import gmtime, strftime
from typing import Optional, List
import xml.etree.ElementTree as ET
import io


@dataclasses.dataclass
class Podcast:
    title: str = ''
    image: str = ''
    link: str = ''
    episodes: List['PodcastEpisode'] = dataclasses.field(default_factory=list)

    author: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    language: Optional[str] = None
    # itunes_block: bool = False
    # googleplay_block: bool = False
    block: bool = False
    new_feed_url: Optional[str] = None

    @classmethod
    def from_dict(cls, d: dict):
        self = cls()
        for k, v in d.items():
            if k in self.__dict__:
                if k == 'episodes':
                    self.episodes = [PodcastEpisode.from_dict(x) for x in v]
                else:
                    self.__dict__[k] = v
        return self

    def to_dict(self):
        return dataclasses.asdict(self)

    def generate_xml(self, *, googleplay=True, itunes=True, normal=True) -> str:
        root_tags = {
            'version': '2.0'
        }
        if googleplay:
            root_tags['xmlns:googleplay'] = 'http://www.google.com/schemas/play-podcasts/1.0'
        if googleplay or itunes:
            root_tags['xmlns:itunes'] = 'http://www.itunes.com/dtds/podcast-1.0.dtd'
        root = ET.Element('rss', root_tags)
        channel = ET.SubElement(root, 'channel')

        ET.SubElement(channel, 'title').text = self.title
        ET.SubElement(channel, 'link').text = self.link
        if normal:
            image = ET.SubElement(channel, 'image')
            ET.SubElement(image, 'link').text = self.link
            ET.SubElement(image, 'title').text = self.title
            ET.SubElement(image, 'url').text = self.image
        if googleplay:
            ET.SubElement(channel, 'googleplay:image', href=self.image)
        if itunes:
            ET.SubElement(channel, 'itunes:image', href=self.image)

        if self.author is not None:
            if googleplay:
                ET.SubElement(channel, 'googleplay:author').text = self.author
            if itunes:
                ET.SubElement(channel, 'itunes:author').text = self.author
        if self.category is not None:
            if googleplay:
                ET.SubElement(channel, 'googleplay:category', text=self.category)
            if itunes:
                ET.SubElement(channel, 'itunes:category', text=self.category)
        if self.description is not None:
            if normal:
                ET.SubElement(channel, 'description').text = self.description
            if googleplay:
                ET.SubElement(channel, 'googleplay:description').text = self.description
            if itunes:
                ET.SubElement(channel, 'itunes:summary').text = self.description
        # if self.explicit:
        #     pass
        if self.language is not None:
            ET.SubElement(channel, 'language').text = self.language
        if self.block:
            if googleplay:
                ET.SubElement(channel, 'googleplay:block').text = 'yes'
            if itunes:
                ET.SubElement(channel, 'itunes:block').text = 'yes'
        if self.new_feed_url is not None:
            if googleplay or itunes:
                ET.SubElement(channel, 'itunes:new-feed-url').text = self.new_feed_url

        for eps in reversed(self.episodes):
            eps.generate_xml(channel, googleplay=googleplay, itunes=itunes, normal=normal)

        out = io.StringIO()
        tree = ET.ElementTree(root)
        tree.write(out, encoding='unicode', xml_declaration=True)
        return out.getvalue()


@dataclasses.dataclass
class PodcastEpisode:
    title: str = ''
    url: str = ''
    type: str = ''
    file_length: int = 0

    description: Optional[str] = None
    explicit: bool = False
    guid: Optional[str] = None
    duration: Optional[int] = None
    pub_date: Optional[int] = None
    block: bool = False

    @classmethod
    def from_dict(cls, d: dict):
        self = cls()
        for k, v in d.items():
            if k in self.__dict__:
                self.__dict__[k] = v
        return self

    def generate_xml(self, channel, *, googleplay=True, itunes=True, normal=True) -> None:
        episode = ET.SubElement(channel, 'item')
        if self.guid is not None:
            ET.SubElement(episode, 'guid', isPermaLink='false').text = self.guid

        if normal:
            ET.SubElement(episode, 'title').text = self.title
        if itunes:
            ET.SubElement(episode, 'itunes:title').text = self.title

        if self.description is not None:
            if normal:
                ET.SubElement(episode, 'description').text = self.description
            if googleplay:
                ET.SubElement(episode, 'googleplay:description').text = self.description
            if itunes:
                ET.SubElement(episode, 'itunes:summary').text = self.description
        ET.SubElement(episode, 'enclosure',
                      url=self.url,
                      type=self.type,
                      length=str(self.file_length))
        # if self.explicit:
        #     pass
        if self.pub_date is not None:
            ET.SubElement(episode, 'pubDate').text = strftime(
                '%a, %d %b %Y %H:%M:%S +0000', gmtime(self.pub_date))
        if self.duration is not None:
            if googleplay or itunes:
                ET.SubElement(episode, 'itunes:duration').text = str(self.duration)
        if self.block:
            if googleplay:
                ET.SubElement(episode, 'googleplay:block').text = 'yes'
            if itunes:
                ET.SubElement(episode, 'itunes:block').text = 'yes'


def test():
    # pd = Podcast()
    # pd.episodes.append(PodcastEpisode())
    # print(dataclasses.asdict(pd))
    d = {
        'title': 'podcast title',
        'image': 'https://test.url/image',
        'link': 'https://test.url/homepage',
        'episodes': [
            {
                'title': 'episode 1',
                'url': 'https://episode.url/1.m4a',
                'type': 'audio/mp4',
                'file_length': 12345,
                'description': 'episode desc abc',
                'explicit': False,
                'guid': 'guid12345678',
                'duration': 60,
                'pub_date': 1623338405,
                'block': False
            },
        ],
        'author': 'author name',
        'category': None,
        'description': 'podcast desc abd',
        'language': 'ja',
        'block': False,
        'new_feed_url': 'https://new.url/',
    }
    pd = Podcast.from_dict(d)
    xml = pd.generate_xml()
    print(xml)
    with open('podcast_test.xml', 'w', encoding='utf-8') as f:
        f.write(xml)


if __name__ == '__main__':
    test()
