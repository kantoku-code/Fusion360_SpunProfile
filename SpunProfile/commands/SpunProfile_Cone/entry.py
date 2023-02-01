import adsk.core as core
import adsk.fusion as fusion
import os
from ...lib import fusion360utils as futil
from ... import config
from .SpunProfileConeFactry import SpunProfileFactry

app = core.Application.get()
ui = app.userInterface


# TODO *** コマンドのID情報を指定します。 ***

CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_spunProfileCone'
CMD_NAME = '回転プロファイル(コーン)'
CMD_Description = '回転プロファイルの作成'
# パネルにコマンドを昇格させることを指定します。
IS_PROMOTED = False

# TODO *** コマンドボタンが作成される場所を定義します。 ***
# これは、ワークスペース、タブ、パネル、および 
# コマンドの横に挿入されます。配置するコマンドを指定しない場合は
# 最後に挿入されます。

WORKSPACE_ID = config.design_workspace
TAB_ID = config.design_tab_id
TAB_NAME = config.design_tab_name

PANEL_ID = config.create_panel_id
PANEL_NAME = config.create_panel_name
PANEL_AFTER = config.create_panel_after

# DROPDOWN_ID = config.dropdown_id
# DROPDOWN_TEXT = config.dropdown_text
DROPDOWN = config.dropDown

COMMAND_BESIDE_ID = ''

# コマンドアイコンのリソースの場所、ここではこのディレクトリの中に
# "resources" という名前のサブフォルダを想定しています。
ICON_FOLDER = os.path.join(
    os.path.dirname(
        os.path.abspath(__file__)
    ),
    'resources',
    ''
)

# イベントハンドラのローカルリストで、参照を維持するために使用されます。
# それらは解放されず、ガベージコレクションされません。
local_handlers = []

_bodyIpt: core.SelectionCommandInput = None
_axisIpt: core.SelectionCommandInput = None
_pitchIpt: core.ValueCommandInput = None

_fact: 'SpunProfileFactry' = None


# アドイン実行時に実行されます。
def start():
    # コマンドの定義を作成する。
    cmd_def = ui.commandDefinitions.addButtonDefinition(
        CMD_ID,
        CMD_NAME,
        CMD_Description,
        ICON_FOLDER
    )

    # コマンド作成イベントのイベントハンドラを定義します。
    # このハンドラは、ボタンがクリックされたときに呼び出されます。
    futil.add_handler(cmd_def.commandCreated, command_created)

    # ******** ユーザーがコマンドを実行できるように、UIにボタンを追加します。 ********
    # ボタンが作成される対象のワークスペースを取得します。
    # workspace = ui.workspaces.itemById(WORKSPACE_ID)

    # toolbar_tab = workspace.toolbarTabs.itemById(TAB_ID)
    # if toolbar_tab is None:
    #     toolbar_tab = workspace.toolbarTabs.add(TAB_ID, TAB_NAME)

    # # ボタンが作成されるパネルを取得します。
    # panel = workspace.toolbarPanels.itemById(PANEL_ID)
    # if panel is None:
    #     panel = toolbar_tab.toolbarPanels.add(PANEL_ID, PANEL_NAME, PANEL_AFTER, False)

    # ドロップダウン
    dropDown: core.DropDownControl = config.dropDown

    # 指定された既存のコマンドの後に、UI のボタンコマンド制御を作成します。
    control = dropDown.controls.addCommand(cmd_def, COMMAND_BESIDE_ID, False)

    # コマンドをメインツールバーに昇格させるかどうかを指定します。
    control.isPromoted = IS_PROMOTED


# アドイン停止時に実行されます。
def stop():
    # このコマンドのさまざまなUI要素を取得する
    workspace = ui.workspaces.itemById(WORKSPACE_ID)
    panel = workspace.toolbarPanels.itemById(PANEL_ID)
    command_control = panel.controls.itemById(CMD_ID)
    command_definition = ui.commandDefinitions.itemById(CMD_ID)

    # ボタンコマンドの制御を削除する。
    if command_control:
        command_control.deleteMe()

    # コマンドの定義を削除します。
    if command_definition:
        command_definition.deleteMe()


def command_created(args: core.CommandCreatedEventArgs):
    # futil.log(f'{CMD_NAME}:{args.firingEvent.name}')

    cmd: core.Command = core.Command.cast(args.command)
    cmd.isPositionDependent = True

    # **inputs**
    inputs: core.CommandInputs = cmd.commandInputs

    global _bodyIpt
    _bodyIpt = inputs.addSelectionInput(
        '_bodyIptId',
        'ボディ',
        '該当するソリッドボディを選択してください'
    )
    _bodyIpt.setSelectionLimits(0)
    _bodyIpt.addSelectionFilter(core.SelectionCommandInput.SolidBodies)
    _bodyIpt.tooltip = 'ソリッドボディが選択可能です'

    global _axisIpt
    _axisIpt = inputs.addSelectionInput(
        '_bodyIptId',
        '回転軸',
        '回転軸を選択してください'
    )
    _axisIpt.setSelectionLimits(0)
    filterLst = [
        core.SelectionCommandInput.ConstructionLines,
        # core.SelectionCommandInput.SketchLines,
        core.SelectionCommandInput.CylindricalFaces,
        core.SelectionCommandInput.ConicalFaces,
        core.SelectionCommandInput.LinearEdges,
    ]
    [_axisIpt.addSelectionFilter(f) for f in filterLst]
    _axisIpt.tooltip = '構築軸・円筒面・円錐面・直線のエッジが選択可能です'

    global _pitchIpt
    unitMgr: core.UnitsManager = futil.app.activeProduct.unitsManager
    _pitchIpt = inputs.addValueInput(
        '_pitchIptId',
        'ピッチ',
        unitMgr.defaultLengthUnits,
        core.ValueInput.createByReal(0.1)
    )
    _pitchIpt.minimumValue = 0.0001
    minValueDisp = unitMgr.convert(
        _pitchIpt.minimumValue,
        unitMgr.internalUnits,
        unitMgr.defaultLengthUnits)
    _pitchIpt.tooltip = f'{minValueDisp}{unitMgr.defaultLengthUnits}以上で設定可能です'

    # **event**
    futil.add_handler(
        cmd.destroy,
        command_destroy,
        local_handlers=local_handlers
    )

    # futil.add_handler(
    #     cmd.executePreview,
    #     command_executePreview,
    #     local_handlers=local_handlers
    # )

    futil.add_handler(
        cmd.execute,
        command_execute,
        local_handlers=local_handlers
    )

    futil.add_handler(
        cmd.inputChanged,
        command_inputChanged,
        local_handlers=local_handlers
    )

    futil.add_handler(
        cmd.preSelect,
        command_preSelect,
        local_handlers=local_handlers
    )

    futil.add_handler(
        cmd.validateInputs,
        command_validateInputs,
        local_handlers=local_handlers
    )


    # other
    global _fact
    _fact = SpunProfileFactry()


def command_validateInputs(args: core.ValidateInputsEventArgs):
    # futil.log(f'{CMD_NAME}:{args.firingEvent.name}')

    global _bodyIpt, _axisIpt
    if _bodyIpt.selectionCount < 1:
        args.areInputsValid = False
    elif _axisIpt.selectionCount < 1:
        args.areInputsValid = False


def command_preSelect(args: core.SelectionEventArgs):
    # futil.log(f'{CMD_NAME}:{args.firingEvent.name}')

    if args.activeInput.selectionCount > 0:
        args.isSelectable = False

    global _fact, _axisIpt
    if args.activeInput != _axisIpt:
        return

    args.isSelectable =  _fact.has_axis(args.selection.entity)


def command_destroy(args: core.CommandEventArgs):
    # futil.log(f'{CMD_NAME}:{args.firingEvent.name}')

    global local_handlers
    local_handlers = []


# def command_executePreview(args: core.CommandEventArgs):
#     # futil.log(f'{CMD_NAME}:{args.firingEvent.name}')


def command_execute(args: core.CommandEventArgs):
    # futil.log(f'{CMD_NAME}:{args.firingEvent.name}')

    global _bodyIpt, _axisIpt, _pitchIpt, _fact
    _fact.get_spun_profile_body(
        _bodyIpt.selection(0).entity,
        _axisIpt.selection(0).entity,
        _pitchIpt.value,
    )


def command_inputChanged(args: core.InputChangedEventArgs):
    # futil.log(f'{CMD_NAME}:{args.firingEvent.name}')

    global _bodyIpt, _axisIpt, _fact

    if args.input == _bodyIpt:
        if _bodyIpt.selectionCount < 1:
            _bodyIpt.hasFocus = True
            return
        if _axisIpt.selectionCount < 1:
            # entity = get_click_face(_bodyIpt.selection(0))
            # print(f'axis:{_fact.has_axis(entity)}')
            # if _fact.has_axis(entity):
            #     _axisIpt.addSelection(entity)

            _axisIpt.hasFocus = True


def get_click_face(
    sel: core.Selection) -> fusion.BRepFace:

    des: fusion.Design = futil.app.activeProduct
    root: fusion.Component = des.rootComponent

    entities = root.findBRepUsingPoint(
        sel.point,
        fusion.BRepEntityTypes.BRepFaceEntityType,
        0.1
    )

    lst = [ent for ent in entities if ent.body == sel.entity]

    if len(lst) > 0:
        return lst[0]
    else:
        return None