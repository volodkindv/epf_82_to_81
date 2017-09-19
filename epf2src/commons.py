import os, shutil, subprocess, base64

delimiter = '\r\n'
beginning = r'{1,' + delimiter + r'{#base64:'
ending = r'}' + delimiter + r'}'


def text_to_file(_filename, text):
    with open(_filename, 'w', encoding='utf-8') as f:
        f.write(text)


def text_from_file(_filename):
    with open(_filename, 'r', encoding='utf-8') as f:
        return f.read()


def erase_and_create_folder(folder):
    if os.path.exists(folder):
        shutil.rmtree(folder)  # почистим папку, потом пересоздадим
    os.makedirs(folder)


def exec_and_wait(command_text):
    return subprocess.Popen(command_text, shell=True, stdout=subprocess.PIPE).stdout.read()  # распаковали файл


def base64_2_bin(filename, newfilename):
    """Извлекает base64 значение из распакованного файла с макетом fileName
    и записывает извлеченный бинарник в new_file_name"""

    with open(filename, 'r', encoding='utf-8') as source:
        _str = source.read()
        len_of_beginning = len(beginning)
        len_of_end = len(ending)
        short_str = _str[len_of_beginning : -len_of_end+1].replace('\n', '').replace('\r', '')
        binary_value = base64.b64decode(short_str, validate=True)
        open(newfilename, 'wb').write(binary_value)


def bin_2_base64(filename, newfilename):
    """Извлекает base64 значение из распакованного файла с макетом fileName
    и записывает извлеченный бинарник в new_file_name"""

    with open(filename, 'rb') as source:
        base64_value = base64.b64encode(source.read())
        _str = beginning + base64_value.decode() + ending
        # with open(newfilename, 'w', encoding='utf-8') as out_file:
        with open(newfilename, 'wb') as out_file:
            out_file.write('\ufeff'.encode())  # BOM
            out_file.write(_str.encode())
            # out_file.write(_str)


