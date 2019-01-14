# Copyright (C) 2012 Red Hat, Inc.
# Authors: Jan Kaluza <jkaluza@redhat.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301,
# USA.

from __future__ import print_function

import os
import errno
from subprocess import Popen, PIPE
import hashlib
import re
from progressbar import ProgressBar


def print_file_info(file_binary='file'):
    if not file_binary.startswith("/") and not file_binary.startswith("./") \
            and not file_binary.startswith("../"):
        popen = Popen('which ' + file_binary, shell=True, bufsize=4096,
                      stdout=PIPE)
        pipe = popen.stdout
        output_which = pipe.read().strip()
        if popen.wait() != 0:
            raise ValueError('could not query {0} for its version ({1})!'
                             .format(file_binary, output_which))
    else:
        output_which = file_binary
    popen = Popen(file_binary + " --version", shell=True, bufsize=4096,
                  stdout=PIPE)
    pipe = popen.stdout
    output_ver = pipe.read().strip()
    if popen.wait() not in (0, 1):
        raise ValueError('could not query {0} for its version ({1})!'
                         .format(file_binary, output_ver))
    print('using file from', output_which)
    print('version is', output_ver)


def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc:  # Python >2.5
        if exc.errno == errno.EEXIST:
            pass
        else:
            raise


def get_file_output(filename, binary="file"):
    popen = Popen(binary + " -b " + filename, shell=True, bufsize=4096,
                  stdout=PIPE, stderr=PIPE)
    pipe = popen.stdout
    output = pipe.read()
    output_err = popen.stderr.read()
    if popen.wait() != 0:
        return "Error while calling file, output: " + str(output) + \
               str(output_err)
    return output


def get_file_mime(filename, binary="file"):
    popen = Popen(binary + " -ib " + filename, shell=True, bufsize=4096,
                  stdout=PIPE, stderr=PIPE)
    pipe = popen.stdout
    output = pipe.read()
    output_err = popen.stderr.read()
    if popen.wait() != 0:
        return "Error while calling file, output: " + str(output) + \
               str(output_err)
    return output


def get_simple_metadata(filename, binary="file"):
    metadata = {}
    metadata['output'] = get_file_output(filename, binary)
    metadata['mime'] = get_file_mime(filename, binary)
    return metadata


def _split_patterns(pattern_id=0, magdir="Magdir", file_name="file",
                    only_name=False):
    FILE_BINARY_HASH = hashlib.sha224(file_name).hexdigest()
    outputdir = ".mgc_temp/" + FILE_BINARY_HASH + "/output"
    mkdir_p(outputdir)

    files = os.listdir(magdir)
    files.sort()
    if len(files) == 0:
        raise ValueError('no files found in Magdir {0}'
                         .format(os.path.join(os.getcwd(), magdir)))
    prog = ProgressBar(0, len(files), 50, mode='fixed', char='#')
    for loop_file_name in files:
        mfile = os.path.join(magdir, loop_file_name)
        if os.path.isdir(mfile):
            continue
        buff = ""
        in_pattern = False
        prog.increment_amount()
        print(prog, "Splitting patterns", end='\r', flush=True)
        with open(mfile, "r") as reader:
            lines = reader.readlines()
        for line_idx, line in enumerate(lines):
            if line.strip().startswith("#") or len(line.strip()) == 0:
                continue
            # print(line.strip()
            if line.strip()[0].isdigit() or \
                    (line.strip()[0] == '-' and line.strip()[1].isdigit()):
                if in_pattern:
                    with open(os.path.join(outputdir, str(pattern_id)), "w") \
                            as writer:
                        writer.write(buff)
                    in_pattern = False
                buff = ""
                if only_name:
                    if not re.match("^[0-9]*(\\s)*name", line.strip()):
                        continue
                in_pattern = True
                pattern_id += 1
                buff += "#" + loop_file_name + "\n"
                buff += "# Automatically generated from:\n"
                buff += "#" + loop_file_name + ":" + str(line_idx) + "\n"
                buff += line
            elif line.strip().startswith(">") or line.strip().startswith("!"):
                if in_pattern:
                    buff += line
                elif only_name == False:
                    print("broken pattern in file '" + loop_file_name + "':" +
                          str(line_idx))
        if in_pattern:
            with open(os.path.join(outputdir, str(pattern_id)), "w") as writer:
                writer.write(buff)
    return pattern_id


def split_patterns(magdir="Magdir", file_name="file"):
    pattern_id = _split_patterns(0, magdir, file_name, True)
    _split_patterns(pattern_id, magdir, file_name)

    print('')


def compile_patterns(file_name="file", file_binary="file"):
    FILE_BINARY_HASH = hashlib.sha224(file_name).hexdigest()
    magdir = ".mgc_temp/" + FILE_BINARY_HASH + "/output"
    files = os.listdir(magdir)
    if len(files) == 0:
        raise ValueError('no files found in Magdir {0}'
                         .format(os.path.join(os.getcwd(), magdir)))
    files.sort(key=lambda x: [int(x)])
    mkdir_p(".mgc_temp")
    mkdir_p(".mgc_temp/" + FILE_BINARY_HASH)
    mkdir_p(".mgc_temp/" + FILE_BINARY_HASH + "/tmp")
    prog = ProgressBar(0, len(files), 50, mode='fixed', char='#')

    for file_index, loop_file_name in enumerate(files):
        out_file = ".mgc_temp/" + FILE_BINARY_HASH + "/.find-magic.tmp." + \
                   str(file_index) + ".mgc"
        if not os.path.exists(out_file):
            with open(os.path.join(magdir, loop_file_name), "r") as reader:
                buf = reader.read()
            first_line = buf.split("\n")[0][1:len(buf.split("\n")[0])]
            with open(os.path.join(".mgc_temp/" + FILE_BINARY_HASH + \
                                   "/tmp/" + first_line), "a") as appender:
                appender.write(buf)
                appender.flush()
            # tmp = open(".mgc_temp/" + FILE_BINARY_HASH + "/.find-magic.tmp",
            #            "a")
            # tmp.write(buf)
            # tmp.flush()
            # tmp.close()
            # os.chdir(".mgc_temp")
            # print("cp .mgc_temp/.find-magic.tmp " +
            #       ".mgc_temp/.find-magic.tmp." + str(file_index) + ";" +
            #       FILE_BINARY + " -C -m .mgc_temp/.find-magic.tmp." +
            #       str(file_index) + ";")
            # mv .find-magic.tmp." + str(file_index) + ".mgc .mgc_temp/;

            # os.system("cp .mgc_temp/" + FILE_BINARY_HASH +
            #           "/.find-magic.tmp .mgc_temp/" + FILE_BINARY_HASH +
            #           "/.find-magic.tmp." + str(file_index) + ";" +
            #           "file -C -m .mgc_temp/" + FILE_BINARY_HASH +
            #           "/.find-magic.tmp." + str(file_index) + ";")
            cmd = file_binary + " -C -m .mgc_temp/" + FILE_BINARY_HASH + "/tmp"
            ret_code = os.system(cmd)
            if ret_code != 0:
                raise ValueError('command {0} returned non-zero exit code {1}!'
                                 .format(cmd, ret_code))
            if os.path.exists("tmp.mgc"):
                ret_code = os.system("mv tmp.mgc " + out_file)
                if ret_code != 0:
                    raise ValueError('moving tmp.mgc to {0} failed with code '
                                     '{1}!'.format(out_file, ret_code))
            # os.chdir("..")
        prog.increment_amount()
        print(prog, "Compiling patterns", end='\r', flush=True)
    print("")


def get_full_metadata(infile, file_name="file", compiled=True,
                      file_binary="file"):
    """
    file-output plus binary search to find the relevant line in magic file
    """
    COMPILED_SUFFIX = ".mgc"
    if not compiled:
        COMPILED_SUFFIX = ""
    FILE_BINARY_HASH = hashlib.sha224(file_name).hexdigest()
    magdir = ".mgc_temp/" + FILE_BINARY_HASH + "/output"
    FILE_BINARY = file_binary
    files = os.listdir(magdir)
    files.sort(key=lambda x: [int(x)])
    tlist = []
    mkdir_p(".mgc_temp")

    # Divide and conquer
    idx_left = 0                # left-most index to consider
    idx_rigt = len(files) - 1   # right-most index to consider
    idx_curr = idx_rigt         # some index in the middle we currently test

    # out_left = ""             # ouput at idx_left, unused
    out_rigt = None             # output at idx_rigt

    while True:
        file_curr = files[idx_curr]          # file name at idx_curr
        cmd = FILE_BINARY + " -b " + infile + " -m .mgc_temp/" + \
              FILE_BINARY_HASH + "/.find-magic.tmp." + str(idx_curr) + \
              COMPILED_SUFFIX
        # print(FILE_BINARY + " " + infile + " -m .mgc_temp/" +
        #       FILE_BINARY_HASH + "/.find-magic.tmp." + str(idx_curr) +
        #       COMPILED_SUFFIX)
        popen = Popen(cmd, shell=True, bufsize=4096, stdout=PIPE)
        pipe = popen.stdout
        out_curr = pipe.read()
        if popen.wait() != 0:
            return dict(output=None, mime=None, pattern=None, suffix=None,
                        err=(cmd, out_curr.strip()))
        if out_rigt == None:
            out_rigt = out_curr
        # idx_left---------idx_curr---------idx_rigt
        # out_left   ==    out_curr     \solution here
        if out_curr != out_rigt:
            idx_left = idx_curr
            # out_left = out_curr
        # idx_left-------------------idx_curr-------------------idx_rigt
        #   solution here/           out_curr        ==         out_rigt
        else:
            idx_rigt = idx_curr
            out_rigt = out_curr

        if idx_curr == idx_left + (idx_rigt - idx_left) / 2:
            if out_rigt != out_curr:
                idx_curr += 1
                out_curr = out_rigt
            file_curr = files[idx_curr]
            # if file_curr in PATTERNS:
            # PATTERNS.remove(file_curr);
            # print(idx_curr, file_curr)
            with open(os.path.join(magdir, file_curr), "r") as reader:
                buf = reader.read()
            if os.path.exists(os.path.dirname(FILE_BINARY) +
                              "/../magic/magic.mime.mgc"):
                cmd = FILE_BINARY + " -bi " + infile + " -m " + \
                      os.path.dirname(FILE_BINARY) + "/../magic/magic"
            else:
                cmd = FILE_BINARY + " -bi " + infile + " -m .mgc_temp/" + \
                      FILE_BINARY_HASH + "/.find-magic.tmp." + str(idx_curr) +\
                      COMPILED_SUFFIX
            popen = Popen(cmd, shell=True, bufsize=4096, stdout=PIPE)
            pipe = popen.stdout
            mime = pipe.read()
            if popen.wait() != 0:
                return dict(output=None, mime=None, pattern=None, suffix=None,
                            err=(cmd, mime.strip()))
            tlist.append(out_curr)
            index = infile.find('.')
            if index == -1:
                suffix = ""
            else:
                suffix = infile[index:]
            if out_curr == "data\n" and idx_curr == 0:
                buf = ""
            return dict(output=out_curr, mime=mime, pattern=buf, suffix=suffix)
        else:
            # set idx_curr to middle between idx_left and idx_rigt
            idx_curr = idx_left + (idx_rigt - idx_left) / 2


def is_compilation_supported(file_name="file", file_binary="file"):
    FILE_BINARY_HASH = hashlib.sha224(file_name).hexdigest()
    if os.system(file_binary + " /bin/sh -m .mgc_temp/" + FILE_BINARY_HASH +
                 "/.find-magic.tmp.0.mgc > /dev/null") != 0:
        print('')
        print("This file version doesn't support compiled patterns "
              "=> they won't be used")
        return False
    else:
        print('Compiled patterns will be used')
        print('')
        return True
