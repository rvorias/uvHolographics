def printLogo():
    log('===========================================================================')
    log('               __  __      __                             __    _          ')
    log('  __  ___   __/ / / /___  / /___  ____ __________ _____  / /_  (_)_________')
    log(' / / / / | / / /_/ / __ \/ / __ \/ __ `/ ___/ __ `/ __ \/ __ \/ / ___/ ___/')
    log('/ /_/ /| |/ / __  / /_/ / / /_/ / /_/ / /  / /_/ / /_/ / / / / / /__(__  ) ')
    log('\__,_/ |___/_/ /_/\____/_/\____/\__, /_/   \__,_/ .___/_/ /_/_/\___/____/  ')
    log('                               /____/          /_/                         ')
    log('===========================================================================')

bl_info = {
    "name": "uvHolographics",
    "description": "",
    "author": "Raphael Vorias",
    "version": (0, 0, 6),
    "blender": (2, 80, 0),
    "location": "3D View > Tools",
    "warning": "", # used for warning icon and text in addons panel
    "wiki_url": "",
    "tracker_url": "",
    "category": "Development"
}

# https://gist.github.com/p2or/2947b1aa89141caae182526a8fc2bc5a

import bpy

from bpy.props import (StringProperty,
                       BoolProperty,
                       IntProperty,
                       FloatProperty,
                       FloatVectorProperty,
                       EnumProperty,
                       PointerProperty,
                       )
from bpy.types import (Panel,
                       Menu,
                       Operator,
                       PropertyGroup,
                       )
from bpy.utils import (previews)

import numpy as np
from random import uniform, randint
import os

DEBUG = True
PATH_UVHOLOGRAPHICS_LOGO = 'logo.png'
TEXTURE_RESOLUTION = 2 # this will be multiplied by 1024
MAIN_OBJECT_NAME = 'Cube'

# global variable to store icons in
custom_icons = None

# ------------------------------------------------------------------------
#    Helper Functions
# ------------------------------------------------------------------------

def log(s):
    '''print a debug message'''
    
    if DEBUG:
        print(s)
        
def create_image(name, k=1):
    '''creates defect textures'''
    
    if name not in bpy.data.images:
        bpy.ops.image.new(name=name,
                            width=k*1024,
                            height=k*1024,
                            color=(0.0,0.0,0.0,0.0))
    else:
        log('-  create_image() : textures exists')
                            
def create_view_layers(context):
    '''todo: checks naming of view layers'''
    
    context.scene.view_layers[0].name = 'real'
    if 'Ground Truth' not in context.scene.view_layers:
        context.scene.view_layers.new(name='ground_truth')

def create_mode_switcher_node_group():
    # https://blender.stackexchange.com/questions/5387/how-to-handle-creating-a-node-group-in-a-script
    # create a group
    if 'mode_switcher' not in bpy.data.node_groups:
        test_group = bpy.data.node_groups.new('mode_switcher', 'ShaderNodeTree')
        
        # create group inputs
        group_inputs = test_group.nodes.new('NodeGroupInput')
        group_inputs.location = (-350,0)
        test_group.inputs.new('NodeSocketShader','Real')
        test_group.inputs.new('NodeSocketColor','Ground Truth')

        # create group outputs
        group_outputs = test_group.nodes.new('NodeGroupOutput')
        group_outputs.location = (300,0)
        test_group.outputs.new('NodeSocketShader','Switch')

        # create three math nodes in a group
        node_mix = test_group.nodes.new('ShaderNodeMixShader')
        node_mix.location = (100,0)
        # adding mode driver
        # don't remove this, difficult to find
        modeDriver = bpy.data.node_groups['mode_switcher'].driver_add('nodes["Mix Shader"].inputs[0].default_value')
        modeDriver.driver.expression = 'mode'
        modeVariable = modeDriver.driver.variables.new()
        modeVariable.name = 'mode'
        modeVariable.type = 'SINGLE_PROP'
        modeVariable.targets[0].id_type = 'SCENE'
        modeVariable.targets[0].id = bpy.data.scenes['Scene']
        modeVariable.targets[0].data_path = 'uv_holographics.mode'

        # link inputs
        test_group.links.new(group_inputs.outputs['Real'], node_mix.inputs[1])
        test_group.links.new(group_inputs.outputs['Ground Truth'], node_mix.inputs[2])

        #link output
        test_group.links.new(node_mix.outputs[0], group_outputs.inputs['Switch'])
    else:
        log('-  create_mode_switcher_node_group() : node group already exists')
        
def add_camera_focus(context, cameraName, targetName):
    camera = context.scene.objects[cameraName]
    target = context.scene.objects[targetName]
    
    if 'Track To' not in camera.constraints:
        tracker = camera.constraints.new(type='TRACK_TO')
        tracker.target = target
        tracker.track_axis = 'TRACK_NEGATIVE_Z'
        tracker.up_axis = 'UP_Y'
    else:
        log('-  add_camera_focus() : camera constraint already exists')
            
def toggle_mode(context):
    '''helper function for background switching'''
    scene = context.scene
    uvh = scene.uv_holographics
        
    if uvh.mode == 0:
        # set from realistic to ground truth
        uvh.mode = 1
        scene.render.filter_size = 0
        scene.view_settings.view_transform = 'Standard'
    else:
        # set from ground truth to realistic
        uvh.mode = 0
        scene.render.filter_size = 1.5
        scene.view_settings.view_transform = 'Filmic'
                
    # hack to update driver dependencies
    bpy.data.node_groups["mode_switcher"].animation_data.drivers[0].driver.expression = 'mode'
            
def render_layer(context,layer,id):
    '''
    Renders a specific layer, useful for compositing view.
    This function is mode agnostic.
    '''
    scene = context.scene
    uvh = scene.uv_holographics
    context.window.view_layer = scene.view_layers[layer]
    
    scene.render.filepath = f'{uvh.output_dir}{layer}/{id:04d}.png'
    bpy.ops.render.render(write_still=True,layer=layer)
    
def run_variation(context):
    '''
    manipulates objects to create variations
    todo: scenarios
    todo: read from XML file
    '''
    
    # assume one camera
    camera = context.scene.objects['Camera']
    
    # we assume a perimeter to sample our camera locations from
    r = 4.0 + uniform(-0.2,8.0)
    theta = np.pi/2 + uniform(-np.pi/8,np.pi/8)
    phi = uniform(0,2*np.pi)
    
    # create parameter
    randX = r*np.sin(theta)*np.cos(phi)
    randY = r*np.sin(theta)*np.sin(phi)
    randZ = r*np.cos(theta)
    
    camera.location = (randX, randY, randZ)
                
# ------------------------------------------------------------------------
#    Scene Properties
# ------------------------------------------------------------------------

class MyProperties(PropertyGroup):
    separate_background: BoolProperty(
        name="Separate background class",
        description="Extra class for background",
        default = True
        )

    n_defects: IntProperty(
        name ="Defect classes",
        description="Number of defect classes",
        default = 1,
        min = 1,
        max = 10
        )
        
    n_samples: IntProperty(
        name ="Number of samples",
        description="Number of samples to generate",
        default = 1,
        min = 1,
        max = 500
        )

    output_dir: StringProperty(
        name = "Output folder",
        description="Choose a directory:",
        default="../output/",
        maxlen=1024,
        subtype='DIR_PATH'
        )
        
    mode: IntProperty(
        name ="Visualization mode",
        description="Realistic/Ground truth",
        default = 0,
        min = 0,
        max = 1
        )

# ------------------------------------------------------------------------
#    Operators
# ------------------------------------------------------------------------
          
class WM_OT_GenerateComponents(Operator):
    '''Generate blank texture maps and view layers'''
    
    bl_label = "Generate components"
    bl_idname = "wm.gen_components"
    
    def execute(self, context):
        scene = context.scene
        uvh = scene.uv_holographics
        
        log('-generating components')
        # create blank textures
        for i in range(uvh.n_defects):
            create_image(name=f"defect{i}",k=2)
            
        create_view_layers(context)
        create_mode_switcher_node_group()
        add_camera_focus(context,'Camera',MAIN_OBJECT_NAME) # updates viewport
        log('[[done]]')
        
        return {'FINISHED'}
      
class WM_OT_ToggleMaterials(Operator):
    '''Toggle between realistic view and ground truth'''
    
    bl_label = "Toggle Real/GT"
    bl_idname = "wm.toggle_real_gt"
    
    def execute(self, context):
        toggle_mode(context)
        
        return {'FINISHED'}
    
class WM_OT_SampleVariation(Operator):
    '''Runs a sample variation'''
    
    bl_label = "Sample variation"
    bl_idname = "wm.sample_variation"
    
    def execute(self, context):
        run_variation(context)
        
        return {'FINISHED'}
            
class WM_OT_StartScenarios(Operator):
    '''Vary camera positions'''
    
    bl_label = "Generate"
    bl_idname = "wm.start_scenarios"
    
    def execute(self, context):
        scene = context.scene
        uvh = scene.uv_holographics
        
        # make sure to start in realistic mode
        if uvh.mode != 0:
            toggle_mode(context)
        
        for i in range(uvh.n_samples):
            run_variation(context)              
            render_layer(context, 'real', i+1)
            toggle_mode(context)
            render_layer(context, 'ground_truth', i+1)
            toggle_mode(context)
            
        # switch back to real scene
        context.window.view_layer = scene.view_layers['real']
        log('[[done]]')
        
        return {'FINISHED'}

# ------------------------------------------------------------------------
#    Panel in Object Mode
# ------------------------------------------------------------------------

class OBJECT_PT_CustomPanel(Panel):
    bl_label = "uvHolographics"
    bl_idname = "OBJECT_PT_custom_panel"
    bl_space_type = "VIEW_3D"   
    bl_region_type = "UI"
    bl_category = "Annotation"
    bl_context = "objectmode"
    
    @classmethod
    def poll(self,context):
        return context.object is not None
    
    def draw_header(self,context):
        global custom_icons
        self.layout.label(text="",icon_value=custom_icons["custom_icon"].icon_id)

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        uvh = scene.uv_holographics
        
        layout.label(text='Setup')
        box = layout.box()
        box.prop(uvh, "separate_background")  
        box.prop(uvh, "n_defects")
        box.operator("wm.gen_components")        
        
        layout.label(text='Operations')
        box = layout.box()
        box.operator("wm.toggle_real_gt")
        box.operator("wm.sample_variation")
        
        layout.label(text='Generation')
        
        box = layout.box()
        box.prop(uvh, "n_samples")
        box.prop(uvh, "output_dir")
        box.operator("wm.start_scenarios")
        box.separator()

#class OBJECT_PT_LabelColorSubPanel(Panel):
#    bl_label = "Class definitions"
#    bl_idname = "OBJECT_PT_label_color_sub_panel"
#    bl_parent_id = "OBJECT_PT_custom_panel"
#    bl_space_type = "VIEW_3D"   
#    bl_region_type = "UI"
#    bl_category = "Annotation"
#    bl_context = "objectmode"
#    
#    @classmethod
#    def poll(self,context):
#        return context.object is not None
#    
#    def draw(self, context):pass
#    def draw_header(self, context):
#        layout = self.layout
#        scene = context.scene
#        uvh = scene.uv_holographics

# ------------------------------------------------------------------------
#    Registration
# ------------------------------------------------------------------------

classes = (
    MyProperties,
    WM_OT_GenerateComponents,
    WM_OT_ToggleMaterials,
    WM_OT_SampleVariation,
    WM_OT_StartScenarios,
    OBJECT_PT_CustomPanel
)

def register():
    from bpy.utils import register_class
    
    global custom_icons
    
    printLogo()
    
    for cls in classes:
        register_class(cls)
        
    # https://blender.stackexchange.com/questions/32335/how-to-implement-custom-icons-for-my-script-addon
    custom_icons = bpy.utils.previews.new()
    script_path = bpy.context.space_data.text.filepath
    icons_dir = os.path.join(os.path.dirname(script_path), "icons")
    custom_icons.load("custom_icon", os.path.join(icons_dir, "logo.png"), 'IMAGE')
        
    bpy.types.Scene.uv_holographics = PointerProperty(type=MyProperties)

def unregister():
    from bpy.utils import unregister_class
    
    global custom_icons
    
    for cls in reversed(classes):
        unregister_class(cls)
    del bpy.types.Scene.uv_holographics
    
    bpy.utils.previews.remove(custom_icons)

if __name__ == "__main__":
    register()
#    unregister()