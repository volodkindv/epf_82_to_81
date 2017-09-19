import os, re, subprocess, time, shutil, sys, glob, argparse
from multiprocessing import Pool  # для многопоточной раскладки
from enum import Enum
import cProfile  # анализ производительности

settings = {'extract_included_epf': False,  # если есть макеты, в которых находятся epf, то они будут тоже разобраны
            'multiprocessing': False,  # выполнять разбивку в несколько процессов
            'use_lxml': True,  # lxml - адски быстрая работа с xml.
            'try_givenames': True,  # если функция givenames падает - продолжить выполнение
            'split_module_text': False}  # разбивать тексты модуле на отдельные файлы (методы)

# для работы с XML есть 2 библиотеки:
if settings['use_lxml']:
    from lxml import etree as ET  # работает гораздо быстрее, но требует установки через pip
else:
    import xml.etree.cElementTree as ET  # штатная

from .ExtractProc_3 import extract_one  # найдено в GComp и адаптировано под python 3.5
from .ones_classes import get_ones_types, get_onec_types_ext  # сюда буду выносить описание типов в 1С
from .ones_classes import get_dict_of_form_elements  # гуиды типов элементов управления на формах
from .commons import *


onectypes = {}  # словарь словарей. На первом уровне - типы элементов (главное окно, кнопка, ...) На втором - порядковые номера элементов и их имена
profiler_results = {}

class SubFolders(Enum):
    # "перечисление" с именами вложенных каталогов для src
    binary = 'Макеты'
    forms = 'Формы'
    other = 'Прочее'


class ReplacesForForms:
    """перечень замен, произведенных над исходным текстом формы
    Пожалуй, стоит перевести на структуру, или вообще встроить в родительский класс"""
    replacenumber = 0
    textreplaces = {}
    base64replaces = {}

# https://habrahabr.ru/company/mailru/blog/202832/
def profile(func):
    """Decorator for run function profile"""
    def wrapper(*args, **kwargs):
        profile_filename = func.__name__ + '.prof'
        profiler = cProfile.Profile()
        result = profiler.runcall(func, *args, **kwargs)
        # profiler.dump_stats(profile_filename)
        profiler.print_stats()
        # with open(profile_filename, 'w') as f:
        #     f.write(profiler.print_stats())
        return result
    return wrapper

def profiler_decor(func):
    """
    Декоратор-профайлер
    Надо научиться отключать при multiprocessing == True
    """

    def wrapper(*args, **kwargs):

        global profiler_results

        funcname = func.__name__
        _startTime = time.time()

        res = func(*args, **kwargs) # выполняем обернутую функцию

        l_time = (time.time() - _startTime)

        if funcname in profiler_results:
            profiler_results[funcname] = profiler_results[funcname] + l_time
        else:
            profiler_results[funcname] = l_time
        return res

    return wrapper


class _Profiler(object):
    """
    класс для замеров времени выполнения различных функций / строк кода
    """

    funcname = ''
    profiler_results = {}

    def __init__(self, fn='', pr=None):
        if pr is None:
            pr = {}
        self.profiler_results = pr
        self.funcname = fn

    def __enter__(self):
        self._startTime = time.time()

    def __exit__(self, type, value, traceback):
        l_time = (time.time() - self._startTime)

        if self.funcname in self.profiler_results:
            self.profiler_results[self.funcname] = self.profiler_results[self.funcname] + l_time
        else:
            self.profiler_results[self.funcname] = l_time

    def print_results(results):
        """выведем результаты красиво"""
        for el in results:  # results - не локальные!
            print(str(results[el])[:5], '\t: ', el)
            # print("Elapsed time: {:.3f} sec".format(l_time))



# region Commons
def indent(elem, level=0):
    """
    готовит ElementTree для pretty print
    не нужно при работе с lxml
    """
    i = "\n" + level * "\t"
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "\t"
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for elem in elem:
            indent(elem, level + 1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i


# @profiler_decor
def getxmlbyindexes(root, indexes):
    """
    Возвращает элемент по последовательности индексов. Это упрощенный аналог xpath
    """
    for i in indexes:
        root = root.getchildren()[i]
    return root


# endregion


class ones_object(object):
    """класс для хранения объекта 1С, полученного из файла на диске"""
    filename = None
    ones_type = None
    replaces = None
    object_as_list = None
    onec_types_ext = None  # новый формат типов, пока что закинем прямо сюда

    def __enter__(self):
        return self
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def __init__(self, filename='1', ones_type=''):
        self.ones_type = ones_type
        self.filename = filename
        self.replaces = ReplacesForForms()
        # и сразу прочитаем
        self.object_as_list = self.filetolist()
        self.onec_types_ext = get_onec_types_ext()

    # @profiler_decor
    def original_value(self, cur):
        # вернет исходное значение из словаря замен

        if type(cur) == str:
            if cur.startswith('text'):
                return self.replaces.textreplaces['"' + cur + '"']
            elif cur.startswith('base64'):
                return self.replaces.base64replaces['"' + cur + '"']
            else:
                return cur.replace('_', '-')  # guid
        else:
            return cur

    # @profiler_decor
    def value_by_address(self, address):
        # path = '3-4-5'
        cur = self.object_as_list
        for i in address.split('-'):
            cur = cur[int(i)]

        return self.original_value(cur)

    # @profiler_decor
    def serialize(self, outfilename=''):
        """
        Превращает файл обычной формы в XML
        """
        if outfilename == '':
            outfilename = self.filename + '.xml'  # по умолчанию будем писать тут же рядом

        xml_root = ET.Element("root")  # рутовый элемент
        self.list_to_elementtree(self.object_as_list, xml_root, 1)

        if settings['try_givenames']:
            try:
                self.givenames(xml_root, self.ones_type)  # подпишем полученные теги
            except:
                print('Не удалось раздать имена для объекта: ' + self.ones_type)
        else:
            self.givenames(xml_root, self.ones_type)  # подпишем полученные теги


        if settings['use_lxml']:
            message = ET.tostring(xml_root, encoding='utf-8', pretty_print=True)  # lxml
        else:
            indent(xml_root)  # для cElementTree
            message = ET.tostring(xml_root, "utf-8")  # cElementTree - кажется, кодировку указывать незачем

        open(outfilename, 'wb').write(message)

    # @profiler_decor
    def list_to_elementtree(self, elements, xmlelement, level=0):
        """
        Собирает XML из массива. Все элементы имеют имя 'elem' и порядковый номер 'order'
        """
        i = -1

        for element in elements:
            i += 1
            linexml = ET.SubElement(xmlelement, "elem")
            linexml.set('order', str(i))  # добавляет порядковый номер элемента в атрибуты

            if type(element) is list:
                self.list_to_elementtree(element, linexml, level + 1)
            else:
                linexml.text = str(self.original_value(element))

    # @profiler_decor
    def filetolist(self):
        """
        Преобразует текст обычной формы в массив массивов массивов (вроде дерева)
        TODO стоит преобразовать так:
        1) замены текста
        2) eval
        3) обратные замены текста (сейчас лежит в другом месте)
        """

        # region RexExpFunctions
        def textrepl(match):
            """
            Вспомогательная функция
            Заменяет тексты в кавычках на "text0".."text123", а исходные значения складывает в словарь replaces
            Потом восстанавливает обратно в момент создания xml
            """
            replacenumberastext = '"text' + str(self.replaces.replacenumber) + '"'
            self.replaces.textreplaces[replacenumberastext] = match.group()
            self.replaces.replacenumber += 1
            return replacenumberastext

        def base64repl(match):
            """
            Вспомогательная функция
            Заменяет base64 на "base64_0".."base64_123", а исходные значения складывает в словарь base64_replaces
            Потом восстанавливает обратно в момент создания xml
            """
            replacenumberastext = '"base64_' + str(
                self.replaces.replacenumber) + '"'  # пользуемся одним и тем же replacenumber, но в данном случае не критично
            self.replaces.base64replaces[replacenumberastext] = match.group()
            self.replaces.replacenumber += 1
            return replacenumberastext

        guidrepl = lambda match: '"' + match.group().replace('-', '_') + '"'

        # endregion

        with open(self.filename, 'r', encoding='utf-8') as file:
            text = file.read()[1:]  # .encode('utf-8').decode('utf-8') # Первые 3 байта приходятся на BOM, они не нужны.

        text_start = text  # бэкап для отладки

        # текст между 2 группами нечетного числа кавычек закинем в словарь
        # pattern = re.compile(r'(?<!["])(")("")*?(?!["]).*?[^"](")("")*?(?!["])',flags=re.DOTALL)
        pattern = re.compile(
            r'(?<!["])'  # Перед фрагментом должен стоять любой символ, кроме кавычки. Этот символ не включается во фрагмент
            r'(")("")*?'  # дальше идет нечетное число кавычек
            r'(?!["])'  # которое зананчивается любым символом кроме кавычки
            r'.*?'  # затем - любое число любых символов(включая 0), ленивая квантификация (все равно не запомню и полезу на вики)
            r'[^"]'  # что угодно, кроме кавычки, 1 штука
            r'(")("")*?'  # снова нечетное число кавычек
            r'(?!["])'  # и затем - любой символ кроме кавычки. Этот символ не включается во фрагмент.
            , flags=re.DOTALL)
        text = pattern.sub(textrepl, text)

        # преобразуем гуиды к строкам, чтобы их можно было закинуть в массив
        # функция замены простая, а потому будет лямбдой
        pattern = re.compile(r'(\w{8}-\w{4}-\w{4}-\w{4}-\w{12})')
        text = pattern.sub(guidrepl, text)

        # теперь надо позаботиться о base64
        pattern = re.compile(r'\{#base64:'  # начало {#base64:
                             r'.{1,}?'  # любое количество других символов
                             r'\}',  # и закончится на }
                             flags=re.DOTALL)
        text = pattern.sub(base64repl, text)  # преобразуем гуиды к строкам, чтобы их можно было закинуть в массив

        # Далее 2 временных патча некоторых особенностей в формах.
        # Обратное преобразование невозможно, пока не придумаю, что делать с этими костылями.
        # Порядок их выполнения важен

        binaryrepl = lambda match: '"' + match.group() + '"'

        # 1) В обычных формах встречается такое: 31.00000000000002 или 1.6e2
        # тоже обернем в кавычки
        # pattern = re.compile(r'\d+\.\d+')
        pattern = re.compile(r'\d+'  # одна или несколько цифр
                             r'\.'  # точка
                             r'(\d|a|b|c|d|e|f)+')  # один или несколько символов: 0..9 или a..f (т.е. hex)
        text = pattern.sub(binaryrepl, text)

        # 2) в управляемых формах появились такие конструкции: 00010101000000. Т.е. нули-единицы, не текст. Просто обернем их в кавычки
        pattern = re.compile(r'(?<![.])'  # начинается НЕ с точки
                             r'\d{14}')  # и содержит росно 14 цифр. Кажется, встречались не только 0-1
        text = pattern.sub(binaryrepl, text)

        text = text\
            .replace('}', ']')\
            .replace('{', '[')  # теперь текст можно преобразовать так, чтобы Питон увидел в нем массив массивов массивов
        return eval(text)  # и получим наконец этот массив.

    def ClearTagName(self, name_of_tag):
        # уберем из описания текущего имени служебные поля
        return name_of_tag.replace('#', '').replace('*', '')
        # return lambda x: name_of_tag.replace('#', '').replace('*', '')

    def SetElementNameFromType(self, element, current_type, is_counter=False):

        if is_counter:
            element.set('counter', 'True')

        if current_type is None:
            return
        else:
            if current_type.onec_type != '':
                element.set('type', current_type.onec_type)
            if current_type.onec_name != '':
                element.set('name', current_type.onec_name)

        # for key,value in current_type._asdict().items():
        #     if key is not None and key!='':
        #         element.set(key, value)  # поименовали текущий тег

        # добавим чертов хак, который надо бы вынести куда-нибудь в будущем
        if current_type.onec_name == "ID_Типа_Элемента_Управления":
            dict_elem_types = get_dict_of_form_elements()
            type_name = dict_elem_types.get(element.text,'Неизвестный элемент управления')
            element.set('type_of_element', type_name)

    def Arrange(self):
        """
        Производит упорядочение содержимого для VCS, дабы не засорять коммиты мусорными диффами
        """
        if self.ones_type == 'Форма':
            self.object_as_list[1][10] = 123  # скинем счетчик сохранений
            # для файла versions будет свой алгоритм
            # и не совсем понятно, как поступать с модулем управляемой формы
        elif self.ones_type == 'versions':
            # в общих чертах так:
            # первые 2 элемента оставим как есть
            # среди остальных все четные скинем на пустой гуид, а все нечетные отсортируем по возрастанию
            pass

    # @profiler_decor
    def givenames(self, elem, onectype_name):
        """
        раздает имена по настройкам из ones_classes.py
        """

        if onectype_name == '':
            return None

        __counter__ = 0  # порядковый номер элемента, который мы собираемся обходить
        onectype = self.onec_types_ext[onectype_name]

        for current_type in onectype:

            if current_type is None:
                __counter__ += 1
                continue

            current = getxmlbyindexes(elem, [__counter__, ])  # может, проще по индексу обратиться? elem[counter]
            self.SetElementNameFromType(current, current_type) # поименовали текущий тег

            if current_type.is_array:  # это массив однотипных элементов, начинающийся со счетчика.
                self.SetElementNameFromType(current, current_type, True)
                __counter__ += 1  # здесь порылся дьявол

                for i in range(int(current.text)):
                    # здесь копипаста кода, увы, пока оставлю
                    current = getxmlbyindexes(elem, [__counter__, ])
                    # может, проще по индексу обратиться? elem[counter]
                    self.SetElementNameFromType(current, current_type)
                    if current_type.onec_type!='':
                        self.givenames(current, current_type.onec_type)
                        __counter__ += 1
                # дальше обязательно будет 0 или несколько однотипных элементов.
                # причем они могут быть как единичными, так и сложными
                # надо обработать их внутри данного цикла

            elif current_type.onec_type!='':  # это вложенный элемент, внутри него тоже можно раздавать имена
                self.givenames(current, current_type.onec_type)
                __counter__ += 1

            else:
                __counter__ += 1 # нам надо просто выдать имя текущему тегу, а мы его уже в начале выдали


def preparetypes():
    """
    Готовит расшифровку внутренней структуры форм 1С
    """

    global onectypes
    if onectypes is None:
        onectypes = get_ones_types()  # вынесено в соседний модуль
    return onectypes


class EpfParser(object):
    filename = None
    filename_short = None
    unpacked_dir = None
    source_dir = None
    curdir = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def __init__(self, filename=''):
        self.filename = filename
        self.filename_short = os.path.basename(self.filename)[:-4]
        self.curdir = os.path.dirname(self.filename)
        self.unpacked_dir = os.path.join(self.curdir, self.filename_short + '.und')  # сюда распакуем v8reader'ом
        self.source_dir = os.path.join(self.curdir, 'src', self.filename_short)  # а сюда переложим красивые файлы

    # @profiler_decor
    def prepare_dirs_for_unpack(self):
        """Чистит предыдущую раскладку и заново создает каталоги для исходников, если надо"""
        if not os.path.exists(os.path.join(self.curdir, 'src')):
            os.mkdir(os.path.join(self.curdir, 'src'))  # создать общую папку src, если ее нет

        if os.path.exists(self.unpacked_dir):
            shutil.rmtree(self.unpacked_dir)  # почистим предыдущую раскладку

        if os.path.exists(self.source_dir):
            shutil.rmtree(self.source_dir)  # почистим предыдущую раскладку

        os.mkdir(self.source_dir)  # и создадим структуру каталогов
        for i in SubFolders:
            os.mkdir(os.path.join(self.source_dir, i.value))

    # @profiler_decor
    def process_epf(self):
        """
        раскладывает отдельно взятый файл epf на исходники
        """
        self.prepare_dirs_for_unpack()  # подготовим каталоги

        command_text = '"UnpackV8.exe" -parse "%s" "%s"' % (self.filename, self.unpacked_dir)
        exec_and_wait(command_text)  # распакуем файл

        # модуль объекта
        for fn in glob.glob(self.unpacked_dir + '/*/text'):
            # предполагаем, что для  epf он только один
            new_file_name = os.path.join(self.source_dir, 'МодульОбъекта.1s')
            os.rename(fn, new_file_name)
            split_module_text(new_file_name)  # раскидаем текст модуля на отдельные файлы

        # этот файл всегда есть в epf, он короткий, задает только идентификатор текущего объекта.
        # Все кишки лежат в файле с именем, равным этому идентификатору
        with ones_object(os.path.join(self.unpacked_dir, 'root')) as rootfile_array:
            descriptionsfilename = rootfile_array.object_as_list[1].replace('_', '-')
            # print('descriptions are here: ' + descriptionsfilename)

        # Этот файл содержит список форм, реквизитов, табличных частей и т.д.
        # Найдем описания форм и переберем их циклом
        with ones_object(os.path.join(self.unpacked_dir, descriptionsfilename), '_root_second') as second_root_file:
            second_root_file.serialize()  # распарсим данный файл по описанию _root_second
            # формы лежат в 3-1-5, в количестве 3-1-5-1, начиная с 3-1-5-2

            forms = []  # подготовим массивы под обычные и управляемые формы
            for form_id in second_root_file.value_by_address('3-1-5')[2:]:

                formfilename = os.path.join(self.unpacked_dir, form_id.replace('_', '-'))
                with ones_object(formfilename) as short_form_desc:
                    # short_form_desc.serialize(formfilename+'.xml')
                    # Признак "управляемая - обычная" находится по адресу 1-1-1-3
                    # pass
                    form_name = short_form_desc.value_by_address(
                        '1-1-1-1-2')  # восстанавливать замены непосредственно внутри объекта, после получения массива

                # а дальше будет formfilename+'.0' - папка, если обычная форма, и файл, если управляемая.
                if os.path.isdir(formfilename + '.0'):
                    _fn, _type = os.path.join(formfilename + '.0', 'form'), 'Форма'
                else:
                    _fn, _type = formfilename + '.0', 'УправляемаяФорма'

                forms.append([_fn, _type, self.source_dir, form_name.replace('"', '')])

            # теперь каждую форму из полученного списка преобразуем в xml
            if settings['multiprocessing']:
                # """Многопоточный вариант"""
                from multiprocessing import cpu_count
                # создадим столько воркеров, сколько ядер у нашего процессора
                with Pool(cpu_count()) as p:
                    p.starmap(parse_and_move_single_file, forms)
            else:
                """Вариант в один поток, для отладки, 10 форм"""
                for form in forms:
                    # parse_and_move_single_file(form)
                    if form[1] == 'УправляемаяФорма' or True:
                        parse_and_move_single_file(form[0], form[1], form[2], form[3])

            # обработка макетов
            for maket_id in second_root_file.value_by_address('3-1-4')[2:]:
                # макеты лежат по адресу 3-1-4, начиная с элемента 2
                fn = os.path.join(self.unpacked_dir, maket_id.replace('_', '-'))
                with ones_object(fn) as maket_id_obj:
                    # print('maket ' + maket_id)
                    sinonym = maket_id_obj.value_by_address('1-2-2')
                    new_file_name = os.path.join(self.source_dir, SubFolders.binary.value, sinonym.replace('"', ''))
                    os.rename(fn + '.0', new_file_name)

                    # TODO сделать одну общую процедуру по обработке элемента:
                    # неважно, макет, обычная/управляемая форма и т.д.

        # Теперь переберем остальные файлы здесь же
        parse_and_move_single_file(os.path.join(self.unpacked_dir, 'root'), '')
        parse_and_move_single_file(os.path.join(self.unpacked_dir, 'version'), '')  # здесь лежит описание - 8.1 или 8.2
        parse_and_move_single_file(os.path.join(self.unpacked_dir, 'versions'),
                                   '')  # здесь еще надо будет строки отсортировать

        # все, что осталось внутри, просто переместим в папку "Прочее"
        for fn in glob.glob(os.path.join(self.unpacked_dir, '*')):
            new_file_name = os.path.join(self.source_dir, 'Прочее', os.path.basename(fn))
            os.rename(fn, new_file_name)

        os.rmdir(
            self.unpacked_dir)  # и удалим папку с распаковкой, т.к. она в этот момент должна быть полностью разобрана

        after_parse_custom_actions_uf(
            self.source_dir)  # какие-то еще действия, не относящиеся напрямую к логике разбора


# @profiler_decor
def parse_and_move_single_file(filename='', ones_type='', dest='', object_name=''):
    """преобразует файл в читаемый формат и выносит его в нужную папку в dest"""
    with ones_object(filename, ones_type) as obj:

        if ones_type in ['Форма', 'УправляемаяФорма']:
            dest = os.path.join(dest, SubFolders.forms.value)
            dest_filename = os.path.join(dest, object_name, 'form')
            # Создадим каталог под них
            if not os.path.exists(os.path.join(dest, object_name)):
                os.mkdir(
                    os.path.join(dest, object_name))  # создадим каталог под данную форму, если его вдруг нет
        else:
            dest = os.path.join(dest, SubFolders.other.value)  # по умолчанию
            dest_filename = ''


        obj.Arrange()  # упорядочим внутреннее представление для VCS

        if obj.ones_type == 'Форма':

            name_of_module_file = os.path.join(os.path.dirname(filename), 'module')
            new_module_file = os.path.join(dest, object_name, 'module.1s')

            os.rename(name_of_module_file, new_module_file)
            split_module_text(new_module_file)

            os.remove(filename)  # удаляем старый файл формы
            obj.serialize(dest_filename)  # вместо него пишем новый, распарсенный

        elif obj.ones_type == 'УправляемаяФорма':

            text_of_module = obj.value_by_address('2')
            obj.object_as_list[2] = '#extracted#'
            text_of_module = text_of_module[1:-1].replace('""',
                                                          '"')
            # двойные кавычки заменим на одинарные. Открывающую и закрывающую кавычку выкинем.

            name_of_module_file = os.path.join(dest, object_name, 'module.1s')
            open(name_of_module_file, 'w', encoding='utf-8').write(text_of_module)
            split_module_text(name_of_module_file)

            os.remove(filename)  # удаляем старый файл формы
            obj.serialize(dest_filename)  # вместо него пишем новый, распарсенный


def after_parse_custom_actions(source_dir):
    """после полной раскладки epf на исходники сделаем что-нибудь еще"""
    suffixes = ['_epf', '_xsd', '_cf']
    for fileName in glob.glob(os.path.join(source_dir, SubFolders.binary.value, '*')):
        for suffix in suffixes:
            if fileName.endswith(suffix):
                end = suffix[1:]
                name = fileName[:-(len(suffix))]  # отрежем окончание
                new_file_name = name + '.' + end

                try:
                    extract_base64(fileName, new_file_name)
                    os.remove(fileName)  # а исходный удалить
                    if (end == 'epf') and settings['extract_included_epf']:
                        EpfParser(new_file_name).process_epf()
                except:
                    print('не разобрались с ' + fileName)


def after_parse_custom_actions_uf(source_dir):
    """после полной раскладки epf на исходники сделаем что-нибудь еще"""
    for fileName in glob.glob(os.path.join(source_dir, SubFolders.binary.value, '*')):

        if os.path.basename(fileName).startswith('Модуль_'):
            new_file_name = fileName + '.epf'

            try:
                extract_base64(fileName, new_file_name)
                os.remove(fileName)  # а исходный удалить
                if settings['extract_included_epf']:
                    EpfParser(new_file_name).process_epf()
            except:
                print('не разобрались с ' + fileName)

# @profiler_decor
def split_module_text(filename):
    if settings['split_module_text']:
        extract_one(filename)

#@profile
def main(l_args):
    preparetypes()  # подготовим описание форм в 1С

    if l_args.action == 'decompile':

        files = []  # массив файлов для парсинга
        search_path = l_args.source  # будем парсить все в данном каталоге
        if search_path == '':
            search_path = os.getcwd()  # но если его не указали, то в текущем

        if not os.path.exists(search_path):
            print('Ошибка: В параметре "source" указан несуществующий путь: ' + search_path)
            return 1

        elif os.path.isdir(search_path):
            if l_args.type == 'epf':
                files = glob.glob(os.path.join(search_path, '*.epf'))
            elif l_args.type == 'object':
                files = glob.glob(os.path.join(search_path, '*'))

            # пройдемся по списку полученных файлов и вычеркнем из них директории

            for fn in files:
                if os.path.isdir(fn) or fn.endswith('.xml'):  # костылек
                    files.remove(fn)  # в 1С такие трюки опасны. Не знаю, как здесь, при случае надо проверить.

        elif os.path.isfile(search_path):
            if l_args.type == 'epf' and l_args.source.lower().endswith('.epf'):  # будем парсить отдельно взятый epf
                if l_args.type == 'epf' and l_args.source.lower().endswith('.epf'):  # будем парсить отдельно взятый epf
                    files.append(l_args.source)
                elif l_args.type == 'object':  # это уже не epf, а отдельный объект 1С
                    files.append(l_args.source)
                else:
                    print('Ошибка: В параметре "source" указан неподходящий файл')
                    return 1

        object_type = '' if l_args.objecttype is None else l_args.objecttype
        # определились со списком файлов для парсинга, приступим к нему
        for fn in files:
            print('parse: ' + os.path.basename(fn)[:-4])
            if l_args.type == 'epf':
                EpfParser(fn).process_epf()
            elif l_args.type == 'object':
                object_ = ones_object(fn, object_type)
                if object_type == 'Форма':
                    object_.object_as_list[1][10] = 123  # еще раз скинем счетчик сохранений
                object_.serialize(fn + '.xml')

    else:
        print('что делать?')


def extract_base64(filename, newfilename):
    """Извлекает base64 значение из распакованного файла с макетом fileName
    и записывает извлеченный бинарник в new_file_name"""
    import base64
    with ones_object(filename) as decompiled:
        _str = decompiled.value_by_address('1').replace('\n', '').replace('\r', '')
        len_of_beginning = len(r'{#base64:')
        len_of_end = len(r'}')
        binary_value = base64.b64decode(_str[len_of_beginning:-len_of_end], validate=True)
        open(newfilename, 'wb').write(binary_value)


def debug():
    # filename = 'C:\\Users\\volodkindv\\Documents\\SVN 1C\\onecDecoder\\test.und\\da7349ba-2d62-46a6-b53f-f0eca2fc8427.0'

    # EpfParser(fn).process_epf()
    # parse_and_move_single_file(filename, 'Форма')
    pass


"""Что хочется:
1) При запуске без параметров - рекурсивно декомпилируется все вокруг (epf)
2) Есть возможность декомпилировать отдельно взятый файл epf
3) Есть возможность указать, надо ли декомпилировать вложенные макеты
    (и как их определять? в другом скрипте? в файле настроек?
4) Возможность декомпилировать отдельный файл из уже разобранного EPF - файл формы, файл root и т.д."""


def get_args():
    parser = argparse.ArgumentParser(description='Распаковка внешних обработок 1C8')
    parser.add_argument('--action', action='store', default='decompile',
                        help='Действие. "decompile" разберет все файлы epf, находящиеся в текущей папке, на исходники')
    parser.add_argument('--source', action='store', default='',
                        help='Каталог / файл для разбора')
    parser.add_argument('--type', action='store', default='epf',
                        help='Тип разбираемого файла. Доступные значения: epf, object')
    parser.add_argument('--objecttype', action='store', default='',
                        help='Тип объекта в разбираемом файле.')

    # "вложенный парсер" можно задавать так: https://habrahabr.ru/post/144416/
    # пока не стоит заморачиваться.
    return parser.parse_args()


if __name__ == "__main__":
    args = get_args()

    # print('source: ' + args.source)
    # print('type: ' + args.type)
    # print('objecttype: ' + args.objecttype)

    # l_args.source = '.\\test_form'
    # l_args.type = 'object'
    # l_args.objecttype = 'Форма'

    result = main(args)
    # result = debug()

    # Profiler.print_results(profiler_results)  # покажем замеры скорости
    sys.exit(result)



# @functools.lru_cache(maxsize=128, typed=False) - аналог "повторного использования" в 1С
# collections.OrderedDict - упорядоченный Словарь. Может подойти для классов - аналогов классов 1С