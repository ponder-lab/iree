# Copyright 2019 The IREE Authors
#
# Licensed under the Apache License v2.0 with LLVM Exceptions.
# See https://llvm.org/LICENSE.txt for license information.
# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

# pylint: disable=unused-variable

import logging
import os
import re
import tempfile
import unittest

import iree.compiler
import iree.runtime
import numpy as np


def create_simple_mul_module():
  binary = iree.compiler.compile_str(
      """
      module @arithmetic {
        func.func @simple_mul(%arg0: tensor<4xf32>, %arg1: tensor<4xf32>) -> tensor<4xf32> {
          %0 = arith.mulf %arg0, %arg1 : tensor<4xf32>
          return %0 : tensor<4xf32>
        }
      }
      """,
      target_backends=iree.compiler.core.DEFAULT_TESTING_BACKENDS,
  )
  m = iree.runtime.VmModule.from_flatbuffer(binary)
  return m


class SystemApiTest(unittest.TestCase):

  def test_non_existing_driver(self):
    with self.assertRaisesRegex(ValueError, "No device found from list"):
      config = iree.runtime.Config("nothere1,nothere2")

  def test_subsequent_driver(self):
    config = iree.runtime.Config("nothere1,local-task")

  def test_multi_config_caches(self):
    config1 = iree.runtime.Config("nothere1,local-sync")
    config2 = iree.runtime.Config("nothere1,local-sync")
    self.assertIs(config1.device, config2.device)

  def test_empty_dynamic(self):
    ctx = iree.runtime.SystemContext()
    self.assertTrue(ctx.is_dynamic)
    self.assertIn("hal", ctx.modules)
    self.assertEqual(ctx.modules.hal.name, "hal")

  def test_empty_static(self):
    ctx = iree.runtime.SystemContext(vm_modules=())
    self.assertFalse(ctx.is_dynamic)
    self.assertIn("hal", ctx.modules)
    self.assertEqual(ctx.modules.hal.name, "hal")

  def test_custom_dynamic(self):
    ctx = iree.runtime.SystemContext()
    self.assertTrue(ctx.is_dynamic)
    ctx.add_vm_module(create_simple_mul_module())
    self.assertEqual(ctx.modules.arithmetic.name, "arithmetic")
    f = ctx.modules.arithmetic["simple_mul"]
    f_repr = repr(f)
    logging.info("f_repr: %s", f_repr)
    self.assertEqual(f_repr, "<VmFunction simple_mul(0rr_r), reflection = {}>")

  def test_duplicate_module(self):
    ctx = iree.runtime.SystemContext()
    self.assertTrue(ctx.is_dynamic)
    ctx.add_vm_module(create_simple_mul_module())
    with self.assertRaisesRegex(ValueError, "arithmetic"):
      ctx.add_vm_module(create_simple_mul_module())

  def test_static_invoke(self):
    ctx = iree.runtime.SystemContext()
    self.assertTrue(ctx.is_dynamic)
    ctx.add_vm_module(create_simple_mul_module())
    self.assertEqual(ctx.modules.arithmetic.name, "arithmetic")
    f = ctx.modules.arithmetic["simple_mul"]
    arg0 = np.array([1., 2., 3., 4.], dtype=np.float32)
    arg1 = np.array([4., 5., 6., 7.], dtype=np.float32)
    results = f(arg0, arg1)
    np.testing.assert_allclose(results, [4., 10., 18., 28.])

  def test_chained_invoke(self):
    # This ensures that everything works if DeviceArrays are returned
    # and input to functions.
    ctx = iree.runtime.SystemContext()
    self.assertTrue(ctx.is_dynamic)
    ctx.add_vm_module(create_simple_mul_module())
    self.assertEqual(ctx.modules.arithmetic.name, "arithmetic")
    f = ctx.modules.arithmetic["simple_mul"]
    arg0 = np.array([1., 2., 3., 4.], dtype=np.float32)
    arg1 = np.array([4., 5., 6., 7.], dtype=np.float32)
    results = f(arg0, arg1)
    results2 = f(results, results)
    np.testing.assert_allclose(results2, [16., 100., 324., 784.])

  def test_tracing_explicit(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      tracer = iree.runtime.Tracer(temp_dir)
      config = iree.runtime.Config("local-task", tracer=tracer)
      self.verify_tracing(config, temp_dir)

  def test_tracing_from_environment(self):
    original = os.environ.get(iree.runtime.TRACE_PATH_ENV_KEY)
    try:
      with tempfile.TemporaryDirectory() as temp_dir:
        os.environ[iree.runtime.TRACE_PATH_ENV_KEY] = temp_dir
        config = iree.runtime.Config("local-task")
        self.verify_tracing(config, temp_dir)
    finally:
      if original:
        os.environ[iree.runtime.TRACE_PATH_ENV_KEY] = original

  def verify_tracing(self, config, temp_dir):
    logging.info("Tracing test to: %s", temp_dir)
    ctx = iree.runtime.SystemContext(config=config)
    ctx.add_vm_module(create_simple_mul_module())
    f = ctx.modules.arithmetic["simple_mul"]
    arg0 = np.array([1., 2., 3., 4.], dtype=np.float32)
    arg1 = np.array([4., 5., 6., 7.], dtype=np.float32)
    results = f(arg0, arg1)
    self.assertTrue(os.path.exists(os.path.join(temp_dir, "arithmetic.vmfb")))
    self.assertTrue(os.path.exists(os.path.join(temp_dir, "calls.yaml")))
    # TODO: Once replay is possible, verify that.

  def test_load_vm_module(self):
    arithmetic = iree.runtime.load_vm_module(create_simple_mul_module())
    arg0 = np.array([1., 2., 3., 4.], dtype=np.float32)
    arg1 = np.array([4., 5., 6., 7.], dtype=np.float32)
    results = arithmetic.simple_mul(arg0, arg1)
    print("SIMPLE_MUL RESULTS:", results)
    np.testing.assert_allclose(results, [4., 10., 18., 28.])

  def test_load_multiple_modules(self):
    # Doing default device configuration multiple times should be valid
    # (if this were instantiating drivers multiple times, it can trigger
    # a crash, depending on whether the driver supports multi-instantiation).
    m = create_simple_mul_module()
    m1 = iree.runtime.load_vm_module(m)
    m2 = iree.runtime.load_vm_module(m)


if __name__ == "__main__":
  logging.basicConfig(level=logging.DEBUG)
  unittest.main()
