from .EpfParser import compileFile, decompileFile
from .EpfParser import settings
from .commons import exec_and_wait, base64_2_bin, bin_2_base64

from .InternalFileParser import *  # отладка
from .EpfParser import replace_module_of_managed_form, versions_file_arrange