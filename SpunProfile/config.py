# Application Global Variables
# This module serves as a way to share variables across different
# modules (global variables).

import os

# Flag that indicates to run in Debug mode or not. When running in Debug mode
# more information is written to the Text Command window. Generally, it's useful
# to set this to True while developing an add-in and set it to False when you
# are ready to distribute it.
DEBUG = True

# Gets the name of the add-in from the name of the folder the py file is in.
# This is used when defining unique internal names for various UI elements 
# that need a unique name. It's also recommended to use a company name as 
# part of the ID to better ensure the ID is unique.
ADDIN_NAME = os.path.basename(os.path.dirname(__file__))
COMPANY_NAME = 'KANTOKU'

# Design Workspace
design_workspace = 'FusionSolidEnvironment'

# Tabs
# design_tab_id = f'{ADDIN_NAME}_design_tab'
# design_tab_name = f'{ADDIN_NAME}'
design_tab_id = 'SolidTab'
design_tab_name = ''

# Panels
# doc_panel_name = 'ドキュメント'
# doc_panel_id = f'{ADDIN_NAME}_doc_panel'
# doc_panel_after = ''

# create_panel_name = '作成'
# create_panel_id = f'{ADDIN_NAME}_create_panel'
# create_panel_after = ''
create_panel_name = ''
create_panel_id = 'SolidCreatePanel'
create_panel_after = ''

# modify_panel_name = '修正'
# modify_panel_id = f'{ADDIN_NAME}_modify_panel'
# modify_panel_after = ''

# construction_panel_name = '構築'
# construction_panel_id = f'{ADDIN_NAME}_construction_panel'
# construction_panel_after = ''

# inspect_panel_name = '検査'
# inspect_panel_id = f'{ADDIN_NAME}_Inspect_panel'
# inspect_panel_after = ''

# DropDown
dropdown_text = '回転プロファイル'
dropdown_id = f'{ADDIN_NAME}_dropdown_spun_profile'


# Reference for use in some commands
all_workspace_names = [
    'FusionSolidEnvironment', 'GenerativeEnvironment', 'PCBEnvironment', 'PCB3DEnvironment', 'Package3DEnvironment',
    'FusionRenderEnvironment', 'Publisher3DEnvironment', 'SimulationEnvironment', 'CAMEnvironment', 'DebugEnvironment',
    'FusionDocumentationEnvironment', 'ElectronEmptyLbrEnvironment', 'ElectronDeviceEnvironment',
    'ElectronFootprintEnvironment', 'ElectronSymbolEnvironment', 'ElectronPackageEnvironment'
]

import adsk.core as core
__app = core.Application.get()
__ui = __app.userInterface
__workspace = __ui.workspaces.itemById(design_workspace)
__toolbar_tab = __workspace.toolbarTabs.itemById(design_tab_id)
__panel = __toolbar_tab.toolbarPanels.itemById(create_panel_id)

# ドロップダウン
dropDown: core.DropDownControl = __panel.controls.addDropDown(
    dropdown_text,
    '',
    dropdown_id,
    '',
    False
)