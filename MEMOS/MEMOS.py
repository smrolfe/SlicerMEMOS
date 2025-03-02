import os
import unittest
import logging
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin

import logging
import os
import sys
import tempfile
import shutil
import time
from glob import glob
from packaging import version

#
# MEMOS
#
class MEMOS(ScriptedLoadableModule):
    """Uses ScriptedLoadableModule base class, available at:
      https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
      """

    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        self.parent.title = "MEMOS"  # TODO make this more human readable by adding spaces
        self.parent.categories = ["MEMOS"]
        self.parent.dependencies = []
        self.parent.contributors = [
            "Sara Rolfe (SCRI), Murat Maga (SCRI, UW)"]  # replace with "Firstname Lastname (Organization)"
        self.parent.helpText = """
      This model loads a PyTorch Deep Learning model and does inference on an 3D diceCT scan of a mouse fetus loaded in the scene. For more information, please see online documentation: https://github.com/SlicerMorph/SlicerMEMOS#readme 
      """
        self.parent.acknowledgementText = """
      This module was developed by Sara Rolfe and was supported by grants (OD032627 and HD104435) awarded to Murat Maga from National Institutes of Health."
      """  # replace with organization, grant and thanks.

class MEMOSWidget(ScriptedLoadableModuleWidget):
    """Uses ScriptedLoadableModuleWidget base class, available at:
      https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
      """
    def setup(self):
        ScriptedLoadableModuleWidget.setup(self)
        # Set up tabs to split workflow
        tabsWidget = qt.QTabWidget()
        singleTab = qt.QWidget()
        singleTabLayout = qt.QFormLayout(singleTab)
        batchTab = qt.QWidget()
        batchTabLayout = qt.QFormLayout(batchTab)
        tabsWidget.addTab(singleTab, "Single volume")
        tabsWidget.addTab(batchTab, "Batch mode")
        self.layout.addWidget(tabsWidget)

        ################################### Single Tab ###################################
        # Instantiate and connect widgets
        #
        # Segmentation Set-up Area
        #
        singleParametersCollapsibleButton = ctk.ctkCollapsibleButton()
        singleParametersCollapsibleButton.text = "Segmentation Set-up"
        singleTabLayout.addRow(singleParametersCollapsibleButton)

        # Layout within the dummy collapsible button
        singleParametersFormLayout = qt.QFormLayout(singleParametersCollapsibleButton)

        #
        # Select base mesh
        #
        self.volumeSelector = slicer.qMRMLNodeComboBox()
        self.volumeSelector.nodeTypes = ( ("vtkMRMLVolumeNode"), "" )
        self.volumeSelector.selectNodeUponCreation = False
        self.volumeSelector.addEnabled = False
        self.volumeSelector.removeEnabled = False
        self.volumeSelector.noneEnabled = True
        self.volumeSelector.showHidden = False
        self.volumeSelector.setMRMLScene( slicer.mrmlScene )
        singleParametersFormLayout.addRow("Volume: ", self.volumeSelector)

        #
        # Select model file
        #
        self.modelPathSingle = ctk.ctkPathLineEdit()
        self.modelPathSingle.currentPath = self.getMEMOSModelPath()
        self.modelPathSingle.filters = ctk.ctkPathLineEdit.Files
        self.modelPathSingle.nameFilters= ["Model (*.pth)"]
        self.modelPathSingle.setToolTip("Select the segmentation model")
        singleParametersFormLayout.addRow("Segmentation model: ", self.modelPathSingle)

        #
        # Apply Single Button
        #
        self.applySingleButton = qt.QPushButton("Apply")
        self.applySingleButton.toolTip = "Generate MEMOS segmentation for loaded volume"
        self.applySingleButton.enabled = False
        singleParametersFormLayout.addRow(self.applySingleButton)

        #
        # Evaluation Area
        #
        singleEvaluationCollapsibleButton = ctk.ctkCollapsibleButton()
        singleEvaluationCollapsibleButton.text = "Evaluate Segmentation"

        #
        # Select MEMOS segmentation
        #
        self.MEMOSSelector = slicer.qMRMLNodeComboBox()
        self.MEMOSSelector.nodeTypes = ( ("vtkMRMLSegmentationNode"), "" )
        self.MEMOSSelector.selectNodeUponCreation = False
        self.MEMOSSelector.addEnabled = False
        self.MEMOSSelector.removeEnabled = False
        self.MEMOSSelector.noneEnabled = True
        self.MEMOSSelector.showHidden = False
        self.MEMOSSelector.setMRMLScene( slicer.mrmlScene )

        #
        # Select Reference segmentation
        #
        self.referenceSelector = slicer.qMRMLNodeComboBox()
        self.referenceSelector.nodeTypes = ( ("vtkMRMLSegmentationNode"), "" )
        self.referenceSelector.selectNodeUponCreation = False
        self.referenceSelector.addEnabled = False
        self.referenceSelector.removeEnabled = False
        self.referenceSelector.noneEnabled = True
        self.referenceSelector.showHidden = False
        self.referenceSelector.setMRMLScene( slicer.mrmlScene )

        #
        # Apply Evaluation Button
        #
        self.evaluateSegmentationButton = qt.QPushButton("Compare Segmentations")
        self.evaluateSegmentationButton.toolTip = "Compare MEMOS segmentation to a reference"
        self.evaluateSegmentationButton.enabled = False

        # Connections
        self.volumeSelector.connect('currentNodeChanged(vtkMRMLNode*)', self.onSelectSingle)
        self.modelPathSingle.connect('currentPathChanged(const QString &)', self.onSelectSingleModelPath)
        self.applySingleButton.connect('clicked(bool)', self.onApplySingleButton)
        self.MEMOSSelector.connect('currentNodeChanged(vtkMRMLNode*)', self.onSelectSingleEval)
        self.referenceSelector.connect('currentNodeChanged(vtkMRMLNode*)', self.onSelectSingleEval)

        ################################### Batch Tab ###################################
        # Instantiate and connect widgets
        #
        # Segmentation Set-up Area
        #
        parametersCollapsibleButton = ctk.ctkCollapsibleButton()
        parametersCollapsibleButton.text = "Segmentation Set-up"
        batchTabLayout.addRow(parametersCollapsibleButton)

        # Layout within the dummy collapsible button
        parametersFormLayout = qt.QFormLayout(parametersCollapsibleButton)

        #
        # Select volume directory
        #
        self.volumePath = ctk.ctkPathLineEdit()
        self.volumePath.filters = ctk.ctkPathLineEdit.Dirs
        self.volumePath.setToolTip("Select the volume directory")
        parametersFormLayout.addRow("Volume directory: ", self.volumePath)

        #
        # Select model file
        #
        self.modelPath = ctk.ctkPathLineEdit()
        self.modelPath.currentPath = self.getMEMOSModelPath()
        self.modelPath.filters = ctk.ctkPathLineEdit.Files
        self.modelPath.nameFilters= ["Model (*.pth)"]
        self.modelPath.setToolTip("Select the segmentation model")
        parametersFormLayout.addRow("Segmentation model: ", self.modelPath)

        #
        # Select volume directory
        #
        self.outputPath = ctk.ctkPathLineEdit()
        self.outputPath.filters = ctk.ctkPathLineEdit.Dirs
        self.outputPath.setToolTip("Select the output directory")
        parametersFormLayout.addRow("Output directory: ", self.outputPath)

        #
        # Apply Button
        #
        self.applyButton = qt.QPushButton("Apply")
        self.applyButton.toolTip = "Generate MEMOS segmentation for each volume in directory."
        self.applyButton.enabled = False
        parametersFormLayout.addRow(self.applyButton)

        # connections
        self.volumePath.connect('currentPathChanged(const QString &)', self.onSelect)
        self.modelPath.connect('currentPathChanged(const QString &)', self.onSelectModelPath)
        self.outputPath.connect('currentPathChanged(const QString &)', self.onSelect)
        self.applyButton.connect('clicked(bool)', self.onApplyButton)

        # Add vertical spacer
        self.layout.addStretch(1)

    def onSelectSingle(self):
        self.applySingleButton.enabled = bool(self.volumeSelector.currentNode() and self.modelPathSingle.currentPath)

    def onSelectSingleModelPath(self):
        self.saveMEMOSModelPath(self.modelPathSingle.currentPath)
        self.modelPath.currentPath = self.getMEMOSModelPath()
        self.applySingleButton.enabled = bool(self.volumeSelector.currentNode() and self.modelPathSingle.currentPath)

    def onSelectSingleEval(self):
        self.evaluateSegmentationButton.enabled = bool(self.MEMOSSelector.currentNode() and self.referenceSelector.currentNode())

    def onSelect(self):
        self.applyButton.enabled = bool(self.modelPath.currentPath and self.volumePath.currentPath and self.outputPath.currentPath)

    def onSelectModelPath(self):
        self.saveMEMOSModelPath(self.modelPathSingle.currentPath)
        self.modelPathSingle.currentPath = self.getMEMOSModelPath()
        self.applyButton.enabled = bool(self.modelPath.currentPath and self.volumePath.currentPath and self.outputPath.currentPath)

    def onApplyButton(self):
        logic = MEMOSLogic()
        logic.setupPythonRequirements()
        self.setColorTable()
        logic.runBatch(self.volumePath.currentPath, self.modelPath.currentPath, self.outputPath.currentPath, self.colorNode)

    def onApplySingleButton(self):
        logic = MEMOSLogic()
        logic.setupPythonRequirements()
        start = time.time()
        self.setColorTable()
        tempVolumePath = os.path.join(slicer.app.temporaryPath, 'tempMEMOSVolume')
        if os.path.isdir(tempVolumePath):
          shutil.rmtree(tempVolumePath)
        os.mkdir(tempVolumePath)
        volumeNode = self.volumeSelector.currentNode()
        
        # temporarily reset the spacing and origin
        originalSpacing = volumeNode.GetSpacing()
        originalOrigin = volumeNode.GetOrigin()
        volumeNode.SetSpacing((1,1,1))
        volumeNode.SetOrigin(0,0,0)
        
        tempVolumeFile = os.path.join(tempVolumePath, volumeNode.GetName() +'.nii.gz')
        slicer.util.saveNode(volumeNode, tempVolumeFile)
        tempOutputPath = os.path.join(slicer.app.temporaryPath,'tempMEMOSOut')
        if os.path.isdir(tempOutputPath):
          shutil.rmtree(tempOutputPath)
        os.mkdir(tempOutputPath)
        logic.runSingle(tempVolumeFile, self.modelPathSingle.currentPath, tempOutputPath)
        if len(os.listdir(tempOutputPath))>0:
          labelFile = os.path.join(tempOutputPath,os.listdir(tempOutputPath)[0])
          labelNode = slicer.util.loadLabelVolume(labelFile)
          labelNode.GetDisplayNode().SetAndObserveColorNodeID(self.colorNode.GetID())
         
          # reset the spacing and origin to original values
          volumeNode.SetSpacing(originalSpacing)
          labelNode.SetSpacing(originalSpacing)
          volumeNode.SetOrigin(originalOrigin)
          labelNode.SetOrigin(originalOrigin)
                    
          segmentationNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode")
          slicer.modules.segmentations.logic().ImportLabelmapToSegmentationNode(labelNode, segmentationNode)
          segmentationNode.CreateClosedSurfaceRepresentation()
          shNode = slicer.mrmlScene.GetSubjectHierarchyNode()
          volID = shNode.GetItemByDataNode(volumeNode)
          segID = shNode.GetItemByDataNode(segmentationNode)
          shNode.SetItemParent(segID,volID)
          self.MEMOSSelector.setCurrentNode(segmentationNode)
          end = time.time()
          print("MEMOS Inference time: ", end - start)
        else:
          print("No segmentation was saved to the temporary folder")
        slicer.mrmlScene.RemoveNode(labelNode)
        shutil.rmtree(tempVolumePath)
        shutil.rmtree(tempOutputPath)

#    def onEvaluateSegmentationButton(self):
#      logic = MEMOSLogic()
#      logic.getDiceTable(self.referenceSelector.currentNode(), self.MEMOSSelector.currentNode())

    def setColorTable(self):
      if hasattr(self, 'colorNode'):
        try:
          slicer.util.getNode(self.colorNode)
          return
        except:
          print("Color node is not in the scene, reloading from file")
          self.colorNode = None
      # Load color table
      colorNodePath = self.resourcePath("Support/KOMP2.ctbl")
      try:
        self.colorNode = slicer.util.loadColorTable(colorNodePath)
      except:
        print("Error loading color node from: ", colorNodePath)
        self.colorNode = None

    def downloadMEMOSModel(self):
      # if no valid model path, try to download
      import SampleData
      filename = "best_metric_model_largePatch_noise.pth"
      link = "https://app.box.com/shared/static/4nygg33o70oj5xvnhew11zz5geclus5b.pth"
      progressDialog = slicer.util.createProgressDialog(
                labelText="Downloading the MEMOS segmentation model. This may take a minute.",
                maximum=0,
            )
      slicer.app.processEvents()
      SampleData.SampleDataLogic().downloadFileIntoCache(link, filename)
      progressDialog.close()
      modelPath = os.path.join(slicer.app.cachePath, filename)
      if self.isValidMEMOSModelPath(modelPath):
        self.saveMEMOSModelPath(modelPath)
        return modelPath
      else:
        slicer.util.infoDisplay("Error downloading MEMOS segmentation model. Please download manually following the instructions on the module help page.")
        return ""

    def saveMEMOSModelPath(self, modelPath):
      # don't save if identical to saved
      settings = qt.QSettings()
      if settings.contains('Developer/MEMOSModelPath'):
        modelPathSaved = settings.value('Developer/MEMOSModelPath')
        if modelPathSaved == modelPath:
          return
      if not self.isValidMEMOSModelPath(modelPath):
        return
      settings.setValue('Developer/MEMOSModelPath', modelPath)

    def getMEMOSModelPath(self):
      # If path is defined in settings then use that
      settings = qt.QSettings()
      if settings.contains('Developer/MEMOSModelPath'):
        modelPath = settings.value('Developer/MEMOSModelPath')
        if self.isValidMEMOSModelPath(modelPath):
          return modelPath
      modelPath = self.downloadMEMOSModel()
      return modelPath

    def isValidMEMOSModelPath(self, modelPath):
      if os.path.exists(modelPath):
        return True
      else:
        print("MEMOS model path invalid: No model found")
        return False

#
# MEMOSLogic
#

class MEMOSLogic(ScriptedLoadableModuleLogic):
    """This class should implement all the actual
      computation done by your module.  The interface
      should be such that other python code can import
      this class and make use of the functionality without
      requiring an instance of the Widget.
      Uses ScriptedLoadableModuleLogic base class, available at:
      https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
      """
    def setupPythonRequirements(self):
      print("Checking python dependencies")
      # Install PyTorch
      try:
        import PyTorchUtils
      except ModuleNotFoundError:
        slicer.util.messageBox("MEMOS requires the PyTorch extension. Please install it from the Extensions Manager.")
      torchLogic = PyTorchUtils.PyTorchUtilsLogic()
      if not torchLogic.torchInstalled():
        logging.debug('MEMOS requires the PyTorch Python package. Installing... (it may take several minutes)')
        torch = torchLogic.installTorch(askConfirmation=True)
        if torch is None:
          slicer.util.messageBox('PyTorch extension needs to be installed manually to use this module.')
    
      # Install additional python packages
      try:
        import pillow
      except:
        logging.debug('Pillow Python package is required. Installing...')
        slicer.util.pip_install('pillow')
      try:
        import nibabel
      except:
        logging.debug('Nibabel Python package is required. Installing...')
        slicer.util.pip_install('nibabel')
      try:
        import einops
      except:
        logging.debug('Einops Python package is required. Installing...')
        slicer.util.pip_install('einops')
      
      # Install MONAI and restart if the version was updated.
      monaiVersion = "0.9.0"
      try:
        import monai
        if version.parse(monai.__version__) != version.parse(monaiVersion):
          logging.debug(f'MEMOS requires MONAI version {monaiVersion}. Installing... (it may take several minutes)')
          slicer.util.pip_uninstall('monai')
          slicer.util.pip_install('monai[pynrrd]=='+ monaiVersion)
          if slicer.util.confirmOkCancelDisplay(f'MONAI version was updated {monaiVersion}.\n Click OK restart Slicer.'):
            slicer.util.restart()
      except:
        logging.debug('MEMOS requires installation of the MONAI Python package. Installing... (it may take several minutes)')
        slicer.util.pip_install('monai[pynrrd]=='+ monaiVersion)
        
    def runSingle(self, imagePath, modelPath, outputPath):
        # import MONAI and dependencies
        import nibabel as nib
        import numpy as np
        import torch
        import einops

        from monai.config import print_config
        from monai.data import Dataset, DataLoader, create_test_image_3d, decollate_batch
        from monai.inferers import sliding_window_inference
        from monai.networks.nets import UNETR
        from monai.data.nifti_writer import write_nifti

        from monai.transforms import (
          Activationsd,
          AsDiscreted,
          AddChanneld,
          Compose,
          EnsureChannelFirstd,
          Invertd,
          LoadImaged,
          Orientationd,
          SaveImaged,
          Spacingd,
          CropForegroundd,
          EnsureTyped,
          ScaleIntensityRanged,
          ToTensord
        )
        # define pre-transforms
        pre_transforms = Compose([
            LoadImaged(keys=["image"]),
            EnsureChannelFirstd(keys=["image"]),
            Orientationd(keys="image", axcodes="RAS"),
            ScaleIntensityRanged(
                keys=["image"], a_min=-175, a_max=250,
                b_min=0.0, b_max=1.0, clip=True),
            CropForegroundd(keys=["image"], source_key="image"),
            AddChanneld(keys=["image"]),
            ToTensord(keys=["image"]),
        ])

        # get volume
        filepath = {"image": imagePath}

        # set up model
        os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"

        # set GPU
        if torch.cuda.is_available():
          os.environ["CUDA_VISIBLE_DEVICES"]="0"
          print("Using device: ", os.environ["CUDA_VISIBLE_DEVICES"])
        # check configuration
        print_config()
        torch.set_num_threads(24)
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print("Using device: ", device)
        image_dim = 128

        net = UNETR(
            in_channels=1,
            out_channels=51,
            img_size=(image_dim, image_dim, image_dim),
            feature_size=16,
            hidden_size=768,
            mlp_dim=3072,
            num_heads=12,
            pos_embed="perceptron",
            norm_name="instance",
            res_block=True,
            dropout_rate=0.0,
        ).to(device)

        if device.type == "cpu":
            net.load_state_dict(torch.load(modelPath, map_location='cpu'))
        else:
            net.load_state_dict(torch.load(modelPath))
        net.eval()

        with torch.no_grad():
          image = pre_transforms(filepath)['image'].to(device)
          output_raw = sliding_window_inference(
            image, (image_dim, image_dim, image_dim), 4, net, overlap=0.8)
          output_formatted = torch.argmax(output_raw, dim=1).detach().cpu()[0, :, :, :]
          outputFile = os.path.basename(filepath.get("image").split('.')[0]) + "_seg.nii.gz"
          print("Writing: ", outputFile)
          write_nifti(
            data=output_formatted,
            file_name=os.path.join(outputPath, outputFile)
              )

    def runBatch(self, volumePath, modelPath, outputPath, colorNode):
        # import MONAI and dependencies
        import nibabel as nib
        import numpy as np
        import torch
        import einops

        from monai.config import print_config
        from monai.data import Dataset, DataLoader, create_test_image_3d, decollate_batch
        from monai.inferers import sliding_window_inference
        from monai.networks.nets import UNETR
        from monai.data.nifti_writer import write_nifti

        from monai.transforms import (
          Activationsd,
          AsDiscreted,
          AddChanneld,
          Compose,
          EnsureChannelFirstd,
          Invertd,
          LoadImaged,
          Orientationd,
          SaveImaged,
          Spacingd,
          CropForegroundd,
          EnsureTyped,
          ScaleIntensityRanged,
          ToTensord
        )
        # define pre-transforms
        pre_transforms = Compose([
            LoadImaged(keys=["image"]),
            EnsureChannelFirstd(keys=["image"]),
            Orientationd(keys="image", axcodes="RAS"),
            ScaleIntensityRanged(
                keys=["image"], a_min=-175, a_max=250,
                b_min=0.0, b_max=1.0, clip=True),
            AddChanneld(keys=["image"]),
            ToTensord(keys=["image"]),
        ])

        # get volumes in directory
        images = []
        volumeExtensions = ['nrrd', 'nii.gz']
        for root, dirnames, imageNames in os.walk(volumePath):
          for imageName in imageNames:
            imName, imExt = imageName.split(os.extsep,1)
            if any( ext in imExt for ext in volumeExtensions):
              images.append(os.path.join(root, imageName))
        files = [{"image": image} for image in images]

        # set up model
        os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"

        # set GPU
        if torch.cuda.is_available():
          os.environ["CUDA_VISIBLE_DEVICES"]="0"
          print("Using device: ", os.environ["CUDA_VISIBLE_DEVICES"])
        # check configuration
        print_config()
        torch.set_num_threads(24)
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print("Using device: ", device)
        image_dim = 128

        net = UNETR(
            in_channels=1,
            out_channels=51,
            img_size=(image_dim, image_dim, image_dim),
            feature_size=16,
            hidden_size=768,
            mlp_dim=3072,
            num_heads=12,
            pos_embed="perceptron",
            norm_name="instance",
            res_block=True,
            dropout_rate=0.0,
        ).to(device)

        if device.type == "cpu":
            net.load_state_dict(torch.load(modelPath, map_location='cpu'))
        else:
            net.load_state_dict(torch.load(modelPath))
        net.eval()

        with torch.no_grad():
          for filepath in files:
            start=time.time()
            image = pre_transforms(filepath)['image'].to(device)
            output_raw = sliding_window_inference(image, (image_dim, image_dim, image_dim), 4, net, overlap=0.8)
            output_final= torch.argmax(output_raw, dim=1).detach().cpu()[0, :, :, :]
            outputName = os.path.basename(filepath.get("image").split('.')[0])
            outputLabelPath = os.path.join(outputPath, outputName + "_seg.nii.gz")
            outputSegPath = os.path.join(outputPath, outputName + ".seg.nrrd")
            print("Writing: ", outputLabelPath)
            write_nifti(
              data=output_final,
              file_name=outputLabelPath
              )
            labelNode = slicer.util.loadLabelVolume(outputLabelPath)
            labelNode.GetDisplayNode().SetAndObserveColorNodeID(colorNode.GetID())
            volumeNode = slicer.util.loadVolume(filepath['image'])
            originalSpacing = volumeNode.GetSpacing()
            originalOrigin = volumeNode.GetOrigin()
            labelNode.SetSpacing(originalSpacing)
            labelNode.SetOrigin(originalOrigin)             
            segmentationNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode")
            slicer.modules.segmentations.logic().ImportLabelmapToSegmentationNode(labelNode, segmentationNode)
            slicer.util.saveNode(segmentationNode, outputSegPath)
            slicer.mrmlScene.RemoveNode(labelNode)
            slicer.mrmlScene.RemoveNode(segmentationNode)
            slicer.mrmlScene.RemoveNode(volumeNode)
            os.remove(outputLabelPath)
            end = time.time()
            print("MEMOS Inference time: ", end - start)

#    def getDiceTable(self, refSeg, predictedSeg):
#      pnode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentComparisonNode")
#      pnode.SetAndObserveReferenceSegmentationNode(refSeg)
#      pnode.SetAndObserveCompareSegmentationNode(predictedSeg)
#      dtab = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLTableNode")
#      fullTable = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLTableNode")
#      fullTable.SetName(refSeg.GetName())
#      fullTable.SetUseFirstColumnAsRowHeader(False)
#      header = fullTable.AddColumn()
#      header.SetName("Metric name")
#      header.InsertNextValue("Reference segmentation")
#      header.InsertNextValue("Reference segment")
#      header.InsertNextValue("Compare segmentation")
#      header.InsertNextValue("Compare segment")
#      header.InsertNextValue("Dice coefficient")
#      header.InsertNextValue("True positives (%)")
#      header.InsertNextValue("True negatives (%)")
#      header.InsertNextValue("False positives (%)")
#      header.InsertNextValue("False negatives (%)")
#      header.InsertNextValue("Reference center")
#      header.InsertNextValue("Compare center")
#      header.InsertNextValue("Reference volume (cc)")
#      header.InsertNextValue("Compare volume (cc)")
#      fullTable.Modified()
#      for index in range(0,refSeg.GetSegmentation().GetNumberOfSegments()):
#        pnode.SetAndObserveDiceTableNode(dtab)
#        pnode.SetReferenceSegmentID(refSeg.GetSegmentation().GetNthSegmentID(index))
#        pnode.SetCompareSegmentID(predictedSeg.GetSegmentation().GetNthSegmentID(index))
#        success = slicer.modules.segmentcomparison.logic().ComputeDiceStatistics(pnode)
#        col = dtab.GetTable().GetColumn(1)
#        col.SetName(predictedSeg.GetSegmentation().GetNthSegmentID(index+1))
#        fullTable.AddColumn(col)
#      flipper = vtk.vtkTransposeTable()
#      flipper.SetInputData(fullTable.GetTable())
#      flipper.Update()
#      fullTable.SetAndObserveTable(flipper.GetOutput())
#      fullTable.RemoveColumn(0)
#      fullTable.RemoveColumn(0)
#      fullTable.RemoveColumn(0)
#      fullTable.RemoveColumn(0)
#      fullTable.SetUseFirstColumnAsRowHeader(True)
#      fullTable.SetUseColumnNameAsColumnHeader(True)
#      slicer.mrmlScene.RemoveNode(dtab)

class MEMOSTest(ScriptedLoadableModuleTest):
    """
      This is the test case for your scripted module.
      Uses ScriptedLoadableModuleTest base class, available at:
      https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
      """

    def runTest(self):
        """Run as few or as many tests as needed here.
          """
        self.setUp()
        self.test_MEMOS1()

    def test_MEMOS1(self):
        """ Ideally you should have several levels of tests.  At the lowest level
          tests should exercise the functionality of the logic with different inputs
          (both valid and invalid).  At higher levels your tests should emulate the
          way the user would interact with your code and confirm that it still works
          the way you intended.
          One of the most important features of the tests is that it should alert other
          developers when their changes will have an impact on the behavior of your
          module.  For example, if a developer removes a feature that you depend on,
          your test should break so they know that the feature is needed.
          """

        self.delayDisplay("Starting the test")
        #
        # first, get some data
        #
        import urllib
        downloads = (
            ('http://slicer.kitware.com/midas3/download?items=5767', 'FA.nrrd', slicer.util.loadVolume),
        )
        for url, name, loader in downloads:
            filePath = slicer.app.temporaryPath + '/' + name
            if not os.path.exists(filePath) or os.stat(filePath).st_size == 0:
                logging.info(f'Requesting download {name} from {url}...\n')
                urllib.urlretrieve(url, filePath)
            if loader:
                logging.info(f'Loading {name}...')
                loader(filePath)
        self.delayDisplay('Finished with download and loading')

        volumeNode = slicer.util.getNode(pattern="FA")
        logic = MEMOSLogic()
        self.assertIsNotNone(logic.hasImageData(volumeNode))
        self.delayDisplay('Test passed!')
