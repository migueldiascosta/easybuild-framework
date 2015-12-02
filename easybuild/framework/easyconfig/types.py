# #
# Copyright 2015-2015 Ghent University
#
# This file is part of EasyBuild,
# originally created by the HPC team of Ghent University (http://ugent.be/hpc/en),
# with support of Ghent University (http://ugent.be/hpc),
# the Flemish Supercomputer Centre (VSC) (https://vscentrum.be/nl/en),
# the Hercules foundation (http://www.herculesstichting.be/in_English)
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
# #

"""
Support for checking types of easyconfig parameter values.

@author: Kenneth Hoste (Ghent University)
"""
from vsc.utils import fancylogger

from easybuild.tools.build_log import EasyBuildError

_log = fancylogger.getLogger('easyconfig.types', fname=False)


def dict2tuple(dict_value):
    """Help function, convert dict value to hashable equivalent via tuples."""
    res = []
    for key, val in sorted(dict_value.items()):
        if isinstance(val, list):
            val = tuple(val)
        res.append((key, val))
    return tuple(res)


def is_value_of_type(value, expected_type):
    """
    Check whether specified value matches a particular very specific (non-trivial) type,
    which is specified by means of a 2-tuple: (parent type, tuple with additional type requirements).

    @param value: value to check the type of
    @param typ_spec: specific type of dict to check for
    """
    type_ok = False

    if expected_type in EASY_TYPES:
        # easy types can be checked using isinstance
        type_ok = isinstance(value, expected_type)

    elif expected_type in CHECKABLE_TYPES:
        parent_type = expected_type[0]
        extra_reqs = dict(expected_type[1])
        # first step: check parent type
        type_ok = isinstance(value, parent_type)
        if type_ok:
            _log.debug("Parent type of value %s matches %s, going in...", value, parent_type)
            # second step: check additional type requirements
            if parent_type == dict:
                extra_req_checkers = {
                    # check whether all keys have allowed types
                    'key_types': lambda val:
                        all([any(is_value_of_type(el, t) for t in extra_reqs['key_types']) for el in val.keys()]),
                    'opt_keys': lambda val:
                        all([k in extra_reqs['required_keys']+extra_reqs['opt_keys'] for k in val.keys()]),
                    'required_keys': lambda val: all([k in val.keys() for k in extra_reqs['required_keys']]),
                    # check whether all values have allowed types
                    'value_types': lambda val:
                        all([any(is_value_of_type(el, t) for t in extra_reqs['value_types']) for el in val.values()]),
                }
            elif parent_type == list:
                extra_req_checkers = {
                    # check required type
                    'value_types': lambda val:
                        all([any(is_value_of_type(el, t) for t in extra_reqs['value_types']) for el in val]),
                }

            else:
                raise EasyBuildError("Don't know how to check value with parent type %s", parent_type)

            for er_key in extra_reqs:
                if er_key in extra_req_checkers:
                    check_ok = extra_req_checkers[er_key](value)
                    msg = ('FAILED', 'passed')[check_ok]
                    type_ok &= check_ok
                    _log.debug("Check for %s requirement (%s) %s for %s", er_key, extra_reqs[er_key], msg, value)
                else:
                    raise EasyBuildError("Unknown type requirement specified: %s", er_key)
            msg = ('FAILED', 'passed')[type_ok]
            _log.debug("Non-trivial value type checking of easyconfig value '%s': %s", value, msg)

        else:
            _log.debug("Parent type of value %s doesn't match %s: %s", value, parent_type, type(value))

    else:
        raise EasyBuildError("Don't know how to check whether specified value is of type %s", expected_type)

    return type_ok


def check_type_of_param_value(key, val, auto_convert=False):
    """
    Check value type of specified easyconfig parameter.

    @param key: name of easyconfig parameter
    @param val: easyconfig parameter value, of which type should be checked
    @param auto_convert: try to automatically convert to expected value type if required
    """
    type_ok, newval = False, None
    expected_type = TYPES.get(key)

    # check value type
    if expected_type is None:
        _log.debug("No type specified for easyconfig parameter '%s', so skipping type check.", key)
        type_ok = True

    else:
        type_ok = is_value_of_type(val, expected_type)

    # determine return value, attempt type conversion if needed/requested
    if type_ok:
        _log.debug("Value type check passed for %s parameter value: %s", key, val)
        newval = val
    elif auto_convert:
        _log.debug("Value type check for %s parameter value failed, going to try to automatically convert to %s",
                   key, expected_type)
        # convert_value_type will raise an error if the conversion fails
        newval = convert_value_type(val, expected_type)
        type_ok = True
    else:
        _log.debug("Value type check for %s parameter value failed, auto-conversion of type not enabled", key)

    return type_ok, newval


def convert_value_type(val, typ):
    """
    Try to convert type of provided value to specific type.

    @param val: value to convert type of
    @param typ: target type
    """
    res = None

    if typ in EASY_TYPES and isinstance(val, typ):
        _log.debug("Value %s is already of specified target type %s, no conversion needed", val, typ)
        res = val

    elif typ in CHECKABLE_TYPES and is_value_of_type(val, typ):
        _log.debug("Value %s is already of specified non-trivial target type %s, no conversion needed", val, typ)
        res = val

    elif typ in TYPE_CONVERSION_FUNCTIONS:
        func = TYPE_CONVERSION_FUNCTIONS[typ]
        _log.debug("Trying to convert value %s (type: %s) to %s using %s", val, type(val), typ, func)
        try:
            res = func(val)
            _log.debug("Type conversion seems to have worked, new type: %s", type(res))
        except Exception as err:
            raise EasyBuildError("Converting type of %s (%s) to %s using %s failed: %s", val, type(val), typ, func, err)

        if not isinstance(res, typ):
            raise EasyBuildError("Converting value %s to type %s didn't work as expected: got %s", val, typ, type(res))

    else:
        raise EasyBuildError("No conversion function available (yet) for target type %s", typ)

    return res


def to_name_version_dict(spec):
    """
    Convert a comma-separated string or 2-element list of strings to a dictionary with name/version keys.
    If the specified value is a dict already, the keys are checked to be only name/version.

    For example: "intel, 2015a" => {'name': 'intel', 'version': '2015a'}

    @param spec: a comma-separated string with two values, or a 2-element list of strings, or a dict
    """
    # check if spec is a string or a list of two values; else, it can not be converted
    if isinstance(spec, basestring):
        spec = spec.split(',')

    if isinstance(spec, list):
        # 2-element list
        if len(spec) == 2:
            res = {'name': spec[0].strip(), 'version': spec[1].strip()}
        else:
            raise EasyBuildError("Can not convert list %s to name and version dict. Expected 2 elements", spec)

    elif isinstance(spec, dict):
        # already a dict, check keys
        if sorted(spec.keys()) == ['name', 'version']:
            res = spec
        else:
            raise EasyBuildError("Incorrect set of keys in provided dictionary, should be only name/version: %s", spec)

    else:
        raise EasyBuildError("Conversion of %s (type %s) to name and version dict is not supported", spec, type(spec))

    return res


def to_dependency(dep):
    """
    Convert a dependency dict obtained from parsing a .yeb easyconfig
    to a dependency dict with name/version/versionsuffix/toolchain keys

    Example:
        {'foo': '1.2.3', 'toolchain': 'GCC, 4.8.2'}
        to
        {'name': 'foo', 'version': '1.2.3', 'toolchain': {'name': 'GCC', 'version': '4.8.2'}}
    """
    depspec = {}
    if isinstance(dep, dict):
        found_name_version = False
        for key, value in dep.items():
            if key in ['name', 'version', 'versionsuffix']:
                depspec[key] = value
            elif key == 'toolchain':
                depspec['toolchain'] = to_name_version_dict(value)
            elif not found_name_version:
                depspec.update({'name': key, 'version': value})
            else:
                raise EasyBuildError("Found unexpected (key, value) pair: %s, %s", key, value)

            if 'name' in depspec and 'version' in depspec:
                found_name_version = True

        if not found_name_version:
            raise EasyBuildError("Can not parse dependency without name and version: %s", dep)

    # also deal with dependencies in the "old" format
    elif isinstance(dep, (tuple, list)):
        if len(dep) >= 2:
            depspec.update({
                'name': dep[0],
                'version': dep[1],
            })
        if len(dep) >= 3:
            depspec.update({'versionsuffix': dep[2]})
        if len(dep) >= 4:
            depspec.update({'toolchain': dep[3]})
    else:
        raise EasyBuildError("Can not convert %s (type %s) to dependency dict", dep, type(dep))

    return depspec


def to_dependencies(dep_list):
    """
    Convert a list of dependencies obtained from parsing a .yeb easyconfig
    to a list of dependencies in the correct format
    """
    return [to_dependency(dep) for dep in dep_list]


# these constants use functions defined in this module, so they needs to be at the bottom of the module

# specific type: dict with only name/version as keys, and with string values
# additional type requirements are specified as tuple of tuples rather than a dict, since this needs to be hashable
NAME_VERSION_DICT = (dict, dict2tuple({
    'required_keys': ['name', 'version'],
    'opt_keys': [],
    'value_types': [str],
}))

DEPENDENCY_DICT = (dict, dict2tuple({
    'opt_keys': ('versionsuffix', 'toolchain'),
    'required_keys': ('name','version'),
}))
DEPENDENCIES = (list, (('value_types', (DEPENDENCY_DICT,)),))

CHECKABLE_TYPES = [NAME_VERSION_DICT, DEPENDENCIES, DEPENDENCY_DICT]

# easy types, that can be verified with isinstance
EASY_TYPES = [basestring, dict, int, list, str, tuple]

# type checking is skipped for easyconfig parameters names not listed in TYPES
TYPES = {
    'dependencies': DEPENDENCIES,
    'name': basestring,
    'toolchain': NAME_VERSION_DICT,
    'version': basestring,
}

TYPE_CONVERSION_FUNCTIONS = {
    basestring: str,
    float: float,
    int: int,
    str: str,
    DEPENDENCIES: to_dependencies,
    NAME_VERSION_DICT: to_name_version_dict,
}
