import traceback
import adsk
import adsk.core as core
import adsk.fusion as fusion
from .CustomGraphicsManager import CustomGraphicsManager
import math
import time

TOTAL_ROTATION_ANGLE = 180
DEBUG = False

class SpunProfileFactry():
    def __init__(self) -> None:
        self.app: core.Application = core.Application.get()
        self.tmpMgr: fusion.TemporaryBRepManager = fusion.TemporaryBRepManager.get()

        des: fusion.Design = self.app.activeProduct
        self.root: fusion.Component = des.rootComponent
        self.viewport: core.Viewport = self.app.activeViewport

        self.largeValue = 1000000 # 仮の値
        self.body: fusion.BRepBody = None
        self.axis: core.InfiniteLine3D = None
        self.sideVector: core.Vector3D = None

        self.camera: core.Camera = None

    def has_axis(
        self,
        entity
    ) -> bool:
        '''
        軸となる要素か？
        '''

        return True if self._get_axis(entity) else False


    def get_spun_profile_body(
        self,
        body: fusion.BRepBody,
        axisEntity,
        count: int,
        isAnimation: bool,
    ) -> None:
        '''
        回転ボディの取得
        '''

        startTime = time.time()

        self.body = body
        self.axisEntity = axisEntity
        self.axis = self._get_axis(self.axisEntity)

        # ボディの範囲
        bBox: core.OrientedBoundingBox3D = self._get_boundingBox(
            self.body,
            self.axis.direction
        )
        self.sideVector = bBox.widthDirection
        self.largeValue = max(
            bBox.height,
            bBox.length,
            bBox.width,
        ) * 1.01

        # 端面部取得
        (_, edgeface1, _) = self._get_cylinder_face(
            bBox,
            self.axis,
            self.largeValue
        )

        # 元の位置での仮原点
        startPoint: core.Point3D = self.axis.intersectWithSurface(edgeface1.geometry)[0]

        # 原点へのマトリックス
        toOriginMat: core.Matrix3D = self._get_matrix_to_origin(
            startPoint,
            self.sideVector,
            self.axis.direction
        )

        # 断面用の面
        sectionFace: fusion.BRepBody = self._get_large_face_xy(self.largeValue)

        # 回転用マトリックス
        mat: core.Matrix3D = core.Matrix3D.create()
        mat.setToRotation(
            math.radians(TOTAL_ROTATION_ANGLE / count),
            self.root.yConstructionAxis.geometry.direction,
            self.root.originConstructionPoint.geometry,
        )

        # ツール用ボディ
        toolBaseBody: fusion.BRepBody = self.tmpMgr.copy(self.body)
        self.tmpMgr.transform(toolBaseBody, toOriginMat)

        # アニメ準備
        if isAnimation:
            self.app.executeTextCommand(
                u'Transaction.Start {}'.format('SpunProfileSpin')
            )

            # 全てのボディ非表示
            self._hide_all_bodies()

            # カメラのバックアップ
            self.camera = self.viewport.camera
            self.camera.isSmoothTransition = False

            # 原点に移動
            self._move_to_origin_camera(toOriginMat)

            # cg
            cgMgr = CustomGraphicsManager()

        # 回転させ削りまくる
        for idx in range(count):
            toolBody: fusion.BRepBody = self.tmpMgr.copy(toolBaseBody)
            try:
                self.tmpMgr.booleanOperation(
                    sectionFace,
                    toolBody,
                    fusion.BooleanTypes.DifferenceBooleanType
                )
            except:
                print(f'ng:{idx}')

            if isAnimation and idx % 3 == 0:
                cgMgr.update(sectionFace, toolBody)

            self.tmpMgr.transform(
                toolBaseBody,
                mat
            )

        # アニメ終了
        if isAnimation:
            cgMgr.removeCG()

            self.viewport.camera = self.camera
            self.viewport.refresh()

            self.app.executeTextCommand(u'Transaction.Abort')

        dump_msg(f' -- end spin:{time.time() - startTime}s')

        # Xのマイナス半面だけ取得
        sectHalf = self._get_intersect_body(
            [
                self.tmpMgr.copy(sectionFace),
                self._get_large_face_xy_half(
                    self.largeValue,
                    False
                )
            ]
        )

        # 180度Deg回転させる
        mats = self._get_rotation_matrix_list([180])
        self.tmpMgr.transform(
            sectHalf,
            mats[0]
        )

        # 積
        sectionFace: fusion.BRepBody = self._get_intersect_body(
            [
                sectionFace,
                sectHalf
            ]
        )

        # 差
        resBody: fusion.BRepBody = self._get_large_face_xy_half(
            self.largeValue,
            True
        )

        self.tmpMgr.booleanOperation(
            resBody,
            sectionFace,
            fusion.BooleanTypes.DifferenceBooleanType
        )

        # 元の位置に戻す
        fromOriginMat: core.Matrix3D = toOriginMat
        fromOriginMat.invert()

        self.tmpMgr.transform(
            resBody,
            fromOriginMat
        )

        # サーフェス出力
        displayAngle = 180 / count
        occ: fusion.Occurrence = self._create_occ(
            'SpunProfile_Spin-' + f'Angle_{displayAngle}Deg'
        )

        bodyList: list = self._draw_bodies(
            [
                resBody
            ],
            occ,
        )
        dump_msg(f' -- end surface:{time.time() - startTime}s')

        # スケッチサポート
        sktPlane: fusion.ConstructionPlane = self._create_construction_plane(
            occ,
            startPoint,
            self.axis.direction,
            self.sideVector,
        )

        # スケッチ
        skt: fusion.Sketch = occ.component.sketches.add(
            sktPlane
        )
        dump_msg(f' -- end sketchn:{time.time() - startTime}s')

        # プロジェクト
        self._project_edges(skt, bodyList)
        dump_msg(f' -- end project:{time.time() - startTime}s')

        self.app.log(
            f'spun_profile_spin time:{time.time() - startTime}s'
        )


    def _project_edges(
        self,
        sketch: fusion.Sketch,
        bodyList: list
    ) -> None:
        '''
        スケッチエッジを投影
        '''

        objs: core.ObjectCollection = core.ObjectCollection.create()
        for b in bodyList:
            [objs.add(e) for e in b.edges]

        sketch.isComputeDeferred = True
        sketch.project(objs)
        # crv: fusion.SketchCurve = None
        # for crv in sketch.sketchCurves:
        #     crv.isReference = False
        sketch.isComputeDeferred = False


    def _create_construction_plane(
        self,
        occurrence: fusion.Occurrence,
        origin: core.Point3D,
        vectorU: core.Vector3D,
        vectorV: core.Vector3D,
    ) -> fusion.ConstructionPlane:
        '''
        平面作成
        '''

        vectorU.normalize()
        vectorV.normalize()
        basePlane: core.Plane = core.Plane.createUsingDirections(
            origin,
            vectorU,
            vectorV,
        )

        comp: fusion.Component = occurrence.component
        des: fusion.Design = comp.parentDesign
        baseFeat: fusion.BaseFeature = None
        if des.designType == fusion.DesignTypes.ParametricDesignType:
            baseFeat = comp.features.baseFeatures.add()

        constPlanes: fusion.ConstructionPlanes = comp.constructionPlanes
        planeIpt: fusion.ConstructionPlaneInput = constPlanes.createInput(
            occurrence
        )

        if baseFeat:
            baseFeat.startEdit()

        planeIpt.setByPlane(basePlane)
        constPlane: fusion.ConstructionPlane = constPlanes.add(
            planeIpt
        )

        if baseFeat:
            baseFeat.finishEdit()

        return constPlane


    def _create_occ(
        self,
        name: str
    ) -> fusion.Occurrence:
        '''
        オカレンス作成
        '''

        des: fusion.Design = self.app.activeProduct
        root: fusion.Component = des.rootComponent

        occ: fusion.Occurrence = root.occurrences.addNewComponent(
            core.Matrix3D.create()
        )
        occ.component.name = name

        return occ


    def _get_intersect_body(
        self,
        bodyLst: list
    ) -> fusion.BRepBody:
        '''
        ブーリアン積のボディ取得
        '''

        return self._get_boolean_body(
            bodyLst,
            fusion.BooleanTypes.IntersectionBooleanType
        )


    def _get_union_body(
        self,
        bodyLst: list
    ) -> fusion.BRepBody:
        '''
        ブーリアン和のボディ取得
        '''

        return self._get_boolean_body(
            bodyLst,
            fusion.BooleanTypes.UnionBooleanType
        )


    def _get_diff_body(
        self,
        bodyLst: list
    ) -> fusion.BRepBody:
        '''
        ブーリアン差のボディ取得
        '''

        return self._get_boolean_body(
            bodyLst,
            fusion.BooleanTypes.DifferenceBooleanType
        )


    def _get_boolean_body(
        self,
        bodyLst: list,
        booleanType: fusion.BooleanTypes
    ) -> fusion.BRepBody:
        '''
        ブーリアンボディ取得
        '''

        resBody: fusion.BRepBody = None
        if len(bodyLst) < 0:
            resBody = None
        elif len(bodyLst) == 1:
            resBody = bodyLst[0]
        else:
            resBody = bodyLst.pop()
            for b in bodyLst:
                try:
                    self.tmpMgr.booleanOperation(
                        resBody,
                        b,
                        booleanType
                    )
                except:
                    pass

        return resBody


    def _get_axis(
        self,
        axisEntity
    ) -> core.InfiniteLine3D:
        '''
        要素から軸となる無限線取得
        '''

        geo = None
        if hasattr(axisEntity, 'worldGeometry'):
            # sketch line
            geo = axisEntity.worldGeometry
        elif hasattr(axisEntity, 'geometry'):
            geo = axisEntity.geometry
        else:
            return None


        if hasattr(geo, 'direction'):
            # construction line
            return geo
        elif hasattr(geo, 'origin') and hasattr(geo, 'axis'):
            # cylinder, cone
            return core.InfiniteLine3D.create(
                geo.origin,
                geo.axis
            )
        elif hasattr(geo, 'startPoint') and hasattr(geo, 'endPoint'):
            # sketch line, liner edge
            stPnt: core.Point3D = geo.startPoint
            edPnt: core.Point3D = geo.endPoint
            return core.InfiniteLine3D.create(
                stPnt,
                stPnt.vectorTo(edPnt)
            )

        return None


    def _get_cylinder_face(
        self,
        bBox: core.OrientedBoundingBox3D,
        axis,
        radius: float
    ) -> fusion.BRepFace:
        '''
        シリンダー面の取得
        '''

        interPoint: core.Point3D = self._get_intersect_point_from_infinite(
            bBox.centerPoint,
            axis,
        )

        p1, p2 = self._get_length_range_points(bBox, interPoint)

        cylinderBody: fusion.BRepBody = self._get_cylinder_body(
            p1,
            p2,
            radius
        )

        return cylinderBody.faces[0], cylinderBody.faces[1], cylinderBody.faces[2]


    def _get_cylinder_body(
        self,
        startPoint: core.Point3D,
        endPoint: core.Point3D,
        radius:float
    ) -> fusion.BRepBody:
        '''
        シリンダーボディ(ソリッド)の取得
        '''

        return self.tmpMgr.createCylinderOrCone(
            startPoint,
            radius,
            endPoint,
            radius
        )


    def _get_intersect_point_from_infinite(
        self,
        point: core.Point3D,
        inf: core.InfiniteLine3D) -> core.Point3D:
        '''
        無限線上の点取得
        '''

        plane: core.Plane = core.Plane.create(
            point,
            inf.direction
        )

        inters: core.ObjectCollection = inf.intersectWithSurface(plane)

        return inters[0]


    def _get_length_range_points(
        self,
        bBox: core.OrientedBoundingBox3D,
        refPoint: core.Point3D
    ) -> set:
        '''
        長さ方向範囲の最大最小点の取得
        '''

        half_length = bBox.length * 0.5
        vec: core.Vector3D = bBox.lengthDirection.copy()

        vec.normalize()
        vec.scaleBy(half_length)
        p1: core.Point3D = refPoint.copy()
        p1.translateBy(vec)

        vec.normalize()
        vec.scaleBy(-half_length)
        p2: core.Point3D = refPoint.copy()
        p2.translateBy(vec)

        return (p1, p2)


    def _get_boundingBox(
        self,
        body: fusion.BRepBody,
        axis: core.Vector3D
    ) -> core.OrientedBoundingBox3D:
        '''
        バウンダリボックス取得
        '''

        measMgr: core.MeasureManager = self.app.measureManager

        return measMgr.getOrientedBoundingBox(
            body,
            axis,
            self._get_orthogonal_vector(axis)
        )


    def _get_orthogonal_vector(
        self,
        vector: core.Vector3D) -> core.Vector3D:
        '''
        直角ベクトルの取得
        '''

        tmpVec: core.Vector3D = core.Vector3D.create(0,0,1)
        if vector.isParallelTo(tmpVec):
            tmpVec = core.Vector3D.create(0,1,0)

        return vector.crossProduct(tmpVec)


    def _draw_bodies(
        self,
        bodyLst: list,
        targetOcc: fusion.Occurrence = None
    ) -> list:
        '''
        bodyの出力
        '''

        des: fusion.Design = self.app.activeProduct
        if not targetOcc:
            comp: fusion.Component = des.rootComponent
        else:
            comp: fusion.Component = targetOcc.component

        baseFeat: fusion.BaseFeature = None
        if des.designType == fusion.DesignTypes.ParametricDesignType:
            baseFeat = comp.features.baseFeatures.add()

        bodies: fusion.BRepBodies = comp.bRepBodies
        resBodies = []
        if baseFeat:
            baseFeat.startEdit()
            resBodies = [bodies.add(body, baseFeat) for body in bodyLst]
            baseFeat.finishEdit()
        else:
            resBodies = [bodies.add(body) for body in bodyLst]

        return resBodies


    def _get_large_face_xy_half(
        self,
        value: float,
        isPlus: bool
    ) -> fusion.BRepBody:
        '''
        xy平面に巨大なX側に半分の平面の取得
        '''

        relative = 1 if isPlus else -1

        try:
            points = [
                core.Point3D.create(value * relative, value, 0),
                core.Point3D.create(0, value, 0),
                core.Point3D.create(0, -value, 0),
                core.Point3D.create(value * relative, -value, 0),
                core.Point3D.create(value * relative, value, 0),
            ]

            return self._get_large_face_form_points(points)
        except:
            self.app.log('Failed:\n{}'.format(traceback.format_exc()))


    def _get_large_face_xy(
        self,
        value: float
    ) -> fusion.BRepBody:
        '''
        xy平面に巨大な平面の取得
        '''

        try:
            points = [
                core.Point3D.create(value, value, 0),
                core.Point3D.create(-value, value, 0),
                core.Point3D.create(-value, -value, 0),
                core.Point3D.create(value, -value, 0),
                core.Point3D.create(value, value, 0),
            ]

            return self._get_large_face_form_points(points)
        except:
            self.app.log('Failed:\n{}'.format(traceback.format_exc()))


    def _get_large_face_form_points(
        self,
        points: list
    ) -> fusion.BRepBody:
        '''
        pointsを元に平面作成
        '''

        try:
            lines = [core.Line3D.create(p1, p2) for p1, p2 in zip(points, points[1:])]

            wireBody: fusion.BRepBody = None
            wireBody, _ = self.tmpMgr.createWireFromCurves(lines)

            return self.tmpMgr.createFaceFromPlanarWires([wireBody])
        except:
            self.app.log('Failed:\n{}'.format(traceback.format_exc()))



    def _get_matrix_to_origin(
        self,
        origin: core.Point3D,
        vectorX: core.Vector3D,
        vectorY: core.Vector3D,
    ) -> core.Matrix3D:
        '''
        原点へのマトリックス取得
        '''

        vectorZ: core.Vector3D = vectorX.crossProduct(vectorY)
        vectorY: core.Vector3D = vectorZ.crossProduct(vectorX)
        vectorX.normalize()
        vectorY.normalize()
        vectorZ.normalize()

        fromMat: core.Matrix3D = core.Matrix3D.create()
        fromMat.setWithCoordinateSystem(
            origin,
            vectorX,
            vectorY,
            vectorZ,
        )

        fromMat.invert()

        return fromMat


    def _get_rotation_matrix_list(
        self,
        angles: list
    ) -> list:
        '''
        断面用のY軸回転マトリックス取得
        '''

        matLst = []
        for ang in angles:
            mat: core.Matrix3D = core.Matrix3D.create()
            mat.setToRotation(
                math.radians(ang),
                self.root.yConstructionAxis.geometry.direction,
                self.root.originConstructionPoint.geometry,
            )
            matLst.append(mat)

        return matLst


    def _hide_all_bodies(
        self
    ) -> core.ObjectCollection:
        '''
        表示されているボディを全て非表示
        '''

        showBodies: core.ObjectCollection = self.root.findBRepUsingPoint(
            core.Point3D.create(0,0,0),
            fusion.BRepEntityTypes.BRepBodyEntityType,
            1000000000000,
            True
        )
        for body in showBodies:
            body.isLightBulbOn = False

        return showBodies


    def _move_to_origin_camera(
        self,
        eyeMatrix: core.Matrix3D,
    ) -> None:
        '''
        カメラを原点に移動
        '''

        camera = self.viewport.camera
        cameraVec: core.Vector3D = camera.target.vectorTo(
            core.Point3D.create(0,0,0)
        )

        targetPnt: core.point3D = camera.target
        targetPnt.translateBy(cameraVec)
        camera.target = targetPnt

        eyePnt: core.point3D = camera.eye
        eyePnt.translateBy(cameraVec)
        # eyePnt.transformBy(eyeMatrix)
        camera.eye = eyePnt

        camera.isSmoothTransition = False

        self.viewport.camera = camera
        self.viewport.refresh()


def dump_msg(msg) -> None:
    if not DEBUG:
        return

    app: core.Application = core.Application.get()
    app.log(msg)