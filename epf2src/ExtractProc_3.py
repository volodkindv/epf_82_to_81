# vim:fileencoding=cp1251
#
Version = """
ExtractProc
Version:        1.3
Authors:
    Alexander S. Gordienko <alex-go@vstu.kirov.ru>
    Alexey Dirks <adirks@ngs.ru>
"""
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

import sys, getopt, re, os, os.path, string
import asyncio


def bytes_to_file(filename, bytes):
        open(filename, 'wb').write(bytes)


#########################################################################
##############      Extract functions into files      ###################
#########################################################################
async def Extract(Dir, ModuleName):

        loop = asyncio.get_event_loop()

        FullName = os.path.join(Dir, ModuleName)
        ModuleName = os.path.splitext(ModuleName)[0]

        dir_len = len(SrcDir) + 1
        relDir = Dir[dir_len:]
        ExtractPath = os.path.join(DestDir, relDir, ModuleName)
        relModulePath = os.path.join(relDir, ModuleName)

        if not os.path.exists(ExtractPath):
                os.makedirs(ExtractPath)

        # inp = open(FullName, 'rb').read().decode('1251')
        inp = open(FullName, 'rb').read().decode('utf-8')

        Module = str(inp).split(os.linesep)
        newModule = ''

        headRem     = re.compile(r'^\s*//\*+\s*$', re.I)
        bodyRem     = re.compile(r'(^\s*//.*$|^\s*$)', re.I)
        forvardProc = re.compile(r'^\s*(?:�������|���������)\s+(?P<name>[0-9a-zA-Z�-��-�_]+)\s*' + \
                                r'\([^\)]*\)\s*(?:�������)?\s*(?:�����)', re.I)
        headProc    = re.compile(r'^\s*(?:�������|���������)\s+(?P<name>[0-9a-zA-Z�-��-�_]+)', re.I)
        tailProc    = re.compile(r'^\s*(?:������������|��������������).*$', re.I)
    
        State = 0
        LineNum = 0
        beginScope = 0
        endScope = 0
        procName = ''
        
        if Verbose > 0:
                pass
                # print(relModulePath + ':', 'windows-1251')
        
        for line in Module:
                head = ''.join(Module[LineNum:LineNum+10])
                if 0 == State:
                        tmp = headProc.match(line)
                        if (None == forvardProc.match(head)) and (None != tmp):
                                State = 2
                                procName = tmp.group('name')
                                beginScope = LineNum            
                        elif None != headRem.match(line):
                                State = 1
                                beginScope = LineNum            
                elif 1 == State:
                        tmp = headProc.match(line)
                        if (None == forvardProc.match(head)) and (None != tmp):
                                State = 2
                                procName = tmp.group('name')
                        elif None == bodyRem.match(line):
                                State = 0
                elif 2 == State:
                        if None != tailProc.match(line):
                                State = 0
                                newModule = newModule + os.linesep.join(Module[endScope:beginScope]) + \
                                        os.linesep + '//###��������� ' + procName + '.txt' + os.linesep
                                endScope = LineNum + 1

                                if Verbose > 1:
                                        print(str('    .' + procName, 'windows-1251'))
                                # writebytes = (os.linesep.join(Module[beginScope:endScope])).encode('1251')
                                writebytes = (os.linesep.join(Module[beginScope:endScope])).encode('utf-8')

                                loop.run_in_executor(None,
                                                     bytes_to_file,
                                                     os.path.join(ExtractPath, procName + '.txt'),
                                                     writebytes)
                LineNum += 1

        if Verbose > 1:
                print()

        newModuleBytes = (newModule + os.linesep.join(Module[endScope:])).encode('utf-8')
        open(os.path.join(ExtractPath, ModuleName + '.1ss'), 'wb').write(newModuleBytes)
        loop.run_in_executor(None,
                             bytes_to_file,
                             os.path.join(ExtractPath, ModuleName + '.1ss'),
                             newModuleBytes)

def visit(arg, dir, names):
        for name in names:
                if os.path.splitext(name)[1].upper() == '.1S':
                        Extract(dir, name)


#########################################################################
############## Assemble separate functions into single module  ##########
#########################################################################
def Assemble(Dir, ModuleName):
        dir_len = len(SrcDir) + 1
        relDir = Dir[dir_len:]

        FullModuleName = os.path.join(Dir, ModuleName)
        relName = os.path.join(relDir, ModuleName)
        ModuleName = os.path.splitext(ModuleName)[0]

        SkeletonDir = os.path.join(DestDir, relDir, ModuleName)
        SkeletonName = os.path.join(SkeletonDir, ModuleName + '.1ss')

        if not os.path.exists(SkeletonName):
                return
        
        if Verbose > 0:
                print(relName + ':', 'cp1251')

        ProcPlace = re.compile(r'^//###��������� (?P<ProcFile>\S+)\s*$', re.I)

        Module = ''
        ToWrite = 0

        inp = open(SkeletonName, 'rb').read().decode('utf-8')
        Skeleton = str(inp).split(os.linesep)
        for line in Skeleton:
                res = ProcPlace.match(line)
                if res != None:
                        ProcFile = os.path.join(SkeletonDir, res.group('ProcFile'))
                        Module = Module + open(ProcFile, 'rb').read().decode('utf-8') + os.linesep
                        ToWrite = 1

                        relName = res.group('ProcFile')

                        if Verbose > 1:
                                print('    .' + relName, 'cp1251')
                else:
                        Module = Module + line + os.linesep

        if Verbose > 1:
                print()

        # if len(Module)>len(os.linesep):
        #         Module = Module[:-len(os.linesep)]

        if ToWrite:
                # Module = Module.rstrip() + os.linesep #����� ������ ������ � ����� �����
                if len(Module) > len(os.linesep):
                        Module = Module[:-len(os.linesep)]

                open(FullModuleName, 'wb').write(Module.encode('utf-8'))

#------------------------------------------------------------------------
def visit_assemble(arg, dir, names):
        for name in names:
                if os.path.splitext(name)[1] in ('.1s', '.1S'):
                        Assemble(dir, name)

def main():
        global SrcDir, DestDir, Verbose
        
        try:
                opts, args = getopt.getopt(sys.argv[1:],
                                        'hEVemp:f:b:sv',
                                        ['help', 'examples', 
                                        'version', 'extract',
                                        'make', 'extract_path=',
                                        'file=', 'base_path=',
                                        'silent', 'verbose'])
        except getopt.GetoptError:
                usage()
                sys.exit(2)

        global fnModule, ExtractPath

        Action = 0    
        SrcDir = ''
        DestDir = ''
        fnModule = ''
        ProcessAll = 1
        Verbose = 1
    
        for o, a in opts:
                if o in ('-h', '--help'):
                        usage()
                        sys.exit()
                elif o in ('-E', '--examples'):
                        examples()
                elif o in ('-V', '--version'):
                        version()
                elif o in ('-e', '--extract'):
                        Action = 1
                elif o in ('-m', '--make'):
                        Action = 2
                elif o in ('-p', '--extract_path'):
                        DestDir = os.path.abspath(a)
                elif o in ('-f', '--file'):
                        fnModule = os.path.abspath(a)
                        ProcessAll = 0
                elif o in ('-b', '--base_path'):
                        SrcDir = os.path.abspath(a)
                        ProcessAll = 1
                elif o in ('-s', '--silent'):
                        if Verbose < 2:
                                Verbose = 0
                elif o in ('-v', '--verbose'):
                        Verbose = 2
                else:
                        usage()
                        sys.exit(2)

        if ProcessAll == 0:
                (SrcDir, fnModule) = os.path.split(fnModule)

        if SrcDir == '':
                SrcDir = r'.\Src'
        if DestDir == '':
                DestDir = SrcDir

        if Action == 1:
                if ProcessAll == 1:
                        os.path.walk(SrcDir, visit, '')
                else:
                        Extract(SrcDir, fnModule)
        elif Action == 2:
                if ProcessAll == 1:
                        os.path.walk(SrcDir, visit_assemble, '')
                else:          
                        Assemble(SrcDir, fnModule)
        else:
                usage()
                sys.exit(2)

def usage():
        print(r"""
������: ExtractProc.py {-h|-E|-V|-e|-m} 
                       [-b <base_path> | [-f <file>] [-p <extract_path>]] 
                       [-s|-v] 

���������:
    -h | --help         - ��� ������
    -E | --examples     - �������� ������� �������������
    -V | --version      - ����������� ������ ������� � �����
    -e | --extract      - ������� ���������/������� �� ������
    -m | --make         - ������ ���������/������� � ������
    -b | --base_path    - ���� � ������������� gcomp ������������
                            (�������������� ��� *.1s)
    -f | --file         - ���� ������
    -p | --extract_path - ���� ��� ����������
    -s | --silent       - "�����" ����� (������ ����� ������������� --verbose)
    -v | --verbose      - ����������� �����
""")

def examples():
        print(r"""
�������:
  
  ������� ������ '.\Src\���������\����������\�����������.1s' � ����� �� 
  ��������� ('.\Src\���������\����������\�����������\'):
    ExtractProc.py -e -f .\Src\���������\����������\�����������.1s

  ������� ������ '.\Src\����������������.1s' � ����� '.\Src\����������������\':
    ExtractProc.py -e -f .\Src\����������������.1s -p .\Src\����������������
  
  ������� ��� ������ ������������� ������������ ������������� � ����� �� 
  ��������� ('.\Src\'):
    ExtractProc.py -e
    
  ������� ��� ������ ������������� ������������ ������������� �
  ����� '.\SrcDir\':
    ExtractProc.py -e -b .\SrcDir\

  ������� ��� ������ ������������� ������������ ������������� �
  ����� '.\SrcDir\' � ����� c:\tmp\SrcDirExt\:
    ExtractProc.py -e -b .\SrcDir\ -p c:\tmp\SrcDirExt\

  �������� �������� ����������:
    ExtractProc.py -m
""")
        sys.exit()

def version():
        print(Version)
        sys.exit()


def extract_one(filename, deletesource = 1):
        global SrcDir, DestDir, Verbose, fnModule, ExtractPath
        SrcDir = os.path.dirname(filename)
        DestDir = SrcDir
        fnModule = filename
        Verbose = 1

        loop = asyncio.get_event_loop()
        loop.run_until_complete(Extract(SrcDir, fnModule))

        if deletesource == 1:
                os.remove(filename)


def assemble_one(filename, deletesource=1):
        global SrcDir, DestDir, Verbose, fnModule, ExtractPath
        SrcDir = os.path.dirname(filename)
        DestDir = SrcDir
        fnModule = filename
        # fnModule = os.path.basename(filename)
        Verbose = 0

        Assemble(SrcDir, fnModule)

        if not os.path.exists(fnModule):
                # ����� �������� ������ ����
                with open(fnModule, 'wb'):
                        pass
        # if deletesource == 1:
        #         os.remove(filename)

        # ���� ����� �������� ������� ������? ��� ���� ����� ��� ������ ������ epf ���� �����.
        # �����, ��������� ����������?


def test():
        _target = r'c:\Git\source_1c_test\������.1s'
        # extract_one( os.path.join(os.curdir, 'main_module.1s') ,deletesource = 0)
        extract_one(_target, False)
        assemble_one(_target, False)

if __name__ == '__main__':
#       main()
        test()
        # SrcDir = os.curdir
        # DestDir = SrcDir
        # fnModule = SrcDir + '\\main_module.1s'
        # Verbose = 1
        #
        # Extract(SrcDir, fnModule)


