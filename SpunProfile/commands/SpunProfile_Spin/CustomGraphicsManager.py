import traceback
import adsk
import adsk.core as core
import adsk.fusion as fusion

class DrawCGFactry():

    def __init__(
        self
    ) -> None:
        '''
        コンストラクタ
        '''

        self.app = core.Application.cast(None)
        self.des :fusion.Design = self.app.activeProduct
        self.root :fusion.Component = self.des.rootComponent

        self.cgGroup = fusion.CustomGraphicsGroup.cast(None)

        self.solidRed = fusion.CustomGraphicsSolidColorEffect.create(
            core.Color.create(255,0,0,255)
        )
        self.solidBlue = fusion.CustomGraphicsSolidColorEffect.create(
            core.Color.create(0,0,255,255)
        )

        self.refreshCG()


    def __del__(
        self
    ) -> None:
        '''
        デストラクタ
        '''

        self.removeCG()


    def removeCG(
        self
    ) -> None:
        '''
        カスタムグラフィックの削除
        '''

        cgs = [cmp.customGraphicsGroups for cmp in self.des.allComponents]
        cgs = [cg for cg in cgs if cg.count > 0]
        
        if len(cgs) < 1: return

        for cg in cgs:
            gps = [c for c in cg]
            gps.reverse()
            for gp in gps:
                gp.deleteMe()


    def refreshCG(
        self
    ) -> None:
        '''
        CGのリフレッシュ
        '''

        self.removeCG()
        des :fusion.Design = self.app.activeProduct
        root :fusion.Component = des.rootComponent
        self.cgGroup = root.customGraphicsGroups.add()


    def update(
        self,
        baseBody: fusion.BRepBody,
        targetBody: fusion.BRepBody,
    ) -> None:
        '''
        ボディの表示アップデート
        '''

        self.refreshCG()

        cgBdy = self.cgGroup.addBRepBody(baseBody)
        cgBdy.color = self.solidBlue
        cgBdy.weight = 2

        cgBdy = self.cgGroup.addBRepBody(targetBody)
        cgBdy.color = self.solidRed
        cgBdy.weight = 2