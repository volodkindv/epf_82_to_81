from collections import namedtuple

onec_int_file = namedtuple('onec_int_file', 'internal readable')

mapping = [

    onec_int_file('bfc31a25-a67c-4b71-9cee-cb0e39957ff7.0', 'AddInDiadocAPI.zip')  # файл компоненты
    , onec_int_file('1073c9b7-35cd-498d-af2f-a127da6df33e.0', 'Модуль_Заглушка.epf')
    , onec_int_file('73797739-7365-4dc3-bfe2-a23530f97e47.0', 'Модуль_РаботаСВнешнимиПечатнымиФормами.epf')
    , onec_int_file('3b8492cb-52b2-4500-9bf4-217a8edffccb.0', 'Модуль_РаботаСРасширением.epf')
    , onec_int_file('51e501e3-c0d2-4462-a5a2-ceab3ffbb65d.0', 'Модуль_ИнтеграцияУниверсальный.epf')
    , onec_int_file('6c2c5dfe-19ba-4126-a0ba-80c8893cab37.0', 'Модуль_ИнтеграцияБП30.epf')
    , onec_int_file('bd336844-6a15-4640-bf86-852e6ee48f7c.0', 'Модуль_ИнтеграцияУТ11.epf')
    , onec_int_file('faf85bcc-323a-4d53-b596-9acc2ab49856.0', 'Модуль_ИнтеграцияБГУ20.epf')
    , onec_int_file('31bcb55d-62cf-402d-824d-8b0b38768901.0', 'Модуль_ИнтеграцияУНФ16.epf')
    # , onec_int_file('69ab5ab8-59de-4069-a5d0-9cd5a8e9a3b0.0', 'ФайлРасширения')
    # , onec_int_file('4501b96c-723a-47ed-bcb2-9f2e9ccd3881.0', 'ШаблонПодключаемогоМодуля.epf')

]


def erase_all():
    # все вложенные модули заменим на пустышки, чтобы основной модуль был легче

    file_names = get_file_names()
    exec_and_wait('"Service\\UnpackV8.exe" -parse "%s" "%s"' % (file_names['full_module_file_name'], file_names['unpack_dir']))

    for onec_file in mapping:
        bin_2_base64(  os.path.join(file_names['root_dir'], 'Service', 'empty.base64')
                     , os.path.join(file_names['unpack_dir'], onec_file.internal))

    exec_and_wait('"Service\\UnpackV8.exe" -build "%s" "%s"' % (file_names['unpack_dir'], file_names['full_module_file_name']))

    shutil.rmtree(file_names['unpack_dir'])


def pack_all_old():
    # все вложенные модули из текущей папки положить вовнутрь модуля

    file_names = get_file_names()
    exec_and_wait('"Service\\UnpackV8.exe" -parse "%s" "%s"' % (file_names['full_module_file_name'], file_names['unpack_dir']))

    for onec_file in mapping:
        bin_2_base64(  os.path.join(file_names['root_dir'], 'Макеты', onec_file.readable)
                     , os.path.join(file_names['unpack_dir'], onec_file.internal))

    exec_and_wait('"Service\\UnpackV8.exe" -build "%s" "%s"' % (file_names['unpack_dir'], file_names['full_module_file_name']))

    shutil.rmtree(file_names['unpack_dir'])


def decode_all():
    # извлечь все вложенные модули в текущую папку

    file_names = get_file_names()
    exec_and_wait('"Service\\UnpackV8.exe" -parse "%s" "%s"' % (file_names['full_module_file_name'], file_names['unpack_dir']))

    for onec_file in mapping:
        base64_2_bin(  os.path.join(file_names['unpack_dir'], onec_file.internal)
                     , os.path.join(file_names['root_dir'], 'Макеты', onec_file.readable))

    shutil.rmtree(file_names['unpack_dir'])


