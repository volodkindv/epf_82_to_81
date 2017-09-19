from EpfParser import *
from shutil import *

etalon = r'c:\Git\source_1c\service\lib_for_1c\epf2src\Форма_Пустышка_Эталон'
form_filename = etalon+'.form'
shutil.copy(etalon, form_filename)
replace_module_of_managed_form(form_filename, etalon+'.module', 'extract')

obj = ones_object(etalon)
obj.serialize_back(etalon+'.back')


