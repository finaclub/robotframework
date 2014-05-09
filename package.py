#!/usr/bin/env python

"""Packaging script for Robot Framework

Usage:  package.py command version_number [release_tag]

Argument 'command' can have one of the following values:
  - sdist    : create source distribution
  - wininst  : create Windows installer
  - all      : create both packages
  - version  : update only version information in 'src/robot/version.py'
  - jar      : create stand-alone jar file containing RF and Jython

'version_number' must be a version number in format '2.x(.y)', 'trunk' or
'keep'. With 'keep', version information is not updated.

'release_tag' must be either 'alpha', 'beta', 'rc' or 'final', where all but
the last one can have a number after the name like 'alpha1' or 'rc2'. When
'version_number' is 'trunk', 'release_tag' is automatically assigned to the
current date.

When creating the jar distribution, jython.jar must be placed in 'ext-lib'
directory, under the project root.

This script uses 'setup.py' internally. Distribution packages are created
under 'dist' directory, which is deleted initially. Depending on your system,
you may need to run this script with administrative rights (e.g. with 'sudo').

Examples:
  package.py sdist 2.0 final
  package.py wininst keep
  package.py all 2.1.13 alpha
  package.py sdist trunk
  package.py version trunk
"""

from __future__ import with_statement, print_function
import sys
import os
from os.path import abspath, dirname, exists, join
import shutil
import re
import time
import subprocess
import zipfile
from glob import glob
import urllib


ROOT_PATH = abspath(dirname(__file__))
DIST_PATH = join(ROOT_PATH, 'dist')
BUILD_PATH = join(ROOT_PATH, 'build')
ROBOT_PATH = join(ROOT_PATH, 'src', 'robot')
JAVA_SRC = join(ROOT_PATH, 'src', 'java', 'org', 'robotframework')
JYTHON_VERSION = '2.5.3'
SETUP_PATH = join(ROOT_PATH, 'setup.py')
BITMAP = join(ROOT_PATH, 'robot.bmp')
INSTALL_SCRIPT = 'robot_postinstall.py'
VERSION_PATH = join(ROBOT_PATH, 'version.py')
POM_PATH = join(ROOT_PATH, 'pom.xml')
VERSIONS = [re.compile('^2\.\d+(\.\d+)?$'), 'trunk', 'keep']
RELEASES = [re.compile('^a\d*$'), re.compile('^b\d*$'),
            re.compile('^rc\d*$'), 'final']
VERSION_CONTENT = """# Automatically generated by 'package.py' script.

import sys

VERSION = '%(version_number)s'
RELEASE = '%(release_tag)s'
TIMESTAMP = '%(timestamp)s'

def get_version(sep=' '):
    if RELEASE == 'final':
        return VERSION
    return VERSION + sep + RELEASE

def get_full_version(who=''):
    sys_version = sys.version.split()[0]
    version = '%%s %%s (%%s %%s on %%s)' \\
        %% (who, get_version(), _get_interpreter(), sys_version, sys.platform)
    return version.strip()

def _get_interpreter():
    if sys.platform.startswith('java'):
        return 'Jython'
    if sys.platform == 'cli':
        return 'IronPython'
    if 'PyPy' in sys.version:
        return 'PyPy'
    return 'Python'
"""

def sdist(*version_info):
    version(*version_info)
    _clean()
    _create_sdist()
    _announce()

def wininst(*version_info):
    version(*version_info)
    _clean()
    if _verify_platform(*version_info):
        _create_wininst()
        _announce()

def all(*version_info):
    version(*version_info)
    _clean()
    _create_sdist()
    if _verify_platform(*version_info):
        _create_wininst()
    _announce()

def version(version_number, release_tag=None):
    _verify_version(version_number, VERSIONS)
    if version_number == 'keep':
        _keep_version()
    elif version_number =='trunk':
        _update_version(version_number, '%d%02d%02d' % time.localtime()[:3])
    else:
        _update_version(version_number, _verify_version(release_tag, RELEASES))
    sys.path.insert(0, ROBOT_PATH)
    from version import get_version
    return get_version(sep='')

def _verify_version(given, valid):
    for item in valid:
        if given == item or (hasattr(item, 'search') and item.search(given)):
            return given
    raise ValueError

def _update_version(version_number, release_tag):
    timestamp = '%d%02d%02d-%02d%02d%02d' % time.localtime()[:6]
    vfile = open(VERSION_PATH, 'w')
    vfile.write(VERSION_CONTENT % locals())
    vfile.close()
    # TODO: Fix before next final release
    #_update_pom_version(version_number, release_tag)
    print('Updated version to %s %s' % (version_number, release_tag))

def _update_pom_version(version_number, release_tag):
    version = '%s-%s' % (version_number, release_tag)
    pom_content = open(POM_PATH).read()
    with open(POM_PATH, 'w') as pom_file:
        pom_file.write(re.sub('(<version>).*(</version>)',
                              '\\1%s\\2' % version, pom_content))


def _keep_version():
    sys.path.insert(0, ROBOT_PATH)
    from version import get_version
    print('Keeping version %s' % get_version())

def _clean():
    print('Cleaning up...')
    for path in [DIST_PATH, BUILD_PATH]:
        if exists(path):
            shutil.rmtree(path)

def _verify_platform(version_number, release_tag=None):
    if release_tag == 'final' and os.sep != '\\':
        print('Final Windows installers can only be created in Windows.')
        print('Windows installer was not created.')
        return False
    return True

def _create_sdist():
    _create('sdist --force-manifest', 'source distribution')

def _create_wininst():
    _create('bdist_wininst --bitmap %s --install-script %s' % (BITMAP, INSTALL_SCRIPT),
            'Windows installer')
    if os.sep != '\\':
        print('Warning: Windows installers created on other platforms may not')
        print('be exactly identical to ones created in Windows.')

def _create(command, name):
    print('Creating %s...' % name)
    rc = os.system('%s %s %s' % (sys.executable, SETUP_PATH, command))
    if rc != 0:
        print('Creating %s failed.' % name)
        sys.exit(rc)
    print('%s created successfully.' % name.capitalize())

def _announce():
    print('Created:')
    for path in os.listdir(DIST_PATH):
        print(abspath(join(DIST_PATH, path)))

def jar(*version_info):
    jython_jar = _get_jython_jar()
    print('Using Jython %s' % jython_jar)
    ver = version(*version_info)
    tmpdir = _create_tmpdir()
    try:
        _compile_java_classes(tmpdir, jython_jar)
        _unzip_jython_jar(tmpdir, jython_jar)
        _copy_robot_files(tmpdir)
        _compile_all_py_files(tmpdir, jython_jar)
        _overwrite_manifest(tmpdir, ver)
        try:
            jar_path = _create_jar_file(tmpdir, ver)
            print('Created %s based on %s' % (jar_path, jython_jar))
        except subprocess.CalledProcessError:
            print("Unable to create jar! Check for jar command available at the command line.")
    except subprocess.CalledProcessError:
        print("Unable to compile java classes! Check for javac command available at the command line.")
    shutil.rmtree(tmpdir)

def _get_jython_jar():
    lib_dir = join(ROOT_PATH, 'ext-lib')
    jar_path = join(lib_dir, 'jython-standalone-%s.jar' % JYTHON_VERSION)
    if os.path.exists(jar_path):
        return jar_path
    if not os.path.exists(lib_dir):
        os.mkdir(lib_dir)
    dl_url = "http://search.maven.org/remotecontent?filepath=org/python/jython-standalone/%s/jython-standalone-%s.jar" \
            % (JYTHON_VERSION, JYTHON_VERSION)
    print('Jython not found, going to download from %s' % dl_url)
    urllib.urlretrieve(dl_url, jar_path)
    return jar_path

def _compile_java_classes(tmpdir, jython_jar):
    source_files = [join(JAVA_SRC, f)
                    for f in os.listdir(JAVA_SRC) if f.endswith('.java')]
    print('Compiling %d source files' % len(source_files))
    subprocess.check_call(['javac', '-d', tmpdir, '-target', '1.5', '-source', '1.5',
                     '-cp', jython_jar] + source_files, shell=os.name=='nt')

def _create_tmpdir():
    tmpdir = join(ROOT_PATH, 'tmp-jar-dir')
    if exists(tmpdir):
        shutil.rmtree(tmpdir)
    os.mkdir(tmpdir)
    return tmpdir

def _unzip_jython_jar(tmpdir, jython_jar):
    zipfile.ZipFile(jython_jar).extractall(tmpdir)

def _copy_robot_files(tmpdir):
    # pyc files must be excluded so that compileall works properly.
    todir = join(tmpdir, 'Lib', 'robot')
    shutil.copytree(ROBOT_PATH, todir, ignore=shutil.ignore_patterns('*.pyc'))
    shutil.rmtree(join(todir, 'htmldata', 'testdata'))

def _compile_all_py_files(tmpdir, jython_jar):
    subprocess.check_call(['java', '-jar', jython_jar, '-m', 'compileall', tmpdir])
    # Jython will not work without its py-files, but robot will
    for root, _, files in os.walk(join(tmpdir,'Lib','robot')):
        for f in files:
            if f.endswith('.py'):
                os.remove(join(root, f))

def _overwrite_manifest(tmpdir, version):
    with open(join(tmpdir, 'META-INF', 'MANIFEST.MF'), 'w') as mf:
        mf.write('''Manifest-Version: 1.0
Main-Class: org.robotframework.RobotFramework
Specification-Version: 2
Implementation-Version: %s
''' % version)

def _create_jar_file(source, version):
    path = join(DIST_PATH, 'robotframework-%s.jar' % version)
    if not exists(DIST_PATH):
        os.mkdir(DIST_PATH)
    _fill_jar(source, path)
    return path

def _fill_jar(sourcedir, jarpath):
    subprocess.check_call(['jar', 'cvfM', jarpath, '.'], cwd=sourcedir,
                    shell=os.name=='nt')


if __name__ == '__main__':
    try:
        globals()[sys.argv[1]](*sys.argv[2:])
    except (KeyError, IndexError, TypeError, ValueError):
        print(__doc__)

