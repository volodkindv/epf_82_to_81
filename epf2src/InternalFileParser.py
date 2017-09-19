import re, time, sys, glob
from enum import Enum

settings = \
    {
        'multiprocessing': False  # выполнять разбивку в несколько процессов
        , 'use_lxml': False  # lxml - адски быстрая работа с xml.
        , 'try_givenames': False  # если функция givenames падает - продолжить выполнение
    }

# для работы с XML есть 2 библиотеки:
if settings['use_lxml']:
    from lxml import etree as ET  # работает гораздо быстрее, но требует установки через pip
else:
    import xml.etree.cElementTree as ET  # штатная

from .ones_classes import get_ones_types, get_onec_types_ext  # сюда буду выносить описание типов в 1С
from .ones_classes import get_dict_of_form_elements  # гуиды типов элементов управления на формах


onectypes = {}  # словарь словарей. На первом уровне - типы элементов (главное окно, кнопка, ...) На втором - порядковые номера элементов и их имена
profiler_results = {}


class ReplacesForForms(object):
    """перечень замен, произведенных над исходным текстом формы
    Пожалуй, стоит перевести на структуру, или вообще встроить в родительский класс"""
    def __init__(self):
        self.replacenumber = 0
        self.textreplaces = {}
        self.base64replaces = {}


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
        root = root.getchildren()[i]  # TODO попробовать заменить на iter
    return root

def get_parents_map(tree):
    parent_map = {child: parent for parent in tree.iter() for child in parent}
    return parent_map

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
        self.ReplacesForForms = None

    def __init__(self, filename='', ones_type=''):
        self.ones_type = ones_type
        self.filename = filename
        self.replaces = ReplacesForForms()
        # и сразу прочитаем
        self.object_as_list = self.filetolist()
        self.onec_types_ext = get_onec_types_ext()


    def original_value(self, cur):
        # вернет исходное значение из словаря замен

        if type(cur) == str:
            if cur.startswith('text'):
                return self.replaces.textreplaces['"' + cur + '"']
            elif cur.startswith('base64'):
                return self.replaces.base64replaces['{"' + cur + '"}']
            elif cur == '':
                return '""'  # Питон при парсинге проглатывает двойные кавычки
            else:
                return cur
                # return cur.replace('_', '-')  # guid
                # это надо бы вынести куда-то в другое место
        else:
            return cur


    def value_by_address(self, address):
        # path = '3-4-5'
        cur = self.object_as_list
        for i in address.split('-'):
            cur = cur[int(i)]

        return self.original_value(cur)


    def serialize(self, outfilename=''):

        # return  #пока не нужно
        """
        Превращает файл обычной формы в XML
        """
        if outfilename == '':
            outfilename = self.filename + '.xml'  # по умолчанию будем писать тут же рядом

        self.xml_root = ET.Element("root")  # рутовый элемент
        self.list_to_elementtree(self.object_as_list, self.xml_root, 1)

        if settings['try_givenames']:
            try:
                self.givenames(self.xml_root, self.ones_type)  # подпишем полученные теги
            except:
                print('Не удалось раздать имена для объекта: ' + self.ones_type)
        else:
            self.givenames(self.xml_root, self.ones_type)  # подпишем полученные теги


        if settings['use_lxml']:
            message = ET.tostring(self.xml_root, encoding='utf-8', pretty_print=True)  # lxml
        else:
            indent(self.xml_root)  # для cElementTree
            message = ET.tostring(self.xml_root, "utf-8")  # cElementTree - кажется, кодировку указывать незачем

        open(outfilename, 'wb').write(message)


    def list_to_elementtree(self, elements, xmlelement, level=0, _path = None):
        """
        Собирает XML из массива. Все элементы имеют имя 'elem' и порядковый номер 'order'
        """
        i = -1

        _inner_path = _path
        if _inner_path is None:
            _inner_path = ''

        for element in elements:
            i += 1
            linexml = ET.SubElement(xmlelement, "elem")
            linexml.set('order', str(i))  # добавляет порядковый номер элемента в атрибуты
            linexml.set('path', _inner_path + '-' + str(i))  # добавляет порядковый номер элемента в атрибуты
            # сюда бы сразу и путь вытащить

            if type(element) is list:
                self.list_to_elementtree(element, linexml, level + 1, _inner_path + '-' + str(i))
            else:
                linexml.text = str(self.original_value(element))


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
            replacenumberastext = '{"base64_' + str(
                self.replaces.replacenumber) + '"}'  # пользуемся одним и тем же replacenumber, но в данном случае не критично
            self.replaces.base64replaces[replacenumberastext] = match.group()[1:-1]
            # откинем открывающую и закрывающую скобки. Это можно сделать на уровне регэкспа, но некогда разбираться.
            self.replaces.replacenumber += 1
            return replacenumberastext

        def guidrepl(match):
            # гуиды будем менять так же, как текст. Только без учета кавычек вокруг, видимо.
            replacenumberastext = '"text' + str(self.replaces.replacenumber) + '"'
            self.replaces.textreplaces[replacenumberastext] = match.group()
            self.replaces.replacenumber += 1
            return replacenumberastext

            # return '"' + match.group().replace('-', '_') + '"'

        def binaryrepl(match):
            return '"' + match.group() + '"'

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

        # 1) В обычных формах встречается такое: 31.00000000000002 или 1.6e2
        # тоже обернем в кавычки
        # pattern = re.compile(r'\d+\.\d+')
        pattern = re.compile(r'\d+'  # одна или несколько цифр
                             r'\.'  # точка
                             r'[\d|a|b|c|d|e|f]+')  # один или несколько символов: 0..9 или a..f (т.е. hex)
        text = pattern.sub(guidrepl, text)

        # 2) в управляемых формах появились такие конструкции: 00010101000000. Т.е. нули-единицы, не текст. Просто обернем их в кавычки
        pattern = re.compile(r'(?<![.])'  # начинается НЕ с точки
                             r'\d{14}')  # и содержит ровно 14 цифр. Кажется, встречались не только 0-1
        text = pattern.sub(guidrepl, text)

        # 3) в обычных формах - нечто похожее на числа с плавающей запятой. 1e2. Возможно, это частный случай от 1)
        pattern = re.compile(r'\d+'  # несколько чисел
                             r'e'  # символ "e"
                             r'\d+')  # несколько чисел
        text = pattern.sub(guidrepl, text)

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

            if dict_elem_types.get(element.text) is not None\
                    and self.onec_types_ext.get(type_name) is not None:
                # для раздачи имен надо как-то подняться на уровень выше
                parent = get_parents_map(self.xml_root)[element]
                self.givenames(getxmlbyindexes(parent, [2,]), type_name)

    def set_original_text_value(self, replacetext, newvalue):
        self.replaces.textreplaces['"' + replacetext + '"'] = newvalue

    def Arrange(self):
        """
        Производит упорядочение содержимого для VCS, дабы не засорять коммиты мусорными диффами
        """
        return  # не задействуем пока

        def arrange_command_panel(root):

            self.set_original_text_value(root[2][1][10], '00000000-0000-0000-0000-000000000000')  # скинем гуид, который хз зачем нужен
            buttons_count = root[2][1][7][4]

            buttons_order = root[2][1][7] [5 + buttons_count + 1] [ 5: 5 + buttons_count*2 : 2]  # каждый второй
            # buttons_order_original = [self.original_value(current) for current in buttons_order]
            # print(buttons_order_original)

            new_order = []
            i = 0
            for el in buttons_order:
                for button in root[2][1][7][5: 5 + buttons_count]:
                    if self.original_value(button[1]) == self.original_value(el):
                        new_order.append(button)
                        new_guid = '00000000-0000-0000-0000-000000000000'[:-5] + '%05d' % (i)
                        self.set_original_text_value(el, new_guid)
                        self.set_original_text_value(button[1], new_guid)
                        break
                i += 1

            i = 0
            for button in new_order:
                root[2][1][7][5+i] = button
                i += 1

            # for button in root[2][1][7] [5: 5 + buttons_count]:
            #     print('guid кнопки:' + self.original_value(button[1]))

            # итак, у нас есть необходимый порядок кнопок, и есть сами кнопки объектами.
            # осталось отсортировать

        def arrange_list_of_elements(root):

            for elem in root[1:]:  # первые 3 элемента - адрес, потом - срез 9первый элемент не нужен0
                if self.original_value(elem[0]) == 'e69bf21d-97b2-4f37-86db-675aea9ec2cb': # это гуид командной панели
                    arrange_command_panel(elem)
                elif self.original_value(elem[0]) == '09ccdc77-ea1a-4a6d-ab1c-3435eada2433': # это гуид панели, на которой тоже могут быть свои ЭУ
                    # arrange_command_panel(elem)
                    arrange_list_of_elements(elem[5])


        if self.ones_type == 'Форма':
            self.object_as_list[1][10] = 123  # скинем счетчик сохранений
            arrange_list_of_elements(self.object_as_list[1][2][2])


            # для файла versions будет свой алгоритм
            # и не совсем понятно, как поступать с модулем управляемой формы
        elif self.ones_type == 'versions':
            # в общих чертах так:
            # первые 2 элемента оставим как есть
            # среди остальных все четные скинем на пустой гуид, а все нечетные отсортируем по возрастанию
            pass


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


    def serialize_back(self, new_filename = None):
        """записывает файл обратно в формат со скобками"""

        if new_filename == None:
            # по умолчанию в этот же файл
            new_filename = self.filename

        def add_current_row_to_line(row, strings):

            if len(strings) == 0:
                strings.append('{')
            else:
                strings.append('\r\n{')

            for el in row:
                if type(el) is list:
                    add_current_row_to_line(el, strings)
                    strings.append(',')
                else:
                    strings.append(str(self.original_value(el)) + ',')

            last_string_index = len(strings)-1
            if last_string_index > 0 and strings[last_string_index] == ',' and strings[last_string_index-1].endswith('}'):
                # strings.pop() # эта запятая не нужна
                strings[last_string_index] = '\r\n}'  # повторы закрывающих скобок не встречаются. Странное эстетство.
            elif strings[last_string_index].endswith('{'):
                strings[last_string_index] = strings[last_string_index] + '}'
            else:
                strings[last_string_index] = strings[last_string_index][:-1]+'}'
                # сотрем последнюю запятую, добавим закрывающую скобку
            # strings.append('}')

        with open(new_filename, 'wb') as file:
            # BOM
            strings=[]
            add_current_row_to_line(self.object_as_list, strings)
            total = ''.join(strings)
            from codecs import BOM_UTF8
            file.write(BOM_UTF8)
            file.write(total.encode('utf-8'))


def preparetypes():
    """
    Готовит расшифровку внутренней структуры форм 1С
    """

    global onectypes
    if onectypes is None:
        onectypes = get_ones_types()  # вынесено в соседний модуль
    return onectypes


def main(l_args):
    pass
    # preparetypes()  # подготовим описание форм в 1С


if __name__ == "__main__":

    result = main()
    sys.exit(result)
