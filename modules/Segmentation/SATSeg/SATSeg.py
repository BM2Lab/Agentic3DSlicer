"""
Module:      SATSeg
Category:    Segmentation
Description: Slicer scripted module — client for SAT (Segment Anything in 3D).
             Sends a volume to a remote SAT inference server and loads the resulting
             segmentation back into Slicer as a named, coloured segmentation node
             with automatic 3D surface rendering.
Phase:       5 — full integration with multi-label, 3D vis, persistent server config
"""

import os
import base64
import json
import tempfile
import shutil
import urllib.request
import slicer
from slicer.ScriptedLoadableModule import (
    ScriptedLoadableModule,
    ScriptedLoadableModuleWidget,
    ScriptedLoadableModuleLogic,
)
from slicer.util import VTKObservationMixin
import qt
import ctk


# ---------------------------------------------------------------------------
# Module registration
# ---------------------------------------------------------------------------

class SATSeg(ScriptedLoadableModule):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent.title = "SAT Segmentation"
        self.parent.categories = ["Segmentation"]
        self.parent.dependencies = []
        self.parent.contributors = ["Agentic3DSlicer"]
        self.parent.helpText = (
            "Universal medical image segmentation via text prompts using SAT. "
            "Connects to a remote SAT inference server (default port 1527).\n\n"
            "1. Start the server:  bash modules/Segmentation/server/start_server.sh\n"
            "2. Click 'Test Connection'\n"
            "3. Enter comma-separated anatomy labels and click 'Run SAT Segmentation'."
        )
        self.parent.acknowledgementText = (
            "SAT: https://github.com/zhaoziheng/SAT  |  "
            "Architecture inspired by SlicerNNInteractive"
        )


# ---------------------------------------------------------------------------
# Widget (UI)
# ---------------------------------------------------------------------------

_SETTINGS_KEY_URL = "SATSeg/serverURL"


class SATSegWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
    def __init__(self, parent=None):
        ScriptedLoadableModuleWidget.__init__(self, parent)
        VTKObservationMixin.__init__(self)
        self.logic = None
        self._lastSegNode = None

    def setup(self):
        super().setup()
        self.logic = SATSegLogic()
        self._buildUI()
        self._restoreSettings()

    def _buildUI(self):
        # ---- Server Connection ----
        connBox = ctk.ctkCollapsibleButton()
        connBox.text = "Server Connection"
        self.layout.addWidget(connBox)
        connLayout = qt.QFormLayout(connBox)

        self.serverURLEdit = qt.QLineEdit("http://localhost:1527")
        self.serverURLEdit.editingFinished.connect(self._saveSettings)
        connLayout.addRow("Server URL:", self.serverURLEdit)

        self.pingBtn = qt.QPushButton("Test Connection")
        self.pingBtn.clicked.connect(self._onPing)
        connLayout.addRow(self.pingBtn)

        self.connStatusLabel = qt.QLabel("Not connected")
        self.connStatusLabel.setStyleSheet("color: gray;")
        connLayout.addRow("Status:", self.connStatusLabel)

        # ---- Input ----
        inputBox = ctk.ctkCollapsibleButton()
        inputBox.text = "Input"
        self.layout.addWidget(inputBox)
        inputLayout = qt.QFormLayout(inputBox)

        self.volumeSelector = slicer.qMRMLNodeComboBox()
        self.volumeSelector.nodeTypes = ["vtkMRMLScalarVolumeNode"]
        self.volumeSelector.selectNodeUponCreation = True
        self.volumeSelector.addEnabled = False
        self.volumeSelector.removeEnabled = False
        self.volumeSelector.noneEnabled = False
        self.volumeSelector.showHidden = False
        self.volumeSelector.setMRMLScene(slicer.mrmlScene)
        inputLayout.addRow("Volume:", self.volumeSelector)

        self.promptEdit = qt.QLineEdit("liver, spleen")
        self.promptEdit.setPlaceholderText("e.g. liver, spleen, left kidney")
        inputLayout.addRow("Labels (text):", self.promptEdit)

        self.modalityCombo = qt.QComboBox()
        self.modalityCombo.addItems(["MR", "CT", "PET"])
        inputLayout.addRow("Modality:", self.modalityCombo)

        # ---- Run ----
        runBox = ctk.ctkCollapsibleButton()
        runBox.text = "Run"
        self.layout.addWidget(runBox)
        runLayout = qt.QVBoxLayout(runBox)

        self.runBtn = qt.QPushButton("Run SAT Segmentation")
        self.runBtn.setEnabled(False)
        self.runBtn.clicked.connect(self._onRun)
        runLayout.addWidget(self.runBtn)

        self.progressBar = qt.QProgressBar()
        self.progressBar.setRange(0, 0)   # indeterminate
        self.progressBar.setVisible(False)
        runLayout.addWidget(self.progressBar)

        self.statusLabel = qt.QLabel("Ready.")
        runLayout.addWidget(self.statusLabel)

        # Show 3D button (enabled after a result exists)
        self.show3DBtn = qt.QPushButton("Show 3D")
        self.show3DBtn.setEnabled(False)
        self.show3DBtn.setToolTip("Build closed-surface representation and switch to 3D view")
        self.show3DBtn.clicked.connect(self._onShow3D)
        runLayout.addWidget(self.show3DBtn)

        self.layout.addStretch(1)

    # ------------------------------------------------------------------ #
    # Settings persistence                                                 #
    # ------------------------------------------------------------------ #

    def _saveSettings(self):
        slicer.app.userSettings().setValue(_SETTINGS_KEY_URL,
                                            self.serverURLEdit.text.strip())

    def _restoreSettings(self):
        saved = slicer.app.userSettings().value(_SETTINGS_KEY_URL, "")
        if saved:
            self.serverURLEdit.setText(saved)

    # ------------------------------------------------------------------ #
    # Handlers                                                             #
    # ------------------------------------------------------------------ #

    def _onPing(self):
        url = self.serverURLEdit.text.strip()
        self._saveSettings()
        ok, msg = self.logic.pingServer(url)
        if ok:
            self.connStatusLabel.setText(f"Connected ({url})")
            self.connStatusLabel.setStyleSheet("color: green;")
            self.runBtn.setEnabled(True)
        else:
            self.connStatusLabel.setText(f"Failed: {msg}")
            self.connStatusLabel.setStyleSheet("color: red;")
            self.runBtn.setEnabled(False)

    def _onRun(self):
        volumeNode = self.volumeSelector.currentNode()
        labels = [l.strip() for l in self.promptEdit.text.split(",") if l.strip()]
        modality = self.modalityCombo.currentText
        serverURL = self.serverURLEdit.text.strip()

        if not volumeNode:
            slicer.util.errorDisplay("Please select a volume.")
            return
        if not labels:
            slicer.util.errorDisplay("Please enter at least one label.")
            return

        self.runBtn.setEnabled(False)
        self.show3DBtn.setEnabled(False)
        self.progressBar.setVisible(True)
        self._setStatus("Exporting volume…")

        try:
            self._setStatus(f"Running SAT inference for: {', '.join(labels)}…")
            segNode = self.logic.runSegmentation(
                volumeNode, labels, modality, serverURL,
                statusCallback=self._setStatus,
            )
            self._lastSegNode = segNode
            self._setStatus(
                f"Done. Segmentation '{segNode.GetName()}' "
                f"({segNode.GetSegmentation().GetNumberOfSegments()} segments)"
            )
            self.show3DBtn.setEnabled(True)
            # Auto-switch to Four-Up layout to expose the 3D view
            slicer.app.layoutManager().setLayout(
                slicer.vtkMRMLLayoutNode.SlicerLayoutFourUpView
            )
        except Exception as e:
            self._setStatus(f"Error: {e}")
            slicer.util.errorDisplay(str(e))
        finally:
            self.runBtn.setEnabled(True)
            self.progressBar.setVisible(False)

    def _onShow3D(self):
        if not self._lastSegNode:
            return
        self._setStatus("Building 3D surface…")
        slicer.app.processEvents()
        self._lastSegNode.CreateClosedSurfaceRepresentation()
        self._lastSegNode.GetDisplayNode().SetVisibility3D(True)
        # Switch to 3D-only layout
        slicer.app.layoutManager().setLayout(
            slicer.vtkMRMLLayoutNode.SlicerLayout3DView
        )
        slicer.app.layoutManager().threeDWidget(0).threeDView().resetFocalPoint()
        self._setStatus("3D view ready.")

    def _setStatus(self, msg):
        self.statusLabel.setText(msg)
        slicer.app.processEvents()

    def cleanup(self):
        self._saveSettings()
        self.removeObservers()


# ---------------------------------------------------------------------------
# Logic
# ---------------------------------------------------------------------------

class SATSegLogic(ScriptedLoadableModuleLogic):

    def pingServer(self, url):
        """Returns (True, "") or (False, error_message)."""
        try:
            with urllib.request.urlopen(f"{url}/health", timeout=5) as resp:
                return resp.status == 200, ""
        except Exception as e:
            return False, str(e)

    def runSegmentation(self, volumeNode, labels, modality, serverURL,
                        statusCallback=None):
        """
        Export volume → POST to SAT server → import mask as segmentation node.

        The combined NIfTI mask (integer labels 1..N) is imported and each
        segment is renamed to match the corresponding entry in `labels`.

        Returns the new vtkMRMLSegmentationNode.
        Raises RuntimeError on any failure.
        """
        def _status(msg):
            if statusCallback:
                statusCallback(msg)

        tmpdir = tempfile.mkdtemp(prefix="satseg_slicer_")
        try:
            # 1. Export volume to NIfTI
            _status("Exporting volume to NIfTI…")
            nifti_path = os.path.join(tmpdir, "volume.nii.gz")
            slicer.util.saveNode(volumeNode, nifti_path)

            # 2. Base64-encode
            with open(nifti_path, "rb") as f:
                volume_b64 = base64.b64encode(f.read()).decode("utf-8")

            # 3. POST to server
            _status(f"Sending to SAT server ({serverURL})…")
            payload = json.dumps({
                "volume_nifti": volume_b64,
                "labels":       labels,
                "modality":     modality.lower(),
            }).encode("utf-8")

            req = urllib.request.Request(
                f"{serverURL}/segment",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            try:
                with urllib.request.urlopen(req, timeout=300) as resp:
                    result = json.loads(resp.read())
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"Server returned HTTP {e.code}: {body}")

            if result.get("status") != "ok":
                raise RuntimeError(result.get("message", "Unknown server error"))

            # 4. Decode mask NIfTI
            _status("Decoding segmentation mask…")
            mask_path = os.path.join(tmpdir, "mask.nii.gz")
            with open(mask_path, "wb") as f:
                f.write(base64.b64decode(result["mask_nifti"]))

            # 5. Load as temporary labelmap
            labelmapNode = slicer.util.loadLabelVolume(mask_path)

            # 6. Create segmentation node and import labelmap
            _status("Importing labelmap as segmentation…")
            segNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode")
            segNode.SetName(f"{volumeNode.GetName()}_SAT")
            segNode.SetReferenceImageGeometryParameterFromVolumeNode(volumeNode)

            slicer.modules.segmentations.logic().ImportLabelmapToSegmentationNode(
                labelmapNode, segNode
            )
            slicer.mrmlScene.RemoveNode(labelmapNode)

            # 7. Rename segments to match input labels
            seg = segNode.GetSegmentation()
            for i, name in enumerate(labels):
                if i < seg.GetNumberOfSegments():
                    seg.GetNthSegment(i).SetName(name)

            # 8. Show in slice views
            slicer.util.setSliceViewerLayers(label=None)  # clear old label layer
            segNode.GetDisplayNode().SetVisibility(True)

            return segNode

        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
