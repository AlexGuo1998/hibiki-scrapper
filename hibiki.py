import datetime
import os
import re
import subprocess
import json
import typing

import requests
import m3u8

from download import DownloaderOptions, DownloadQueue

# UA = 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:88.0) Gecko/20100101 Firefox/88.0'

type_keys_dict = typing.Dict[str, bytes]
type_download_list = typing.List[typing.Tuple[str, str]]


class Downloader:
    Empty = object()

    def __init__(self):
        self.session = requests.Session()
        # self.session.headers['User-Agent'] = UA
        # self.session.headers['X-Requested-With'] = 'XMLHttpRequest'
        # self.session.headers['Origin'] = 'https://hibiki-radio.jp'
        # self.session.headers['Referer'] = 'https://hibiki-radio.jp/'

    def set_proxy(self, http_proxy, https_proxy=Empty):
        if https_proxy is self.Empty:
            https_proxy = http_proxy
        proxy_dict = {}
        if http_proxy is not None:
            proxy_dict['http'] = http_proxy
        if https_proxy is not None:
            proxy_dict['https'] = https_proxy
        self.session.proxies = proxy_dict

    def set_session(self, session):
        self.session = session

    def get_date_episode(self, program_info_raw: bytes):
        program_info_json = json.loads(program_info_raw.decode('utf-8'))
        episode_info = program_info_json['episode']
        # episode_id: int = episode_info['id']
        episode_name: str = episode_info['name']
        episode_time: str = episode_info['updated_at']

        # program_name: str = program_info_json['access_id']

        # TODO may not always working (how do we parse all names safely?)
        #  e.g. '第240BanG!!!!!'
        #       '第38回（通算90回）'
        match = re.match(r'第(\d+)回', episode_name)
        assert match is not None
        episode_index = int(match.group(1))

        match = re.match(r'(\d{4})/(\d{2})/(\d{2}) (\d{2}):(\d{2}):(\d{2})', episode_time)
        assert match is not None
        dt = datetime.datetime(
            int(match.group(1)),
            int(match.group(2)),
            int(match.group(3)),
            int(match.group(4)),
            int(match.group(5)),
            int(match.group(6)),
            tzinfo=datetime.timezone(datetime.timedelta(hours=9), 'JST'))

        return dt, episode_index

    def create_project(self, program_info_raw: bytes, dirname):
        # program_info_json, program_info_raw = self._get_program_info(program_name)
        program_info_json = json.loads(program_info_raw.decode('utf-8'))
        # print(json.dumps(program_info_json, ensure_ascii=False, indent=1))

        print('create_project start')
        os.makedirs(dirname, exist_ok=False)

        streams = []
        save_pairs = []
        for stream, stream_name in (
                (program_info_json['episode']['video'], 'main'),
                (program_info_json['episode']['additional_video'], 'additional'),
        ):
            print(f'try stream name: {stream_name}')
            try:
                stream_id = stream['id']
            except (KeyError, TypeError):
                print(f'stream id for {stream_name} not found! skipping...')
                continue

            print(f'stream id for {stream_name} is {stream_id}')

            save_pairs_new, stream_info = self._get_stream_info(stream_id, stream_name)

            save_pairs.extend(save_pairs_new)
            streams.append(stream_info)

            print(f'stream name: {stream_name} done')

        project = {
            'info_json': 'program_info.json',
            'streams': streams,
        }
        save_pairs.append(('program_info.json', program_info_raw))
        save_pairs.append(('project.json', json.dumps(project).encode('utf-8')))

        # write all files at once
        print(f'saving all files to "{dirname}"')
        for filename, content in save_pairs:
            full_name = os.path.join(dirname, filename)
            print(f'Writing "{full_name}"')
            with open(full_name, 'wb') as f:
                f.write(content)
        print('create_project done')

    def get_metadata(self, program_info_raw: bytes):
        program_info_json = json.loads(program_info_raw.decode('utf-8'))

        description = program_info_json['episode']['episode_parts'][0]['description']
        description = description.strip().replace('\r\n', '\n')
        artist = self._get_artist(description)
        date, episode = self.get_date_episode(program_info_raw)

        metadata = {
            'song': '',
            'album': program_info_json['name'],
            'artist': artist,
            'albumartist': '',
            'comment': description,

            # 'type': xxx,
            'track': episode,
            'year': date.year,
        }
        return metadata

    def _get_artist(self, desc):
        desc_list = desc.split('\n\n')
        names = []
        for item in desc_list:
            lines = [x.strip() for x in item.split('\n')]
            name = lines[0]
            names.append(name)
        return names

    # def create_project_from_stream_id(self, stream_id, dirname, stream_name='stream'):
    #     os.makedirs(dirname, exist_ok=False)
    #
    #     save_pairs, stream_info = self._get_stream_info(stream_id, stream_name)
    #
    #     project = {
    #         'info_json': 'program_info.json',
    #         'streams': [stream_info],
    #     }
    #     save_pairs.append(('project.json', json.dumps(project).encode('utf-8')))
    #
    #     # write all files at once
    #     print(f'Saving to "{dirname}"')
    #     for filename, content in save_pairs:
    #         with open(os.path.join(dirname, filename), 'wb') as f:
    #             f.write(content)
    #     print('Done!')

    def _get_stream_info(self, stream_id, stream_name):
        print('getting stream url')
        playlist_url, stream_info_raw = self._get_stream_url(stream_id)

        prefix = f'{stream_name}_{stream_id}_'
        playlist_filename = f'{prefix}playlist.m3u8'
        variant_filename = f'{prefix}variant.m3u8'
        patched_filename = f'{prefix}patched.m3u8'

        # print('getting stream playlist and keys')
        playlist_content, variant_content, m3u8_patched, key_dict, download_list = \
            self._get_stream_download_info(playlist_url, prefix=prefix)

        save_pairs = [
            (playlist_filename, playlist_content),
            (variant_filename, variant_content),
            (patched_filename, m3u8_patched)]
        save_pairs.extend(key_dict.items())

        stream_info = {
            'stream_id': stream_id,
            'stream_name': stream_name,
            'prefix': prefix,
            'playlist_url': playlist_url,
            'playlist_file': playlist_filename,
            'variant_file': variant_filename,
            'patched_file': patched_filename,
            'key_files': list(key_dict.keys()),
            'download_list': download_list,
        }
        return save_pairs, stream_info

    def _get_stream_url(self, video_id) -> typing.Tuple[str, bytes]:
        r = self.session.get('https://vcms-api.hibiki-radio.jp/api/v1/videos/play_check',
                             # headers={'Accept': 'application/json, text/plain, */*'},
                             params={'video_id': video_id},
                             headers={'X-Requested-With': 'XMLHttpRequest'})
        r.raise_for_status()
        j = r.json()
        playlist = j['playlist_url']
        return playlist, r.content

    def _get_stream_download_info(self, stream_url, prefix='') \
            -> typing.Tuple[bytes, bytes, bytes,
                            type_keys_dict, type_download_list]:
        # fetch playlist
        print(f'fetching playlist ({stream_url})')
        r = self.session.get(stream_url)
        r.raise_for_status()
        m3u8_playlist_content = r.content
        m3u8_playlist_obj = m3u8.loads(m3u8_playlist_content.decode('utf-8'), stream_url)
        assert m3u8_playlist_obj.is_variant, f'm3u8 "{stream_url}" should be variant'

        # select variant
        best_quality_id = 0
        best_quality_br = 0
        print('available variants:')
        for i, stream_url in enumerate(m3u8_playlist_obj.playlists, start=1):
            codecs = stream_url.stream_info.codecs
            br = stream_url.stream_info.average_bandwidth or stream_url.stream_info.bandwidth
            print(f'  {i}: {codecs} {br // 1024}kbps ({(br * 60) // (1024 * 8)}KB per minute)')
            if br > best_quality_br:
                best_quality_id = i
                best_quality_br = br
        if len(m3u8_playlist_obj.playlists) == 1:
            print(f'selecting the only variant')
            variant_id = 1
        else:
            print(f'selecting best: {best_quality_id}')
            variant_id = best_quality_id
        variant_url = m3u8_playlist_obj.playlists[variant_id - 1].absolute_uri

        # fetch variant
        print(f'fetching variant ({variant_url})')
        r = self.session.get(variant_url)
        r.raise_for_status()
        m3u8_variant_content = r.content
        m3u8_variant_obj = m3u8.loads(m3u8_variant_content.decode('utf-8'), variant_url)

        # fetch keys and patch m3u8
        print('fetching key contents')
        key_dict: type_keys_dict = {}  # key_id, key_content
        for i, key in enumerate(m3u8_variant_obj.keys):
            key_url = key.absolute_uri

            key_id = f'{prefix}key_{i:05d}.key'

            print(f'key "{key_url}" -> "{key_id}"')
            r = self.session.get(key_url)
            r.raise_for_status()
            key_content = r.content

            key.uri = key_id
            key_dict[key_id] = key_content

        # get download url and patch m3u8
        print('patching playlist')
        download_list: type_download_list = []
        for i, segment in enumerate(m3u8_variant_obj.segments):
            segment_url = segment.absolute_uri
            ext_m = re.match(r'.*(\.[^.]*)$', segment_url)
            ext = '' if ext_m is None else ext_m.group(1)

            download_id = f'{prefix}segment_{i:05d}{ext}'

            segment.uri = download_id
            download_list.append((segment_url, download_id))

        m3u8_patched_content = m3u8_variant_obj.dumps().encode('utf-8')

        return m3u8_playlist_content, m3u8_variant_content, m3u8_patched_content, key_dict, download_list

    def download(self, dirname):
        with open(os.path.join(dirname, 'project.json'), 'r', encoding='utf-8') as f:
            project = json.load(f)
        queue_new = []
        for stream in project['streams']:
            queue = stream['download_list']
            for url, filename in queue:
                filename_full = os.path.join(dirname, filename)
                if os.access(filename_full, os.F_OK):
                    continue
                queue_new.append((url, filename_full, filename))
        if len(queue_new) == 0:
            print('Nothing to download!')
            return

        opt = DownloaderOptions()
        opt.proxies = self.session.proxies
        # opt.chunk_size = 1024
        opt.min_rate = 1
        # opt.queue_size = 8
        opt.hide_progress_bar = True
        dq = DownloadQueue(queue_new, opt)
        try:
            dq.run()
        finally:
            files = os.listdir(dirname)
            for file in files:
                if file.endswith(opt.temp_suffix):
                    os.remove(os.path.join(dirname, file))
        if len(dq.results) == 0:
            print('Download failed due to severe error!')
            return
        print('Download finished!')
        error_count = 0
        for (url, filename, info), (success, message) in zip(queue_new, dq.results):
            if not success:
                error_count += 1
                print(f'Error when downloading {filename} ({url}):\n{message}\n')
        if error_count > 0:
            print(f'{error_count} errors encountered')
            if error_count == len(queue_new):
                print('All files failed, try again or contact author!')
        else:
            print('All files done')

    def remux(self, dirname, ignore_missing=False):
        with open(os.path.join(dirname, 'project.json'), 'r', encoding='utf-8') as f:
            project = json.load(f)

        files = os.listdir(dirname)
        for stream in project['streams']:
            print('Checking...')
            if not ignore_missing:
                missing = []
                for url, filename in stream['download_list']:
                    if filename not in files:
                        missing.append(filename)
                if missing:
                    print(f'{len(missing)} files missing, abort')
                    return

            prefix = stream['prefix']
            filename = f'{prefix}out.m4a'
            print(f'Saving to "{filename}"')

            args = ['ffmpeg', '-hide_banner', '-y',
                    '-allowed_extensions', 'ALL',  # needed for .key keyfiles
                    '-i', stream['patched_file'],
                    '-c', 'copy',
                    '-movflags', '+faststart',
                    filename]
            p = subprocess.run(args, cwd=dirname)
            if p.returncode != 0:
                print('Something went wrong!')
            else:
                print('Done!')

    def download_images(self, dirname):
        print('start downloading images')
        with open(os.path.join(dirname, 'project.json'), 'r', encoding='utf-8') as f:
            project = json.load(f)

        with open(os.path.join(dirname, project['info_json']), 'r', encoding='utf-8') as f:
            info_json = json.load(f)

        paths = [
            ('pc_image_url',),
            ('sp_image_url',),
            ('episode', 'episode_parts', None, 'pc_image_url'),
            ('episode', 'episode_parts', None, 'sp_image_url'),
            ('episode', 'chapters', None, 'pc_image_url'),
            ('episode', 'chapters', None, 'sp_image_url'),
            ('casts', None, 'pc_image_url'),
            ('casts', None, 'sp_image_url'),
        ]
        urls = set()
        for path in paths:
            url_found = list(self._try_json_path(info_json, path))
            print(f'found {url_found} at path {path}')
            urls.update(url_found)

        for url in urls:
            print(f'download "{url}"')
            filename = os.path.join(dirname, self.filename_from_url(url))
            if os.access(filename, os.F_OK):
                print(f'removing existent file "{filename}"')
                os.remove(filename)
            p = subprocess.run(('wget', '-O', filename, url))
            p.check_returncode()

        print('download images done')

    @classmethod
    def _try_json_path(cls, obj, path) -> typing.Iterator[typing.Any]:
        if len(path) == 0:
            yield obj
            return
        x = path[0]
        remain = path[1:]
        if isinstance(x, int):
            assert isinstance(obj, list)
            yield from cls._try_json_path(obj[x], remain)
        elif x is None:
            assert isinstance(obj, list)
            for item in obj:
                yield from cls._try_json_path(item, remain)
        elif isinstance(x, str):
            assert isinstance(obj, dict)
            yield from cls._try_json_path(obj[x], remain)

    @staticmethod
    def filename_from_url(url):
        match = re.match(r'.*/([^/]*(?:\?.*)?)$', url)
        if match is not None:
            url = match.group(1)
        return url.replace('/', '%2F')

    def archive(self, dirname):
        print('start archiving to tar.xz')
        with open(os.path.join(dirname, 'project.json'), 'r', encoding='utf-8') as f:
            project = json.load(f)

        # remove artifacts
        files = os.listdir(dirname)
        for stream in project['streams']:
            prefix = stream['prefix']
            filename = f'{prefix}out.m4a'
            if filename in files:
                fullname = os.path.join(dirname, filename)
                print(f'removing artifact "{fullname}"')
                os.remove(fullname)

        # do archive
        archive_file = f'{dirname}.tar.xz'
        print(f'archiving to {archive_file}')
        try:
            with open(archive_file, 'wb') as f:
                tar = subprocess.Popen(('tar', '-c', dirname), stdout=subprocess.PIPE)
                xz = subprocess.Popen(('xz', '-9', '-e'), stdin=tar.stdout, stdout=f)
                tar.stdout.close()
                tar.wait()
                xz.wait()
                assert tar.returncode == 0
                assert xz.returncode == 0
        except Exception:
            if os.access(archive_file, os.F_OK):
                os.remove(archive_file)
            raise


if __name__ == '__main__':
    _dl = Downloader()
    _dl.set_proxy('127.0.0.1:1081')

    _dirname = 'test-pstl'
    _program_name = 'pstl'

    # _r = _dl.session.get(f'https://vcms-api.hibiki-radio.jp/api/v1/programs/{_program_name}',
    #                      headers={'X-Requested-With': 'XMLHttpRequest'})
    # _r.raise_for_status()
    # _info_raw = _r.content
    # _dl.create_project(_info_raw, _dirname)

    # _dirname = 'test-1234'
    # _dl.create_project_from_stream_id(1234, _dirname)

    # _dl.download(_dirname)
    # _dl.download_images(_dirname)
    # _dl.remux(_dirname)

    # _dl.archive(_dirname)
