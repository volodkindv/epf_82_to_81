"""Определение классов объектов, используемых в 1С."""
import json, collections

def get_ones_types():

    """
    Готовит расшифровку внутренней структуры форм 1С
    """

    onectypes = dict()

    onectypes['Форма'] = \
        [
            None  #0
             , '#ГлавноеОкно' # 1
             , '#РеквизитыФормы'  # 2
             , '#_СохранениеЗначений'  # 3
             ,  None  # 4
             , 'АвтоЗаголовок'  # 5
             , 'СостояниеОкна'  # 6
             , 'ПоложениеПрикрепленногоОкна'  # 7
             , 'ТолькоПросмотр'  # 8 'СоединяемоеОкно' ? WTF???
             , 'ПоложениеОкна'  # 9
             , 'ИзменениеРазмера'  # 10
             , '#_НастройкиКонтекстногоМеню'  # 11
             ,  None  # 12
             , '_где_то_здесь_КартинкаЗаголовка'  # 13
             , 'СпособОтображенияОкна'  # 14
             , 'ИзменятьСпособОтображенияОкна'  # 15
             ,  None  # 16
             , 'РежимРабочегоСтола'  # 17
             , 'РазрешитьЗакрытие'  # 18
             , 'ПроверятьЗаполнениеАвтоматически'  # 19 # кажется, это как раз из новых платформ
         ]

    onectypes['_НастройкиКонтекстногоМеню'] = \
        [
            'АвтоКонтекстноеМеню'  # 0    # 1 и далее появятся только в том случае, если этот элемент равен 1
        ]

    onectypes['ГлавноеОкно'] = \
        [
            None  #0
            , '_Заголовок_Внутри'  # 1  # это похоже на отдельный класс - Заголовок, я его уже где-то упоминал
            , '#_ЭлементыФормы_вспом_1'  # 2
            , 'Ширина'  # 3
            , 'Высота'  # 4
            ,  None  # 5
            , 'ИспользоватьСетку'  # 6
            , 'ИспользоватьВыравнивающиеЛинии'  # 7
            , 'ГоризонтальныйШагСетки'  # 8
            , 'ВертикальныйШагСетки'  # 9
            , 'СчетчикСохранений'  # 10
        ]


    onectypes['РеквизитыФормы'] = \
        []  # здесь, кажется, будет самое интересное

    onectypes['_ЭлементыФормы_вспом_1'] = \
        [
            None  # 0
            , '#_ЭлементыФормы_вспом_2'  # 1  Может, это и есть ПанельФормы?
            , '#_ЭлементыФормы_Настоящие_ПрямоСписок'  # 1  Может, это и есть ПанельФормы?
        ]

    onectypes['_ЭлементыФормы_Настоящие_ПрямоСписок'] = \
        [
            '#ЭлементУправления*'  # 0 - количество, 1 и далее - сами элементы
        ]

    onectypes['_ЭлементыФормы_вспом_2'] = \
        [
            None  # 0
            , '#_ЭлементыФормы_вспом_3'  # 1
        ]

    onectypes['_НеизвестныйОбъект'] = \
        [ # сюда будут ссылаться массивы из непонятных объектов
        ]

    onectypes['_ЭлементыФормы_вспом_3'] = \
        [
            '#Оформление1'  # 0
            , None  # число, 21
            , '#_НеизвестныйОбъект*'
            , '#_НеизвестныйОбъект*'
            , '#_НеизвестныйОбъект*'
            , '#_НеизвестныйОбъект*'
            , None, None  # 6-7. И здесь, возможно, ошибка: какие-то из этих элементов - счетчики
            , '#_Картинки'  # 8
            , 'ОтображениеЗакладок'  # 9
            , 'РаспределятьПоСтраницам'  # 10
            , '#_СтраницыФормы'  # 11
            , 'АвтоПравила'  # 12
            , 'АвтоПорядокОбхода'  # 13
            , 'РежимПрокручиваемыхСтраниц'  # 14
            , '#Привязка*'  # 14 - количество привязок, 15 и далее - сами привязки
            # после привязок идут еще 6 элементов в 8.2.19. А в 8.2.9 - 5 элементов! И читается нормально.
        ]

    onectypes['Привязка'] = \
        []

    onectypes['_СтраницыФормы'] = \
        [
            None  # 0
            , '#Страница*'  # 1 - количество, 2 и далее - сами страницы
        ]

    onectypes['Страница'] = \
        [
            None  # 0
            , 'Заголовок'  #1  # Кажется, что для Заголовков и прочих подписей существует отдельный класс - с указанием языка
            , 'КартинкаЗаголовка'  # 2
            , None  # 3
            , 'Видимость'  #4
            , 'Доступность'  #5
            , 'Имя'  # 6
            , 'Раскрыта'  # 7
        ]
    # страница панели или формы? Или это одно и то же?

    onectypes['_СохранениеЗначений'] = \
        [
            # похоже, это скорее Данные (основной реквизит формы).
            None  # гуид, может быть нулями
            , '#_СохранениеЗначений1*'  # несколько таких объектов
        ]

    onectypes['Оформление1'] = \
        [
            None  # 0
            , 'Доступность'  # 1
            , 'ЦветФона #_Цвет'  # 2 уткнулся в то, что имя - отдельно, тип - отдельно. Это поле - цвет фона, например
            , 'ЦветТекста #_Цвет'  # 3 - пусть пока без вложенного объекта
            , 'Шрифт'  # 4
            , None  # 5
            , None  # 6
            , 'ЦветФонаПоля #_Цвет'  # 7
            , 'ЦветТекстаПоля #_Цвет'  # 8
            , 'ЦветФонаКнопки #_Цвет'  # 9
            , 'ЦветТекстаКнопки #_Цвет'  # 10
            , None  # 11
            , 'Подсказка'  # 12, очень похожа на Заголовок
        ]

    onectypes['_Цвет'] = \
        []

    onectypes['_Картинки'] = \
        [
            None  # 0
            , 'РазмерКартинки'  # 1 Кажется, здесь ошибка
            , '#Картинка'  # 2
        ]

    onectypes['Картинка'] = \
        []

    onectypes['_СохранениеЗначений1'] = \
        [
            None  # 0
            , 'СохранятьЗначения'  # 1
            , None, None  # 2-3
            , 'ВосстанавливатьЗначенияПриОткрытии'  # 4
        ]

    onectypes['_root_second'] = \
        [
            None, None, None  # 0-2
            , '#_root_second_2'  # 3  описание файла, на который ссылается root
        ]

    onectypes['_root_second_2'] = \
        [
            None  # 0
            , '#_root_second_3'  # 1
        ]

    onectypes['_root_second_3'] = \
        [
            None, None, None, None, None  # 0-4
            ,  '#_root_second_ФормыОбработки'  # 5
            ,  '#_root_second_РеквизитыОбработки'  # 6
        ]

    onectypes['_root_second_ФормыОбработки'] = \
        [
            '_UUID_метка_что_это_формы' # 0
            , '#ФормыОбработки*'  # 1 # А дальше идут гуиды самих форм. Вот отсюда мы можем уже обращаться к именам файлов.
    # И в этом файле не понять, какие из них обычные, а какие управляемые
        ]

    onectypes['ФормыОбработки'] = \
        []

    onectypes['_root_second_РеквизитыОбработки'] = \
        []

    onectypes['ЭлементУправления'] = \
        [
            'ID_Типа_Элемента_Управления'  # 0. Здесь можно обратиться к расшифровке гуидов из Ассемблы
            # можно прямо здесь зашить инструкцию: "ищи тип по гуиду"
            # проблема только в том, что тип назначается, кажется, уровнем выше
            , '_какой-то_порядок_(число)'  # 1. Единичный элемент, пока не интересен
            , None  # 2. Здесь и в 3 самое интересное
            , '#РазмещениеНаФорме'  # 3. Здесь и в 3 самое интересное
            , '#ВнутренниеПоляЭлементаУправления'  # 4. Здесь дублируется заголовок и еще что-то вложенное. Скорей всего, это имя для внутреннего пользования (из кода формы)
            , 'ВложенныеЭлементыУправления #_ЭлементыФормы_Настоящие_ПрямоСписок'  # 5. Коллекция ЭУ, вложенных в текущий
        ]

    onectypes['РазмещениеНаФорме'] = \
        [
            None
            , 'Лево'
            , 'Верх'
            , 'Право'
            , 'Низ'
            , None  # дальше где-то будут привязки
        ]

    onectypes['ВнутренниеПоляЭлементаУправления'] = \
        [
            None
            , 'ВнутреннееИмя'
            , None  #
        ]

    onectypes['Кнопка'] = \
        [
            # None, None, None, None, None  # 0-4
            # ,  '#_root_second_ФормыОбработки'  # 5
            # ,  '#_root_second_РеквизитыОбработки'  # 6
        ]

    onectypes['КоманднаяПанель_внутренности1'] = \
        [
            None, None, None, None, None, None, None
            , '#КоманднаяПанель_внутренности2'  # 7 - где-то внутри как раз будут кнопки
            , None, None
            , 'НепонятныйГуид'  # 10 - меняется от сохранения к сохранению, смысловая нагрузка неизвестна.
        ]

    onectypes['КоманднаяПанель'] = \
        [
            None
            , '#КоманднаяПанель_внутренности1'
        ]

    onectypes['КоманднаяПанель_внутренности2'] = \
        [
            None, None, None, None
            , '#_КнопкаКоманднойПанели*'
            , None
            , '#КоманднаяПанель_ПорядокКнопок'
        ]

    onectypes['_КнопкаКоманднойПанели'] = \
        [
            None
            , 'GUID'  # генерится рандомно при каждом сохранении
            # , '#КоманднаяПанель_внутренности1'
        ]

    onectypes['КоманднаяПанель_ПорядокКнопок'] = \
        [
            None, None, None, None, None
            # Начиная с 6-й идет порядок кнопок - но через одну!
            # , '#_КнопкаКоманднойПанели*'
            # , None
            # , '#ПорядокКнопок'
        ]

    onectypes['УправляемаяФорма'] = \
        []

    return onectypes


def get_dict_of_form_elements():
    """
    словарь гуидов элементов управления 1С
    расшифровка взята с assembla
    """
    type_dict = {
        "09ccdc77-ea1a-4a6d-ab1c-3435eada2433"  :  "_Панель"
        , "6ff79819-710e-4145-97cd-1618da79e3e2"  :  "_Кнопка"
        , "0fc7e20d-f241-460c-bdf4-5ad88e5474a5"  :  "_Надпись"
        , "381ed624-9217-4e63-85db-c4c3cb87daae"  :  "_ПолеВвода"
        , "ea83fe3a-ac3c-4cce-8045-3dddf35b28b1"  :  "_ТабличноеПоле"
        , "35af3d93-d7c7-4a2e-a8eb-bac87a1a3f26"  :  "_Флажок"
        # , "782e569a-79a7-4a4f-a936-b48d013936ec"  :  "Переключатель"  #  здесь ошибки: гуиды дублируются в следующих 4 строках
        # , "19f8b798-314e-4b4e-8121-905b2a7a03f5"  :  "Поле списка"
        # , "782e569a-79a7-4a4f-a936-b48d013936ec"  :  "Поле выбора"  # поэтому отключу все 4 до лучших времен
        # , "19f8b798-314e-4b4e-8121-905b2a7a03f5"  :  "Рамка группы"
        , "e69bf21d-97b2-4f37-86db-675aea9ec2cb"  :  "КоманднаяПанель"
        , "151ef23e-6bb2-4681-83d0-35bc2217230c"  :  "_ПолеКартинки"
        , "36e52348-5d60-4770-8e89-a16ed50a2006"  :  "_Разделитель"
        , "236a17b3-7f44-46d9-a907-75f9cdc61ab5"  :  "_ПолеТабличногоДокумента"
        , "14c4a229-bfc3-42fe-9ce1-2da049fd0109"  :  "_ПолеТекстовогоДокумента"
        , "b1db1f86-abbb-4cf0-8852-fe6ae21650c2"  :  "_Индикатор"
        , "e3c063d8-ef92-41be-9c89-b70290b5368b"  :  "_ПолеКалендаря"
        , "42248403-7748-49da-b782-e4438fd7bff3"  :  "_ПолеГрафическойСхемы"
        , "6c06cd5d-8481-4b6f-a90a-7a97a8bb8bef"  :  "_ПолосаРегулирования"
        , "d92a805c-98ae-4750-9158-d9ce7cec2f20"  :  "_ПолеHTMLДокумента"
        , "ad37194e-555e-4305-b718-5dca84baf145"  :  "_ПолеГеографическойСхемы"
        , "a8b97779-1a4b-4059-b09c-807f86d2a461"  :  "_Диаграмма"
        , "e5fdc112-5c84-4a16-9728-72b85692b6e2"  :  "_ДиаграммаГанта"
        , "a26da99e-184a-4823-b0d6-62816d38dc4e"  :  "_СводнаяДиаграмма"
        , "984981b1-622d-4ebc-94f7-885f0cdfb59a"  :  "_Дендрограмма"

        # дальше собирал сам
        , "19f8b798-314e-4b4e-8121-905b2a7a03f5"  :  "_ПолеСписка"
        , "782e569a-79a7-4a4f-a936-b48d013936ec"  :  "_Переключатель"
        , "90db814a-c75f-4b54-bc96-df62e554d67d"  :  "_РамкаГруппы"
        , "64483e7f-3833-48e2-8c75-2c31aac49f6e"  :  "_ПолеВыбора"
    }

    return type_dict


def get_onec_types_ext():

    """выдает типы 1С в новом формате: сразу с указанием, кто массив, а кто имя и т.д."""

    _types=get_ones_types()

    nt = collections.namedtuple('onec_object', 'onec_name onec_type is_array comment')

    for key1,value1 in _types.items():  # 1 уровень - словарь известных типов

        new_list=[]
        for i in range(len(value1)):  # 2 уровень - массив, описывающий свойства данного типа
            key2 = value1[i]
            # print(key2)

            if key2 is None:
                new_list.append(
                    None
                    # nt(None, None, False, '')
                )
                continue

            new_type = ''
            new_name = ''
            is_array = False

            for word in key2.split():

                if word.endswith('*'):
                    is_array = True

                if word.startswith('#'):
                    new_type = clearName(word)
                else:
                    new_name = clearName(word)

            new_list.append(
                nt(onec_name = new_name, onec_type=new_type, is_array=is_array, comment= '')
                            )
            if new_type!='':
                test_type = _types[new_type]  # страховка: есть ли такой тип в списке
        _types[key1] = new_list  # заменим старый массив на новый

    return _types


def main():

    # for key,value in get_ones_types().items():
    #     if type(value) != list:
    #         print(key)
    #         print(value)
    #     pass

    _types = get_onec_types_ext()
    # import pickle

    enc = 'utf8'
    filename = '.types.json'
    with open(filename, 'w', encoding=enc) as fp:
        json.dump(_types, fp, ensure_ascii=False, indent='\t')
        # pickle.dump(_types, file=fp, protocol=0)

    # with open(filename, 'r', encoding=enc) as fp:
    #     # settings = json.load(fp)
    #     settings = pickle.load(fp, protocol=3)

    # print(settings)

def clearName(name_of_tag):
    return name_of_tag.replace('#', '').replace('*', '')


def _thinking():
    """
    Пора делать прямо классы и объекты, соответствующие объектам форм в 1С
    Т.е. Панель будет объектом, в ней будут свойства, и эти свойства будут читаться/писаться в некотором порядке.
    Что мне надо сейчас:
    просто раздать имена элементам управления в XML
    Это можно сделать отдельным методом в функции givenames(), например
    Или патчить givenames для того, чтобы переходить в другую функцию, когда натыкаемся на список ЭУ
    """

    pass


if __name__ == "__main__":
    main()