from epf2src import *
from epf2src.InternalFileParser import *
from epf2src.commons import *
import sys, os, os.path, glob, subprocess, shutil, re

rootdir = ''

# region debug functions

def make_xml_in_dir(directory):
    '''
    Пробегает по директории directory и пытается все файлы по пути продублировать в xml
    Используется для анализа изменений, на собственно конвертацию не влияет
    '''

    for filename in glob.glob(os.path.join(os.curdir, directory, '*')):
        try:
            ones_object(filename).serialize()
        except:
            pass

    for filename in glob.glob(os.path.join(os.curdir, directory, '*', 'form')):
        try:
            ones_object(filename).serialize()
        except:
            pass


def take_from_81():

    '''
    возьмем из распакованной версии 8.1 некоторые файлы как есть
    это позволит быстрее отсеять критичные изменения
    :return:
    '''
    files = [
        'version'
        # , 'f7aa9e0f-862b-489a-8a81-1a6d6fba89f6'  # файл-ссылка на форму
        # , 'c8111449-a1ee-4eae-95e5-1d3688d73ad4'  # корень обработки
    ]


    for filename in files:
        shutil.copyfile('./downgrade_test_82.und/' + filename, './downgrade_test_82_saved.und/' + filename)


# endregion debug


# region main

def downgrade_single_dir(directory, templates):
    '''

    принимает на вход имя каталога (относительно текущего) с распакованной обработкой
    и начинает понижать в нем версию обработки
    '''

    descr_file = None

    rootdir = os.path.join(os.path.curdir, directory)
    # make_xml_in_dir(directory)

    # быстро пробежимся по файлу version
    with ones_object(os.path.join(rootdir, "version")) as ob:
        ob.object_as_list[0][0] = 106
        ob.serialize_back()

    # узнаем имя главного файла после root
    root_filename = os.path.join(rootdir, 'root')
    with ones_object(root_filename) as ob:
        descr_file = ob.value_by_address('1')

    # теперь наведаемся в этот файл: здесь сама обработка, ее формы, реквизиты
    with ones_object(os.path.join(rootdir, descr_file)) as ob:
        # ob.serialize()  # xml
        # cut_properties_at_address(ob, '3-1-6-2-0-1', 2)  # иногда не работает, надо понять, что это

        managed_forms = []  # сюда запишем гуиды управляемых форм, потом поудаляем их

        # еще надо вытащить ссылки на формы и их тоже сконвертировать
        for elem in ob.object_as_list[3][1][5] [2:]:
            form_guid = ob.original_value(elem)
            # тут еще хорошо бы вычеркивать управляемые формы автоматом
            downgrade_form_header_file(os.path.join(rootdir, form_guid), templates)
            ordinary_form_file = os.path.join(rootdir, form_guid + '.0', 'form')

            if os.path.exists(ordinary_form_file):
                # обычная форма, конвертируем
                downgrade_form_body_file(ordinary_form_file)
            else:
                # управляемая форма, кидаем в список на удаление
                # managed_forms.append(form_guid)
                os.remove(os.path.join(rootdir, form_guid + '.0'))  # сразу удалим файл на всякий случай
                managed_forms.append(elem)

        for guid in managed_forms:
            # пройдемся по управляемым формам и выкинем их их списка
            # а добавляем гуиды или же ключи?
            # попробуем ключи
            ob.object_as_list[3][1][5].remove(guid)


        # теперь хорошо бы пробежаться по СКД макетам и их тоже сконвертировать
        for elem in ob.object_as_list[3][1][4] [2:]:
            downgrade_skd(os.path.join(rootdir, ob.original_value(elem)))



        ob.object_as_list[3][1][5][1] = ob.object_as_list[3][1][5][1] - len(managed_forms)  # количество форм тоже уменьшим
        ob.serialize_back()  # и запишем обратно


def cut_properties_at_address(onesobj, address, until):
    '''
    Удаляет элементы тега в onesobj по указанному адресу
    Сакральный смысл: предполагается, что в формате для 8.2 свойств больше, чем в формате 8.1
    И новые свойства, скорее всего, располагаются в конце
    Поэтому для даунгрейда на 8.1 надо удалить какие-то свойства объекта, начиная с позиции until
    :param onesobj: ссылка на ones_object
    :param address: адрес тега в виде '3-1-6-2'
    :param until: до какого количества элементов в массиве надо порезать тег
    :return:
    лучше упаковать ее как метод объекта onesobj
    '''

    target = onesobj.object_as_list
    for i in address.split('-'):
        target = target[int(i)]

    for i in range(until, len(target)):
        target.pop()  # удаляем последний элемент списка


def exec_and_wait(command_text):
    '''
    Сокращение для запуска внешней программы
    '''
    return subprocess.Popen(command_text, shell=True, stdout=subprocess.PIPE).stdout.read()


def downgrade_form_header_file(filename, templates):
    '''
    конвертит маленький заголовочный файл формы
    Здесь вместо конвертации всего объекта будем извлекать из файла для 8.2 общие сведения
        и подставлять их в шаблон формы 8.1
    :param filename:
    :return:
    '''
    with ones_object(filename) as ob:
        # print(filename)
        # ob.serialize()  # xml
        template = templates['form_header']

        if ob.value_by_address('1-1-1-1-3-0') == 0:
            synonym = '""'  # если синоним не задан
        else:
            synonym = ob.value_by_address('1-1-1-1-3-2')

        patterns = {
            'Гуид': ob.value_by_address('1-1-1-1-1-2')
            , 'Имя': ob.value_by_address('1-1-1-1-2')
            , 'Синоним': synonym
            , 'Комментарий': ob.value_by_address('1-1-1-1-4')
        }

        text_to_file(filename, replace_patterns(template, patterns))


def downgrade_form_body_file(filename):
    '''
    конвертит основной файл формы
    :param filename:
    :return:
    '''
    with ones_object(filename) as ob:

        # 1. Ищем расположение реквизитов
        # 2. Удаляем однин элемент в середине
        # 3. Сериализуем обратно

        for requisite in ob.object_as_list[2][2][1:]:  # или с 1?
            requisite.pop(2)  #удалим один лишний нолик в середине

        ob.serialize_back()
        # ob.serialize()


def downgrade_skd(filename):
    '''
    Конвертит макет СКД при необходимости (сначала проверяет, что за макет попался)
    Если попался именно СКД, то вырезает из него секцию <settingsVariant>.*<\/settingsVariant>
    Эта секция не поддерживается в 8.1

    Здесь жуткие костыли, по факту пересобираем схему заново из кусков.
    Может работать нестабильно.

    :param filename:
    :return:
    '''
    with ones_object(filename) as ob:

        if ob.value_by_address('1-1') == 6:  # это СКД

            unknown_bytes = 27  # количество байт в начале, которые не будем конвертировать

            bytes_old = open(filename + '.0', 'rb').read()
            text = bytes_old[unknown_bytes:].decode('utf-8')

            pattern = re.compile(r'<settingsVariant>.*<\/settingsVariant>', flags = re.DOTALL)
            text = pattern.sub('', text)  # удалим варианты настроек

            pattern = re.compile(r'<dataCompositionSchema.*<\/dataCompositionSchema>', flags = re.DOTALL + re.IGNORECASE)
            text = pattern.search(text).group(0) # вытащим корень отдельно

            header_81 = r'<dataCompositionSchema xmlns="http://v8.1c.ru/8.1/data-composition-system/schema" xmlns:dcscom="http://v8.1c.ru/8.1/data-composition-system/common" xmlns:dcscor="http://v8.1c.ru/8.1/data-composition-system/core" xmlns:dcsset="http://v8.1c.ru/8.1/data-composition-system/settings" xmlns:v8="http://v8.1c.ru/8.1/data/core" xmlns:v8ui="http://v8.1c.ru/8.1/data/ui" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            # такой заголовок имеет СКД в 8.1. В 8.2 он гораздо короче.

            pattern = re.compile(r'<dataCompositionSchema.*>', flags = re.IGNORECASE)
            text = pattern.sub(header_81, text)  # удалим варианты настроек


            text = r'<?xml version="1.0" encoding="UTF-8"?>' + os.linesep + text
            open(filename + '.0', 'wb').write(text.encode('utf-8'))


def replace_patterns(text, patterns):
    '''
    Протая замена текста по шаблонам
    '''

    for key, value in patterns.items():
        text = text.replace('#' + key, value)
    return text


def get_templates(path_to):
    '''
    Возвращает коллекцию Ключ-Значение с шаблонами
    Шаблоны должны лежать в папке path_to
    '''
    templates = dict()
    for filename in glob.glob(os.path.join(path_to, '*')):
        templates[os.path.basename(filename)] = text_from_file(filename)
    return  templates


def convert_epf(epf_name):

    templates = get_templates('./templates')
    epf_unpacked_name = epf_name + '.und'  # распаковываем epf в эту же папку
    epf_result_name = epf_name.replace('.epf', '_81.epf')  # и результат сюда же положим

    exec_and_wait('Unpackv8.exe -parse ' + epf_name + ' ' + epf_unpacked_name)
    # распакуем эталонный файл, сохраненный в конфигураторе 8.2

    downgrade_single_dir(epf_unpacked_name, templates)
    # собственно алгоритм. Преобразование файлов в указанном каталоге

    exec_and_wait('Unpackv8.exe -build ' + epf_unpacked_name + ' ' + epf_result_name)
    # соберем все обратно в новый файл рядом

    shutil.rmtree(epf_unpacked_name)
    # и почистим за собой


# endregion main


if __name__ == '__main__':

    if len(sys.argv) == 2:
        # запуск из командной строки
        for fn in glob.glob(os.path.join('.', sys.argv[1])):
            convert_epf(fn)
    else:
        # запуск из PyCharm - отладка
        os.chdir(r'c:\Git\onecDecoder')
        convert_epf('test.epf')

