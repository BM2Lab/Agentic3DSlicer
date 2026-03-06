"""
Module:      SATSegTest
Category:    Segmentation / Testing
Description: Basic self-test for the SATSeg scripted module.
             Verifies the module loads and the widget instantiates without errors.
"""

import unittest
import slicer


class SATSegTest(unittest.TestCase):

    def setUp(self):
        slicer.mrmlScene.Clear(0)

    def test_module_loads(self):
        """Module should be accessible via slicer.modules.satseg."""
        self.assertTrue(hasattr(slicer.modules, "satseg"),
                        "satseg module not found in slicer.modules")

    def test_widget_instantiates(self):
        """Switching to the module should not raise."""
        try:
            slicer.util.selectModule("SATSeg")
        except Exception as e:
            self.fail(f"selectModule('SATSeg') raised: {e}")

    def tearDown(self):
        slicer.mrmlScene.Clear(0)
