import json
import os
import shutil
import string
import re

import requests

import hibiki
import mp4tools
from podcast import Podcast, PodcastEpisode
import tools
from wxpush import sendNotification

AUDIO_DIR = 'audio'
ARCHIVE_DIR = 'archive'
PODCAST_FILE = 'podcast.rss'
AUDIO_URL_PREFIX = 'https://some.domain/shuwarin-radio/'

PROJECT_FOLDER_PREFIX = 'pstl'
AUDIO_NAME_PREFIX = 'shuwarin-radio'
METADATA_ALBUM_ARTIST = 'Pastel＊Palettes'

CHARACTER_NAMES_PP = (
    ('前島亜美', 'aya'),
    ('小澤亜李', 'hina'),
    ('上坂すみれ', 'chisato'),
    ('中上育実', 'maya'),
    ('秦佐和子', 'eve'),

    ('丸山 彩', 'aya'),
    ('氷川日菜', 'hina'),
    ('白鷺千聖', 'chisato'),
    ('大和麻弥', 'maya'),
    ('若宮イヴ', 'eve'),
)
MAP_PP = {
    'aya': '前島亜美',
    'hina': '小澤亜李',
    'chisato': '上坂すみれ',
    'maya': '中上育実',
    'eve': '秦佐和子',
}

TABLE_TEMPLATE = string.Template('''\
|-
|${index}
|${date}
|{{PastelPalettes出演列表|${icon}}}
|style=text-align:left|{{HideInline|录制后感想|<br>{{Lang|ja|${content}}}}}
|${url}''')


def gen_table(j):
    episode_name: str = j['episode']['name']
    match = re.match(r'第(\d+)回', episode_name)
    assert match is not None
    episode_index = int(match.group(1))

    time: str = j['episode_updated_at']
    match = re.match(r'(\d{4})/(\d{2})/(\d{2}) (\d{2}):(\d{2}):(\d{2})', time)
    assert match is not None
    date_str = f'{int(match.group(2))}月{int(match.group(3))}日'

    line_split = '<br>'

    desc: str = j['episode']['episode_parts'][0]['description']
    desc = desc.strip().replace('\r\n', '\n')
    anchor_list, content_list = get_anchor_content(desc, line_split)
    icon = '|'.join(anchor_list)
    content = '<br><br>'.join(content_list)

    url = (f'[{AUDIO_URL_PREFIX}{AUDIO_NAME_PREFIX}-{episode_index:04d}-main.m4a 音频] '
           f'[{AUDIO_URL_PREFIX}{AUDIO_NAME_PREFIX}-{episode_index:04d}-additional.m4a 乐屋里音频]')

    return TABLE_TEMPLATE.substitute(dict(
        index=episode_index,
        date=date_str,
        icon=icon,
        content=content,
        url=url,
    ))


def get_anchor_content(desc, line_split='<br>', character_names=CHARACTER_NAMES_PP):
    desc_list = desc.split('\n\n')
    icons = []
    contents = []
    for item in desc_list:
        lines = [x.strip() for x in item.split('\n')]
        contents.append(line_split.join(lines))

        name = lines[0]
        for text, anchor in character_names:
            if text in name:
                icons.append(anchor)
                break
        else:
            raise ValueError(f'Unknown name: {name}')
    return icons, contents


def update_artists(artists, character_names=CHARACTER_NAMES_PP, map_names=MAP_PP):
    out = []
    for ar in artists:
        for text, anchor in character_names:
            if text in ar:
                out.append(map_names[anchor])
                break
        else:
            raise ValueError(f'Unknown name: {ar}')
    return out


def get_default_podcast():
    pd = Podcast(
        title='Pastel＊Palettesのしゅわりんラジオ',
        image='',  # TODO
        link='https://hibiki-radio.jp/description/pstl',
        author='Pastel＊Palettes',
        description='',  # auto update
        language='ja',
        block=True,
        new_feed_url=None,
    )
    return pd


def run(data):
    info_raw: bytes = data['info_raw']
    info_json: dict = data['info_json']
    session: requests.Session = data['session']
    save: dict = data['save']
    # print(info_json)

    out = []

    dl = hibiki.Downloader()
    dl.set_session(session)

    # check if is new
    date, episode = dl.get_date_episode(info_raw)
    if episode == save.get('last_episode'):
        # same episode, but different id, date, etc.
        skip_audio = True
        out.append('Warning: same episode number, different identity. Generate audio file skipped')
    else:
        skip_audio = False

    # create project
    project_name = f'{PROJECT_FOLDER_PREFIX}-{date.year:04d}{date.month:02d}{date.day:02d}'
    if os.access(project_name, os.F_OK):
        print(f'project "{project_name}" exists, rename old project')
        tools.rename_file(project_name, ext='')
    dl.create_project(info_raw, project_name)
    with open(os.path.join(project_name, 'project.json'), 'r', encoding='utf-8') as f:
        project = json.load(f)

    # download all
    dl.download(project_name)
    dl.download_images(project_name)

    # archive (.tar.xz, Linux only)
    dl.archive(project_name)
    tar_xz_name = f'{project_name}.tar.xz'
    tar_xz_name_dist = tools.find_valid_filename(
        os.path.join(ARCHIVE_DIR, tar_xz_name), ext='.tar.xz')
    print(f'moving archive to "{tar_xz_name_dist}"')
    os.rename(tar_xz_name, tar_xz_name_dist)

    if not skip_audio:
        # generate audio files
        print(f'remux audio')
        dl.remux(project_name)

        # test main & addition availability
        main = None  # <- filename after remux, or None
        additional = None
        for stream in project['streams']:
            prefix = stream['prefix']
            audio_file = os.path.join(project_name, f'{prefix}out.m4a')
            if stream['stream_name'] == 'main':
                main = audio_file
            elif stream['stream_name'] == 'additional':
                additional = audio_file
        print(f'main audio?: {main}')
        print(f'additional audio?: {additional}')

        # tagging (need mp4v2 binary in PATH https://github.com/TechSmith/mp4v2)
        print(f'tagging')
        metadata = dl.get_metadata(info_raw)
        original_artist = metadata['artist']
        original_comment = metadata['comment']

        metadata['albumartist'] = METADATA_ALBUM_ARTIST
        metadata['artist'] = '/'.join(update_artists(original_artist))
        metadata['comment'] = (f'{date.year:04d}-{date.month:02d}-{date.day:02d} 第{episode}回\n\n'
                               f'{original_comment}')
        arts = [
            os.path.join(project_name, dl.filename_from_url(info_json['episode']['chapters'][0]['pc_image_url'])),
            os.path.join(project_name, dl.filename_from_url(info_json['episode']['episode_parts'][0]['pc_image_url'])),
        ]
        if main is not None:
            metadata['song'] = f'しゅわラジ {episode:04d}'
            print(f'main metadata: {metadata}')
            mp4tools.write_tags(main, metadata, wipe=True)
            mp4tools.write_arts(main, arts, wipe=True)
            mp4tools.optimize(main)
        if additional is not None:
            metadata['song'] = f'しゅわラジ {episode:04d} 楽屋裏'
            print(f'additional metadata: {metadata}')
            mp4tools.write_tags(additional, metadata, wipe=True)
            mp4tools.write_arts(additional, arts, wipe=True)
            mp4tools.optimize(additional)

        # copy main & additional to deploy path
        if main is not None:
            main_dist = os.path.join(AUDIO_DIR, f'{AUDIO_NAME_PREFIX}-{episode:04d}-main.m4a')
            print(f'copy main to {main_dist}')
            os.rename(main, main_dist)
        if additional is not None:
            additional_dist = os.path.join(AUDIO_DIR, f'{AUDIO_NAME_PREFIX}-{episode:04d}-additional.m4a')
            print(f'copy additional to {additional_dist}')
            os.rename(additional, additional_dist)

        # update podcast file
        print(f'update podcast file')
        podcast_dict = save.get('podcast', None)
        if podcast_dict is None:
            print('warning: generating new podcast file')
            pd = get_default_podcast()
        else:
            pd = Podcast.from_dict(podcast_dict)
        pd.description = info_json['description'].strip().replace('\r\n', '\n')
        if main is not None:
            video_id = info_json['episode']['video']['id']
            duration = int(info_json['episode']['video']['duration'])
            pd.episodes.append(PodcastEpisode(
                title=f'しゅわラジ {episode:04d}',
                url=f'{AUDIO_URL_PREFIX}{AUDIO_NAME_PREFIX}-{episode:04d}-main.m4a',
                type='audio/mp4',
                file_length=os.path.getsize(main_dist),
                description=original_comment,
                guid=f'pstl-{episode}-{video_id}-main',
                duration=duration,
                pub_date=int(date.timestamp()),
            ))
        if additional is not None:
            video_id = info_json['episode']['additional_video']['id']
            duration = int(info_json['episode']['additional_video']['duration'])
            pd.episodes.append(PodcastEpisode(
                title=f'しゅわラジ {episode:04d} 楽屋裏',
                url=f'{AUDIO_URL_PREFIX}{AUDIO_NAME_PREFIX}-{episode:04d}-additional.m4a',
                type='audio/mp4',
                file_length=os.path.getsize(additional_dist),
                description=original_comment,
                guid=f'pstl-{episode}-{video_id}-additional',
                duration=duration,
                pub_date=int(date.timestamp()),
            ))
        with open(PODCAST_FILE, 'w', encoding='utf-8') as f:
            f.write(pd.generate_xml())
        podcast_dict = pd.to_dict()

        # generate wikitext
        print(f'generate wikitext')
        wikitext = gen_table(info_json)
        out.append(f'wikitext:\n{wikitext}')

        # finally update save data
        save['last_episode'] = episode
        save['podcast'] = podcast_dict

    # remove project (be careful when testing)
    print(f'remove project "{project_name}"')
    shutil.rmtree(project_name)

    # need wxpush dev account for WeChat notification https://wxpusher.zjiecode.com/
    if out:
        out.insert(0, 'Shuwarin Radio scraping report')
        out_str = ('\n' + '=' * 20 + '\n').join(out)
        # out_str = out_str.replace('<', '&lt;')
        print(f'Send report:\n{out_str}')
        sendNotification(out_str, summary='Shuwarin Radio scraping report')

    print(f'All done!!!')


def update_podcast():
    print(f'update podcast file')
    with open('save.json', 'r', encoding='utf-8') as f:
        save = json.load(f)['pstl']['callback_save']

    podcast_dict = save.get('podcast', None)
    if podcast_dict is None:
        raise ValueError('no podcast data')
    else:
        pd = Podcast.from_dict(podcast_dict)
    with open(PODCAST_FILE, 'w', encoding='utf-8') as f:
        f.write(pd.generate_xml())


if __name__ == '__main__':
    update_podcast()
