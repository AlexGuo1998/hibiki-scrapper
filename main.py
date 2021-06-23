# 1. read config, read database
# 2. get json
# 3. test: need update?
# 4. do work

import importlib
import json
import time

import requests

import wxpush


class Loader:
    Empty = object()

    def __init__(self, config: dict):
        self.session = requests.Session()
        self.session.headers['User-Agent'] = config.get('user_agent', '')
        proxy_config = config.get('proxy', {})
        self.set_proxy(http_proxy=proxy_config.get('http_proxy', None),
                       https_proxy=proxy_config.get('https_proxy', self.Empty))

    def set_proxy(self, http_proxy, https_proxy=Empty):
        if https_proxy is self.Empty:
            https_proxy = http_proxy
        proxy_dict = {}
        if http_proxy is not None:
            proxy_dict['http'] = http_proxy
        if https_proxy is not None:
            proxy_dict['https'] = https_proxy
        self.session.proxies = proxy_dict

    def run(self, program_name, save, program_config):
        # run with "live" json info
        info_json, info_raw = self.get_program_info(program_name)
        return self._run_implementation(program_name, save, program_config, info_json, info_raw)

    def run_archived(self, program_name, save, program_config, info_raw_list):
        # run with "archived" json info
        result = False
        for i, info_raw in enumerate(info_raw_list):
            print('')
            print(f'{i} of {len(info_raw_list)}')
            print('')
            info_json = json.loads(info_raw.decode('utf-8'))
            result = self._run_implementation(program_name, save, program_config, info_json, info_raw) or result
        return result

    def _run_implementation(self, program_name, save, program_config, info_json: dict, info_raw: bytes):
        episode_info = info_json['episode']
        episode_id: int = episode_info['id']
        episode_name: str = episode_info['name']
        episode_time: str = episode_info['updated_at']

        if (
                save.get('episode_id') != episode_id or
                save.get('episode_name') != episode_name or
                save.get('episode_time') != episode_time
        ):
            # changed, load handler
            print(f'new episode {episode_id} ({episode_name}, {episode_time})')
            handler = importlib.import_module(f'handler_{program_name}')
            data = {
                'info_raw': info_raw,
                'info_json': info_json,
                'session': self.session,
                'save': save.setdefault('callback_save', {}),
                'config': program_config,
            }
            handler.run(data)

            # save only on success
            save['episode_id'] = episode_id
            save['episode_name'] = episode_name
            save['episode_time'] = episode_time
            return True
        else:
            print(f'no new episode')
            return False

    def get_program_info(self, program_name):
        r = self.session.get(f'https://vcms-api.hibiki-radio.jp/api/v1/programs/{program_name}',
                             headers={'X-Requested-With': 'XMLHttpRequest'})
        r.raise_for_status()
        info_raw = r.content
        info_json = r.json()
        return info_json, info_raw


def main():
    print('')
    print('=' * 80)
    print('')
    print(time.strftime('%Y-%m-%d %H:%M:%S'))

    with open('config.json', 'r', encoding='utf-8') as f:
        config: dict = json.load(f)
    try:
        with open('save.json', 'r', encoding='utf-8') as f:
            save: dict = json.load(f)
    except FileNotFoundError:
        print('warning: save.json not found, generating new')
        save: dict = {}
    programs = config['programs']
    loader = Loader(config['main_config'])
    wxpush.WxPusher_TOKEN = config['main_config']['push']['token']
    wxpush.WxPusher_UIDs = config['main_config']['push']['uid_list']

    save_changed = False
    first = True
    for program_name in programs:
        if first:
            first = False
        else:
            print('')

        print(f'check program {program_name}')
        try:
            program_save = save.setdefault(program_name, {})
            program_config = config.get('program_config', {}).get(program_name, {})
            has_new = loader.run(program_name, program_save, program_config)
            if has_new:
                save_changed = True
        except Exception:
            # hint: you may want to "raise" here when debugging
            import traceback
            exc_text = traceback.format_exc()
            print(f'Exception:\n{exc_text}')
            wxpush.sendNotification(f'HiBiKi scraping exception:\n{exc_text}',
                                    summary='HiBiKi scraping exception')

    if save_changed:
        with open('save.json', 'w', encoding='utf-8') as f:
            json.dump(save, f, ensure_ascii=False, indent=4)


def main_archived():
    print('')
    print('=' * 80)
    print('')
    print(time.strftime('%Y-%m-%d %H:%M:%S'))
    with open('config.json', 'r', encoding='utf-8') as f:
        config: dict = json.load(f)
    with open('save.json', 'r', encoding='utf-8') as f:
        save: dict = json.load(f)

    loader = Loader(config['main_config'])

    program_name = 'xxx'
    json_list = [
        # 'xxx_1/program_info.json',
        # 'xxx_2/program_info.json',
    ]

    info_raw_list = []
    for json_file in json_list:
        with open(json_file, 'rb') as f:
            info_raw_list.append(f.read())

    program_save = save.setdefault(program_name, {})
    program_config = config.get('program_config', {}).get(program_name, {})
    loader.run_archived(program_name, program_save, program_config, info_raw_list)

    with open('save.json', 'w', encoding='utf-8') as f:
        json.dump(save, f, ensure_ascii=False, indent=4)


if __name__ == '__main__':
    main()
    # main_archived()
