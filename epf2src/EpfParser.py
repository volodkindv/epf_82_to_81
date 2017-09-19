import os.path, glob, zipfile, uuid, gzip
from multiprocessing import cpu_count, Pool
import datetime

from collections import namedtuple

from .InternalFileParser import ones_object
from .ExtractProc_3 import *
from hashlib import md5
from .commons import *
# from .custom_code import *  # времянка - потестировать

ones_internal_file = namedtuple('ones_internal_file', 'guid obj_type')

class epf_parser_settings:
    def __init__(self, multiprocessing=True, split_module=True):
        self.multiprocessing = multiprocessing
        self.split_module = split_module

#settings = epf_parser_settings(multiprocessing=False, split_module=False)
settings = epf_parser_settings(multiprocessing=False)


def versions_file_arrange(filename, paste_null_guid=False):
    """
    Упорядочит внутренний файл versions
    """

    # return

    with ones_object(filename) as versions_object:

        location = os.path.dirname(filename)  # посмотрим остальные файлы/каталоги внутри этой папки

        pairs = []
        for i in range(0, int(len(versions_object.object_as_list)/2)):  # здесь всегда четное количество элементов, да ведь?
            pairs.append(
                    [versions_object.object_as_list[i*2]
                        , versions_object.object_as_list[i*2+1]]
            )
            pass

        for i in range(1, len(pairs)):
            if paste_null_guid:
                # при разборке epf
                new_value = '00000000-0000-0000-0000-000000000000'
            else:
                _filename = versions_object.original_value(pairs[i][0]).replace('"', '')
                if _filename != '""'\
                        and os.path.exists(os.path.join(location, _filename)):
                    new_value = _md5(os.path.join(location, _filename))
                else:
                    # new_value = '00000000-0000-0000-0000-000000000000'
                    new_value = str(uuid.uuid1())  # в любой непонятной ситуации будем ставить рандомный гуид
                    # print(new_value)


                    # при сборке epf
                # if pairs[i][0].find(module_object_guid + '.0') >= 0 \
                #         and module_object_guid != '':
                #     new_value = module_object_md5
                # else:
                #     new_value = str(uuid.uuid1())
                # new_value = module_object_md5  # ТЕСТ!!!
                # какой MD5 ставить?


            versions_object.set_original_text_value(pairs[i][1], '' + new_value + '')

        versions_object.serialize_back(filename)  # вернем в этот же файл

        text = text_from_file(filename).replace(',', ',' + os.linesep)
        text_to_file(filename, text)

        # versions_object.serialize_back(filename + '.new')  # вернем в этот же файл


def parse_root(unpacked_dir):

    result = []

    # этот файл всегда есть в epf, он короткий, задает только идентификатор текущего объекта.
    # Все кишки лежат в файле с именем, равным этому идентификатору
    with ones_object(os.path.join(unpacked_dir, 'root')) as rootfile_array:
        descr_guid = rootfile_array.value_by_address('1').replace('_', '-')
        result.append(ones_internal_file(obj_type='ФайлОписаний', guid=descr_guid))

    # Этот файл содержит список форм, реквизитов, табличных частей и т.д.
    with ones_object(os.path.join(unpacked_dir, descr_guid), '_root_second') as second_root_file:

        result.append(ones_internal_file(obj_type='МодульОбъекта', guid=second_root_file.value_by_address('3-1-1-3-1-1-2')))

        for guid in second_root_file.value_by_address('3-1-5')[2:]:
            # формы лежат в 3-1-5, в количестве 3-1-5, начиная с элемента 2
            result.append(ones_internal_file(obj_type='Формы', guid=second_root_file.original_value(guid)))

        for guid in second_root_file.value_by_address('3-1-4')[2:]:
            # макеты лежат по адресу 3-1-4, начиная с элемента 2
            result.append(ones_internal_file(obj_type='Макеты', guid=second_root_file.original_value(guid)))

    return result


# метод будет обрабатывать единичный файл/папку filename и складывать в какое-то место из dest.
def unpack_single_object(unpacked_dir, source_dir, guid, obj_type):

    action = 'unpack'
    if obj_type == 'МодульОбъекта':

        if guid is not None:
            process_object_module(unpacked_dir, source_dir, guid, action)

    elif obj_type == 'Формы':

        if os.path.isdir(os.path.join(unpacked_dir, guid + '.0')):
            process_ordinary_form(unpacked_dir, source_dir, guid, action)
        else:
            process_managed_form(unpacked_dir, source_dir, guid, action)

    elif obj_type == 'Макеты':

        process_maket(unpacked_dir, source_dir, guid, action)

    else:
        pass


# Метод, обратный для unpack_single_object
def pack_single_object(unpacked_dir, object_dir, obj_type):

    action = 'pack'
    guid = text_from_file(os.path.join(object_dir, 'guid'))  # гуид будет лежать в этой же папке рядом

    if obj_type == 'МодульОбъекта':

        process_object_module(unpacked_dir, object_dir, guid, action)

    elif obj_type == 'Формы':

        # здесь надо как-то понять, что за форма перед нами: обычная или управляемая
        if guid.endswith('.ordinary'):
        # if os.path.isdir(os.path.join(unpacked_dir, guid + '.0')):
            process_ordinary_form(unpacked_dir, object_dir, guid.replace('.ordinary', ''), action)
        else:
            process_managed_form(unpacked_dir, object_dir, guid.replace('.managed', ''), action)

    elif obj_type == 'Макеты':

        process_maket(unpacked_dir, object_dir, guid, action)

    else:
        pass


def split_module_text(filename):
    if settings.split_module:
        extract_one(filename)


# region single_object_processing


# Обработка модуля объекта
def process_object_module(unpacked_dir, source_dir, guid, action):

    # NB: модуля объекта может и не быть
    if action == 'unpack':
        new_folder_name = os.path.join(source_dir, '_Объект_')
        new_file_name = os.path.join(new_folder_name, 'Модуль.1s')
        text_to_file(os.path.join(new_folder_name, 'guid'), guid)  # запишем гуид
        if os.path.exists(os.path.join(unpacked_dir, guid + '.0')):
            # Тонкость: модуль объекта может быть папкой с файлом text внутри, а может быть конечным файлом. Упс.
            if os.path.isdir(os.path.join(unpacked_dir, guid + '.0')):
                os.rename(os.path.join(unpacked_dir, guid + '.0', 'text'), new_file_name)
            else:
                os.rename(os.path.join(unpacked_dir, guid + '.0'), new_file_name)
            split_module_text(new_file_name)  # раскидаем текст модуля на отдельные файлы

    elif action == 'pack':
        assembled_file_name = os.path.join(source_dir, 'Модуль.1s')
        if os.path.exists(assembled_file_name+'s'):
            assemble_one(assembled_file_name)
            if os.path.isdir(os.path.join(unpacked_dir, guid + '.0')):
                os.replace(assembled_file_name, os.path.join(unpacked_dir, guid + '.0', 'text'))
            else:
                os.replace(assembled_file_name, os.path.join(unpacked_dir, guid + '.0'))



# Обработка макета
def process_maket(unpacked_dir, source_dir, guid, action):
    # макеты тоже стоит сжимать, если они не текстовые
    # но текстовые можно оставить на когда-нибудь потом.
    if action == 'unpack':
        with ones_object(os.path.join(unpacked_dir, guid)) as short_descr:
            object_name = short_descr.value_by_address('1-2-2').replace('"', '')
            new_folder_name = os.path.join(source_dir, 'Макеты', object_name)
            new_file_name = os.path.join(new_folder_name, 'Макет')
            erase_and_create_folder(new_folder_name)
            os.rename(os.path.join(unpacked_dir, guid + '.0'), new_file_name)
            hide_int_file_from_vsc(new_file_name, action)
            text_to_file(os.path.join(new_folder_name, 'guid'), guid)  # запишем гуид
            #  тут еще можно подумать про УФ и ее встроенные макеты: рекурсивный разбор, соответствие имен и т.д.
    elif action == 'pack':
        new_file_name = os.path.join(source_dir, 'Макет')
        hide_int_file_from_vsc(new_file_name, action)
        os.replace(new_file_name, os.path.join(unpacked_dir, guid + '.0'))
        # shutil.copy(new_file_name, os.path.join(unpacked_dir, guid + '.0'))


# Обработка файлов обычной формы
def process_ordinary_form(unpacked_dir, source_dir, guid, action):

    if action == 'unpack':
        with ones_object(os.path.join(unpacked_dir, guid), 'Форма') as short_descr:
            object_name = short_descr.value_by_address('1-1-1-1-2').replace('"', '')
            new_folder_name = os.path.join(source_dir, 'Формы', object_name)
            os.makedirs(new_folder_name)

            path_to_bare_form = os.path.join(source_dir, 'ФайлыФорм', object_name + '.form')
            os.rename(os.path.join(unpacked_dir, guid + '.0', 'form'), path_to_bare_form)
            #  это сам файл формы - временно можно убрать

            with ones_object(path_to_bare_form, 'Форма') as form_obj:
                form_obj.Arrange()  # скинем счетчик сохранений и т.д.
                form_obj.serialize_back(path_to_bare_form)
                # form_obj.serialize()

            hide_int_file_from_vsc(path_to_bare_form, action)

            name_of_module_file = os.path.join(unpacked_dir, guid + '.0', 'module')
            new_module_file = os.path.join(new_folder_name, 'Модуль.1s')

            os.rename(name_of_module_file, new_module_file)
            split_module_text(new_module_file)

            text_to_file(os.path.join(new_folder_name, 'guid'), guid + '.ordinary')  # запишем гуид

            # os.remove(filename)  # удаляем старый файл формы
            # obj.serialize(dest_filename)  # вместо него пишем новый, распарсенный

    elif action == 'pack':
        # и поищем сам файл формы
        object_name = os.path.basename(source_dir)
        path_to_bare_form = os.path.abspath(os.path.join(source_dir, '..', '..', 'ФайлыФорм', object_name + '.form'))
        hide_int_file_from_vsc(path_to_bare_form, action)
        target_dir = os.path.join(unpacked_dir, guid + '.0')
        erase_and_create_folder(target_dir)
        # shutil.copy(path_to_bare_form, os.path.join(target_dir, 'form'))
        shutil.move(path_to_bare_form, os.path.join(target_dir, 'form'))

        assembled_file_name = os.path.join(source_dir, 'Модуль.1s')
        assemble_one(assembled_file_name)

        os.replace(assembled_file_name, os.path.join(target_dir, 'module'))


# Обработка файла управляемой формы
def process_managed_form(unpacked_dir, source_dir, guid, action):

    if action == 'unpack':
        filename = os.path.join(unpacked_dir, guid)
        with ones_object(os.path.join(unpacked_dir, guid)) as short_descr:
            object_name = short_descr.value_by_address('1-1-1-1-2').replace('"', '')
            new_folder_name = os.path.join(source_dir, 'Формы', object_name)
            os.makedirs(new_folder_name)

        new_module_file = os.path.join(new_folder_name, 'Модуль.1s')
        replace_module_of_managed_form(filename + '.0', new_module_file, 'unpack')
        split_module_text(new_module_file)
        text_to_file(os.path.join(new_folder_name, 'guid'), guid + '.managed')  # запишем гуид

        path_to_bare_form = os.path.abspath(os.path.join(source_dir, 'ФайлыФорм', object_name + '.form'))
        os.rename(filename + '.0', path_to_bare_form)

        # ones_object(path_to_bare_form, 'УправляемаяФорма').serialize()  # пересохраним в XML для анализа

        hide_int_file_from_vsc(path_to_bare_form, action)

    elif action == 'pack':
        assembled_file_name = os.path.join(source_dir, 'Модуль.1s')
        assemble_one(assembled_file_name)

        # это файл управляемой формы в und, в нем код модуля уже заменен на магическую строку
        object_name = os.path.basename(source_dir)
        path_to_bare_form = os.path.abspath(os.path.join(source_dir, '..', '..', 'ФайлыФорм', object_name + '.form'))
        hide_int_file_from_vsc(path_to_bare_form, action)
        replace_module_of_managed_form(path_to_bare_form, assembled_file_name, 'pack')
        # shutil.copy(path_to_bare_form, os.path.join(unpacked_dir, guid + '.0'))
        shutil.move(path_to_bare_form, os.path.join(unpacked_dir, guid + '.0'))
        os.remove(assembled_file_name)  # почистим


def hide_int_file_from_vsc(filename, action):
    """
    сжимает файл формы в бинарный формат, чтобы избежать мержа гитом
    такое временное решение, пока не придумал, как сбрасывать бестолковые изменения таких файлов
    """

    bypass_this_action = False  # здесь будем переключать

    # не нравится: в одном действии старый файл удаляется, в другом - остается.

    if not bypass_this_action:
        zipfilename = filename + '.zip'

        if action == 'unpack':
            with zipfile.ZipFile(zipfilename, 'w') as z:
                dt = 946666800 # 2000-01-01
                os.utime(filename, (dt, dt))  # чтобы не менялась сигнатура zip файла, принудительно сбросим время создания файла на фиксированное
                z.write(filename, arcname=os.path.basename(filename), compress_type=zipfile.ZIP_DEFLATED)
            os.remove(filename)
        elif action == 'pack':
            with zipfile.ZipFile(zipfilename, 'r') as z:
                member = z.filelist[0]
                z.extract(member, os.path.dirname(filename))
    else:
        zipfilename = filename + '.txt'

        if action == 'unpack':
            os.rename(filename, zipfilename)
        elif action == 'pack':
            shutil.copy(zipfilename, filename)


# Вспомогательная функция для извлечения/упаковки модуля управляемой формы
def replace_module_of_managed_form(form_filename, module_filename, action):
    """
    В/из файла управляемой формы form_filename вливаем/извлекаем текст модуля.
    В данный момент плохо: если код модуля пустой, то он плох заменяется.
    """
    replace_text = '#extracted#'
    if action == 'unpack':
        with ones_object(form_filename, 'УправляемаяФорма') as form_obj:
            # print('maket ' + maket_id)
            text_of_module = form_obj.value_by_address('2')
            form_obj.object_as_list[2] = replace_text  # уберем из описания формы код ее модуля
            form_obj.Arrange()  # скинем счетчик сохранений и т.д.
            form_obj.serialize_back(form_filename)


            text_of_module = text_of_module[1:-1].replace('""', '"')
            open(module_filename, 'w', encoding='utf-8').write(text_of_module)
            # двойные кавычки заменим на одинарные. Открывающую и закрывающую кавычку выкинем.

    elif action == 'pack':
        full_text = text_from_file(form_filename)
        _t = text_from_file(module_filename)
        _t = '"' + _t.replace('"', '""') + '"'
        replaced = full_text.replace(replace_text, _t)
        text_to_file(form_filename, replaced)


# endregion


def _md5(_filename):
    m = md5()
    if os.path.isdir(_filename):
        if os.path.exists(os.path.join(_filename, 'text')):
            m.update(open(os.path.join(_filename, 'text'), 'rb').read())
        elif os.path.exists(os.path.join(_filename, 'form')):
            m.update(open(os.path.join(_filename, 'form'), 'rb').read())
        else:
            return '00000000-0000-0000-0000-000000000000'  # нет сил

    elif os.path.exists(_filename):
        m.update(open(_filename, 'rb').read())
    else:
        return  '00000000-0000-0000-0000-000000000000'  # нет сил

    hash = m.hexdigest()
    # print(hash)
    return hash[0:8] + '-' + hash[8:12] + '-' + hash[12:16] + '-' + hash[16:20] + '-' + hash[20:]
    # 916b52b - 462 - 4a8 - 788 - ad51c01949ba
    # 00000000 - 0000 - 0000 - 0000 - 000000000000


def compileFile(file_name, source_dir, v8unpack_file):
    # все вложенные модули из текущей папки положить вовнутрь модуля
    # нужны параметры: имя разбираемого файла, имя папки под исходники,

    unpack_dir = file_name + '.unpack'
    if os.path.exists(unpack_dir):
        shutil.rmtree(unpack_dir)  # почистим за собой после прошлого раза

    shutil.copytree(os.path.join(source_dir, 'Прочее'), os.path.abspath(unpack_dir))

    # Теперь соберем обратно тексты форм
    parameters = []

    parameters.append([unpack_dir, os.path.join(source_dir, '_Объект_'), 'МодульОбъекта'])

    for folder in glob.glob(os.path.join(source_dir, 'Формы', '*')):
        parameters.append([unpack_dir, folder, 'Формы'])

    for folder in glob.glob(os.path.join(source_dir, 'Макеты', '*')):
        parameters.append([unpack_dir, folder, 'Макеты'])

    if settings.multiprocessing:
        # """Многопоточный вариант"""
        # создадим столько воркеров, сколько ядер у нашего процессора
        with Pool(cpu_count()) as p:
            p.starmap(pack_single_object, parameters)
    else:
        """Вариант в один поток, для отладки"""
        for param in parameters:
            pack_single_object(param[0], param[1], param[2])

    # вот здесь можно поискать гуид модуля объекта
    module_GUID = text_from_file(os.path.join(source_dir, '_Объект_', 'guid'))
    versions_file_arrange(os.path.join(unpack_dir, 'versions'), False)
    # try:
    #     module_md5 = _md5(os.path.join(unpack_dir, module_GUID + '.0', 'text'))
    #     versions_file_arrange(os.path.join(unpack_dir, 'versions'), False, module_GUID, module_md5)
    # except:
    #     versions_file_arrange(os.path.join(unpack_dir, 'versions'), False)
    #     print('не удалось посчитать md5')


    exec_and_wait('"%s" -build "%s" "%s"' % (v8unpack_file, unpack_dir, file_name))
    shutil.rmtree(unpack_dir)


def decompileFile(file_name, source_dir, v8unpack_file):
    # извлечь все вложенные модули в текущую папку

    unpack_dir = file_name + '.unpack'

    erase_and_create_folder(source_dir)
    erase_and_create_folder(unpack_dir)

    # не хватает: расположения UnpackV8.exe
    exec_and_wait('"%s" -parse "%s" "%s"' % (v8unpack_file, file_name, unpack_dir))

    # из распакованной папки рассортируем все файлы по местам и дадим человеческие имена
    versions_file_arrange(os.path.join(unpack_dir, 'versions'), True)

    # подготовим папки, куда будем раскладывать все
    for folder in ('_Объект_', 'Формы', 'Макеты', 'ФайлыФорм'):
        erase_and_create_folder(os.path.join(source_dir, folder))

    parameters = []
    for every in parse_root(unpack_dir):
        parameters.append([unpack_dir, source_dir, every.guid, every.obj_type])

    if settings.multiprocessing:
        # """Многопоточный вариант"""
        # создадим столько воркеров, сколько ядер у нашего процессора
        with Pool(cpu_count()) as p:
            p.starmap(unpack_single_object, parameters)
    else:
        """Вариант в один поток, для отладки"""
        for param in parameters:
            unpack_single_object(param[0], param[1], param[2], param[3])

    # Все, что останется внутри unpacked_dir, упакуем в zip
    shutil.copytree(unpack_dir, os.path.join(source_dir, 'Прочее'))

    # Почистим и снова распакуем на время отладки
    shutil.rmtree(unpack_dir)


def main():
    pass

def test():
    testfilename = r'c:\Git\source_1c_test\versions'
    versions_file_arrange(testfilename)
    pass

if __name__ == '__main__':
    # main()
    test()
