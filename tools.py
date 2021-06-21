import os


def find_valid_filename(filename: str, ext=None):
    if ext is None:
        i = filename.rfind('.')
        if i == -1:
            ext = ''
        else:
            ext = filename[i:]
    else:
        assert filename.endswith(ext)
    if len(ext) > 0:
        filename = filename[:-len(ext)]
    add = ''
    add_num = 0
    while os.access(filename + add + ext, os.F_OK):
        add_num += 1
        add = f'.{add_num}'
    return filename + add + ext


def rename_file(filename, ext=None):
    new_filename = find_valid_filename(filename, ext)
    os.rename(filename, new_filename)
