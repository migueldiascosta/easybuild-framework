#!/usr/bin/env python
# Copyright 2015-2016 Ghent University
#
# This file is part of EasyBuild,
# originally created by the HPC team of Ghent University (http://ugent.be/hpc/en),
# with support of Ghent University (http://ugent.be/hpc),
# the Flemish Supercomputer Centre (VSC) (https://www.vscentrum.be),
# Flemish Research Foundation (FWO) (http://www.fwo.be/en)
# and the Department of Economy, Science and Innovation (EWI) (http://www.ewi-vlaanderen.be/en).
#
# http://github.com/hpcugent/easybuild
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
Script to find reverse dependencies of easyconfigs and/or easyblocks

:author: Miguel Dias Costa (National University of Singapore)
"""
import os
import sys

from vsc.utils.generaloption import SimpleOption

from easybuild.framework.easyconfig.parser import EasyConfigParser
from easybuild.framework.easyconfig.templates import template_constant_dict
from easybuild.tools.build_log import EasyBuildError
from easybuild.tools.config import init_build_options
from easybuild.tools.filetools import find_easyconfigs
from easybuild.tools.toolchain import DUMMY_TOOLCHAIN_NAME


class ReverseDependenciesOption(SimpleOption):
    """Custom option parser for this script."""
    ALLOPTSMANDATORY = False


def get_names(ec_file):
    ec = EasyConfigParser(ec_file).get_config_dict()
    template_values = template_constant_dict(ec)

    name = "%(name)s/%(version)s" % ec

    if ec['toolchain']['name'] != DUMMY_TOOLCHAIN_NAME:
        name += "-%(name)s-%(version)s" % ec['toolchain']

    if 'versionsuffix' in ec:
        versionsuffix = ec['versionsuffix'] % template_values
        name += versionsuffix

    dep_names = []
    if 'dependencies' in ec:
        for dependency in ec['dependencies']:

            dep_name = "%s/%s" % dependency[:2]

            if ec['toolchain']['name'] != DUMMY_TOOLCHAIN_NAME:
                dep_name += "-%(name)s-%(version)s" % ec['toolchain']

            # dependency versionsuffix
            if len(dependency) == 3:
                dep_name += dependency[2] % template_values

            dep_names.append(dep_name)

    # also include toolchain as dependency (likely not complete)
    if ec['toolchain']['name'] != DUMMY_TOOLCHAIN_NAME:
        dep_names.append("%(name)s/%(version)s" % ec['toolchain'])

    return (name, dep_names)


def update_vertex(depgraph, name, ec_file=None, dependencies=None, dependant=None):

    if not name in depgraph:
        depgraph[name] = {}
        depgraph[name]['dependencies'] = []
        depgraph[name]['dependants'] = []

    if ec_file:
        depgraph[name]['spec'] = ec_file

    if dependencies:
        depgraph[name]['dependencies'] = dependencies
        for dependency in dependencies:
            update_vertex(depgraph, dependency, dependant=depgraph[name]['spec'])

    if dependant:
        depgraph[name]['dependants'].append(dependant)

# MAIN

try:
    init_build_options()

    options = {
        'robot-path': ("Where to look for dependants", None, 'store', None),
    }
    go = ReverseDependenciesOption(options)

    if go.options.robot_path:
        robot_path = [go.options.robot_path]
    else:
        robot_path = go.args

    ec_files = [ec for p in go.args for ec in find_easyconfigs(p)]
    if not ec_files:
        raise EasyBuildError("No easyconfig files specified")

    candidate_ec_files = [ec for p in robot_path for ec in find_easyconfigs(p)]
    if not candidate_ec_files:
        raise EasyBuildError("No easyconfig files in robot-path")

    depgraph = {}

    ecs = []
    for ec_file in ec_files:
        try:
            name, dep_names = get_names(ec_file)
            ecs.append(name)
        except EasyBuildError, err:
            sys.stderr.write("Ignoring issue when processing %s: %s", ec_file, err)

    for ec_file in candidate_ec_files:
        try:
            name, dep_names = get_names(ec_file)
            update_vertex(depgraph, name, ec_file, dependencies=dep_names)
        except EasyBuildError, err:
            sys.stderr.write("Ignoring issue when processing %s: %s", ec_file, err)

    dependants = []
    for name in ecs:
        if name in depgraph:
            dependants.extend(depgraph[name]['dependants'])

    for dependant in sorted(dependants):
        print dependant

except EasyBuildError, err:
    sys.stderr.write("ERROR: %s\n" % err)
    sys.exit(1)
