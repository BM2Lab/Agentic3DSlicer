@controller.action("Load a NIfTI volume into the scene")
async def load_volume(path: str, session: SlicerSession):
    result = await session.exec(f"""
import slicer
node = slicer.util.loadVolume('{path}')
__result__ = {{'name': node.GetName(), 'id': node.GetID()}}
""")
    return ActionResult(extracted_content=str(result["result"]))

@controller.action("Get current scene state")
async def get_scene_state(session: SlicerSession):
    result = await session.exec("""
import slicer, json
__result__ = {
    'volumes': [n.GetName() for n in slicer.util.getNodesByClass('vtkMRMLVolumeNode')],
    'segs':    [n.GetName() for n in slicer.util.getNodesByClass('vtkMRMLSegmentationNode')],
    'transforms': [n.GetName() for n in slicer.util.getNodesByClass('vtkMRMLTransformNode')],
}
""")
    return ActionResult(extracted_content=json.dumps(result["result"]))