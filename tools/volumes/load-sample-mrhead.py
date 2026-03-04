"""
Tool:        load-sample-mrhead.py
Category:    volumes
Tags:        volume, load, sample, MRHead, SampleData, scalar volume, demo
Description: Download and load the MRHead sample volume from Slicer's built-in SampleData module
Usage:       Run inside Slicer's Python environment (headless or GUI)
             import SampleData; exec(open('load-sample-mrhead.py').read())
Version:     1.0
Verified:    2026-03-04  (Slicer 5.10.0, dims=256x256x130)
"""
import SampleData

volumeNode = SampleData.SampleDataLogic().downloadMRHead()
slicer.app.processEvents()
print(f"Loaded: {volumeNode.GetName()}  dims={volumeNode.GetImageData().GetDimensions()}")
