# Copyright (c) Meta Platforms, Inc. and affiliates.
# SPDX-License-Identifier: LGPL-2.1-or-later

import re
import sys
from typing import NamedTuple, Sequence, TextIO, Tuple


class ConstantClass(NamedTuple):
    name: str
    enum_class: str
    regex: str
    constants: Sequence[Tuple[str, str]] = ()


CONSTANTS = (
    ConstantClass("Architecture", "Enum", r"DRGN_ARCH_([a-zA-Z0-9_]+)"),
    ConstantClass("FindObjectFlags", "Flag", r"DRGN_FIND_OBJECT_([a-zA-Z0-9_]+)"),
    ConstantClass(
        "PlatformFlags",
        "Flag",
        r"DRGN_PLATFORM_([a-zA-Z0-9_]+)(?<!DRGN_PLATFORM_DEFAULT_FLAGS)",
    ),
    ConstantClass("PrimitiveType", "Enum", r"DRGN_(C)_TYPE_([a-zA-Z0-9_]+)"),
    ConstantClass(
        "ProgramFlags", "Flag", r"DRGN_PROGRAM_([a-zA-Z0-9_]+)(?<!DRGN_PROGRAM_ENDIAN)"
    ),
    ConstantClass(
        "Qualifiers", "Flag", r"DRGN_QUALIFIER_([a-zA-Z0-9_]+)", [("NONE", "0")]
    ),
    ConstantClass("SymbolBinding", "Enum", r"DRGN_SYMBOL_BINDING_([a-z-A-Z0-9_]+)"),
    ConstantClass("SymbolKind", "Enum", r"DRGN_SYMBOL_KIND_([a-z-A-Z0-9_]+)"),
    ConstantClass("TypeKind", "Enum", r"DRGN_TYPE_([a-zA-Z0-9_]+)"),
)


def gen_constant_class(
    drgn_h: str, output_file: TextIO, constant_class: ConstantClass
) -> None:
    constants = list(constant_class.constants)
    constants.extend(
        ("_".join(groups[1:]), groups[0])
        for groups in re.findall(
            r"^\s*(" + constant_class.regex + r")\s*[=,]", drgn_h, flags=re.MULTILINE
        )
    )
    output_file.write(
        f"""
static int add_{constant_class.name}(PyObject *m, PyObject *enum_module)
{{
	PyObject *tmp, *item;
	int ret = -1;

	tmp = PyList_New({len(constants)});
	if (!tmp)
		goto out;
"""
    )
    for i, (name, value) in enumerate(constants):
        output_file.write(
            f"""\
	item = Py_BuildValue("sK", "{name}", (unsigned long long){value});
	if (!item)
		goto out;
	PyList_SET_ITEM(tmp, {i}, item);
"""
        )
    output_file.write(
        f"""\
	{constant_class.name}_class = PyObject_CallMethod(enum_module, "{constant_class.enum_class}", "sO", "{constant_class.name}", tmp);
	if (!{constant_class.name}_class)
		goto out;
	if (PyModule_AddObject(m, "{constant_class.name}", {constant_class.name}_class) == -1) {{
		Py_CLEAR({constant_class.name}_class);
		goto out;
	}}
	Py_DECREF(tmp);
	tmp = PyUnicode_FromString(drgn_{constant_class.name}_DOC);
	if (!tmp)
		goto out;
	if (PyObject_SetAttrString({constant_class.name}_class, "__doc__", tmp) == -1)
		goto out;

	ret = 0;
out:
	Py_XDECREF(tmp);
	return ret;
}}
"""
    )


def gen_constants(input_file: TextIO, output_file: TextIO) -> None:
    drgn_h = input_file.read()
    output_file.write(
        """\
/* Generated by libdrgn/build-aux/gen_constants.py. */

#include "drgnpy.h"

"""
    )
    for constant_class in CONSTANTS:
        output_file.write(f"PyObject *{constant_class.name}_class;\n")
    for constant_class in CONSTANTS:
        gen_constant_class(drgn_h, output_file, constant_class)
    output_file.write(
        """
int add_module_constants(PyObject *m)
{
	PyObject *enum_module;
	int ret;

	enum_module = PyImport_ImportModule("enum");
	if (!enum_module)
		return -1;

"""
    )
    for i, constant_class in enumerate(CONSTANTS):
        if i == 0:
            output_file.write("\tif (")
        else:
            output_file.write("\t    ")
        output_file.write(f"add_{constant_class.name}(m, enum_module) == -1")
        if i == len(CONSTANTS) - 1:
            output_file.write(")\n")
        else:
            output_file.write(" ||\n")
    output_file.write(
        """\
		ret = -1;
	else
		ret = 0;
	Py_DECREF(enum_module);
	return ret;
}
"""
    )


if __name__ == "__main__":
    gen_constants(sys.stdin, sys.stdout)
