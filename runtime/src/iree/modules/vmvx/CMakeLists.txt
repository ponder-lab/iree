# Copyright 2022 The IREE Authors
#
# Licensed under the Apache License v2.0 with LLVM Exceptions.
# See https://llvm.org/LICENSE.txt for license information.
# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

set(_VMVX_OPTIONAL_COPTS)
set(_VMVX_OPTIONAL_DEPS)

if(IREE_BUILD_EXPERIMENTAL_VMVX_MMT4D)
  list(APPEND _VMVX_OPTIONAL_DEPS iree::builtins::mmt4d)
endif()

iree_cc_library(
  NAME
    vmvx
  COPTS
    ${_VMVX_OPTIONAL_COPTS}
  HDRS
    "module.h"
  TEXTUAL_HDRS
    "exports.inl"
  SRCS
    "module.c"
  DEPS
    iree::base
    iree::base::tracing
    iree::vm
    ${_VMVX_OPTIONAL_DEPS}
  PUBLIC
)
