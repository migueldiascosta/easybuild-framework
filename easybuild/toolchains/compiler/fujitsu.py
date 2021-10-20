##
# Copyright 2014-2021 Ghent University
#
# This file is part of EasyBuild,
# originally created by the HPC team of Ghent University (http://ugent.be/hpc/en),
# with support of Ghent University (http://ugent.be/hpc),
# the Flemish Supercomputer Centre (VSC) (https://www.vscentrum.be),
# Flemish Research Foundation (FWO) (http://www.fwo.be/en)
# and the Department of Economy, Science and Innovation (EWI) (http://www.ewi-vlaanderen.be/en).
#
# https://github.com/easybuilders/easybuild
#
# EasyBuild is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation v2.
#
# EasyBuild is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with EasyBuild.  If not, see <http://www.gnu.org/licenses/>.
##
"""
Support for the Fujitsu compilers (i.e. fcc, frt).

:author: Miguel Dias Costa (National University of Singapore)
"""
import os
import re

import easybuild.tools.environment as env
import easybuild.tools.systemtools as systemtools
from easybuild.tools.build_log import EasyBuildError
from easybuild.tools.filetools import which
from easybuild.tools.toolchain.compiler import Compiler, DEFAULT_OPT_LEVEL

TC_CONSTANT_FUJITSU = 'Fujitsu'


class FujitsuCompiler(Compiler):
    """Generic support for using Fujitsu compiler drivers."""
    TOOLCHAIN_FAMILY = TC_CONSTANT_FUJITSU
    COMPILER_FAMILY = TC_CONSTANT_FUJITSU

    COMPILER_CC = 'fcc'
    COMPILER_CXX = 'FCC'

    COMPILER_F77 = 'frt'
    COMPILER_F90 = 'frt'
    COMPILER_FC = 'frt'

    COMPILER_UNIQUE_OPTION_MAP = {
        DEFAULT_OPT_LEVEL: 'O2',
        'lowopt': 'O1',
        'noopt': 'O0',
        'opt': 'Kfast',  # -O3 -Keval,fast_matmul,fp_contract,fp_relaxed,fz,ilfunc,mfunc,omitfp,simd_packed_promotion
        'optarch': '',  # Fujitsu compiler by default generates code for the arch it is running on
        'openmp': 'Kopenmp',
        'unroll': 'funroll-loops',
        # apparently the -Kfp_precision flag doesn't work in clang mode, will need to look into these later
        # also at strict vs precise and loose vs veryloose
        'strict': ['Knoeval,nofast_matmul,nofp_contract,nofp_relaxed,noilfunc'],  # ['Kfp_precision'],
        'precise': ['Knoeval,nofast_matmul,nofp_contract,nofp_relaxed,noilfunc'],  # ['Kfp_precision'],
        'defaultprec': [],
        'loose': ['Kfp_relaxed'],
        'veryloose': ['Kfp_relaxed'],
        # apparently the -K[NO]SVE flags don't work in clang mode
        # SVE is enabled by default, -Knosimd seems to disable it
        'vectorize': {False: 'Knosimd', True: ''},
    }

    # used when 'optarch' toolchain option is enabled (and --optarch is not specified)
    COMPILER_OPTIMAL_ARCHITECTURE_OPTION = {
        # -march=archi[+features]. At least on Fugaku, these are set by default (-march=armv8.3-a+sve and -mcpu=a64fx)
        (systemtools.AARCH64, systemtools.ARM): '',
    }

    # used with --optarch=GENERIC
    COMPILER_GENERIC_OPTION = {
        (systemtools.AARCH64, systemtools.ARM): '-mcpu=generic -mtune=generic',
    }

    compiler_prefix = None

    def prepare(self, *args, **kwargs):

        try:
            self.compiler_prefix = os.path.split(os.path.dirname(which(self.COMPILER_CC)))[0]
        except TypeError:
            raise EasyBuildError("Could not find path to Fujitsu compiler. You may need to load the correct module"
                                 "for your system.")

        super(FujitsuCompiler, self).prepare(*args, **kwargs)

        # fcc doesn't accept e.g. -std=c++11 or -std=gnu++11, only -std=c11 or -std=gnu11
        pattern = r'-std=(gnu|c)\+\+(\d+)'
        if re.search(pattern, self.vars['CFLAGS']):
            self.log.debug("Found '-std=(gnu|c)++' in CFLAGS, fcc doesn't accept '++' here, removing it")
            self.vars['CFLAGS'] = re.sub(pattern, r'-std=\1\2', self.vars['CFLAGS'])
            self._setenv_variables()

        # make sure fujitsu compiler paths are added to the relevant environment variables
        clang_libdir = os.path.join('clang-comp', 'lib64')
        path_variables = {'bin': ['PATH'],
                          'lib64': ['LIBRARY_PATH', 'LD_LIBRARY_PATH'],
                          clang_libdir: ['LIBRARY_PATH', 'LD_LIBRARY_PATH']}
        for subdir, var_names in path_variables.items():
            for var_name in var_names:
                var_value = os.getenv(var_name, '')
                path = os.path.join(self.compiler_prefix, subdir)
                if path not in var_value:
                    self.log.debug("Adding %s to $%s" % (path, var_name))
                    env.setvar(var_name, os.pathsep.join([var_value, path]))

        # make sure compiler_prefix/include folder is not in environment, conflicts with clang mode
        inc_path = os.path.join(self.compiler_prefix, 'include')
        for var_name in os.environ:
            var_value = os.getenv(var_name, '')
            if inc_path in var_value:
                self.log.debug("Removing %s from $%s" % (inc_path, var_name))
                env.setvar(var_name, os.pathsep.join([p for p in var_value.split(os.pathsep) if inc_path not in p]))

    def _set_compiler_vars(self):
        super(FujitsuCompiler, self)._set_compiler_vars()

        # enable clang compatibility mode
        self.variables.nappend('CFLAGS', ['Nclang'])
        self.variables.nappend('CXXFLAGS', ['Nclang'])

        # also add fujitsu module library paths to LDFLAGS
        for subdir in ['', 'clang-comp']:
            libdir = os.path.join(self.compiler_prefix, subdir, 'lib64')
            self.log.debug("Adding %s to $LDFLAGS" % libdir)
            self.variables.nappend('LDFLAGS', [libdir])
