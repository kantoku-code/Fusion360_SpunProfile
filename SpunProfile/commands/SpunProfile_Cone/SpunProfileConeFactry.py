import traceback
import adsk
import adsk.core as core
import adsk.fusion as fusion
import time

class SpunProfileFactry():
    def __init__(self) -> None:
        self.app: core.Application = core.Application.get()
        self.tmpMgr: fusion.TemporaryBRepManager = fusion.TemporaryBRepManager.get()

        self.largeValue = 1000000
        self.body: fusion.BRepBody = None
        self.cylinder: fusion.BRepFace = None
        self.axis: core.InfiniteLine3D = None
        

    def has_axis(
        self,
        entity) -> bool:
        '''
        軸となる要素か？
        '''

        return True if self._get_axis(entity) else False


    def get_spun_profile_body(
        self,
        body: fusion.BRepBody,
        axisEntity,
        pitch: float):
        '''
        回転ボディの取得
        '''

        startTime = time.time()

        self.body = body
        self.axisEntity = axisEntity
        self.axis = self._get_axis(self.axisEntity)

        (self.cylinder, edgeface1, edgeface2) = self._get_cylinder_face()

        startPoint: core.Point3D = self.axis.intersectWithSurface(edgeface1.geometry)[0]
        endPoint: core.Point3D = self.axis.intersectWithSurface(edgeface2.geometry)[0]
        vector: core.Vector3D = startPoint.vectorTo(endPoint)
        
        unitVec: core.Vector3D = vector.copy()
        unitVec.scaleBy(pitch / vector.length)

        count = int(vector.length / pitch) + 1
        point: core.Point3D = startPoint.copy()

        cylinder_data = []
        for _ in range(count):
            checkPlane: core.Plane = core.Plane.create(
                point,
                self.axis.direction
            )

            interBody: fusion.BRepBody = self.tmpMgr.planeIntersection(
                self.body,
                checkPlane
            )

            measMgr: core.MeasureManager = self.app.measureManager
            res: core.MeasureResults = measMgr.measureMinimumDistance(
                interBody,
                self.cylinder
            )

            cylinder_data.append(
                (
                    point.copy(),
                    self.largeValue - res.value
                )
            )

            point.translateBy(unitVec)

        corns = []
        for cyl1, cyl2 in zip(cylinder_data, cylinder_data[1:]):
            corns.append(
                self.tmpMgr.createCylinderOrCone(
                    cyl1[0],
                    cyl1[1],
                    cyl2[0],
                    cyl2[1],
                )
            )

        resBody: fusion.BRepBody = self._get_union_body(corns)

        displayPitch = self._get_disply_pitch_str(pitch)
        occ: fusion.Occurrence = self._create_occ(
            'SpunProfile_' + f'pitch_{displayPitch}'
        )

        self._draw_bodies(
            [
                resBody
            ],
            occ,
        )

        self.app.log(
            f'spun_profile_cone pitch:{displayPitch} time:{time.time() - startTime}s'
        )


    def _get_disply_pitch_str(
        self,
        value: float) -> str:
        '''
        ドキュメント設定の長さ単位付き値
        '''

        unitMgr: core.UnitsManager = self.app.activeProduct.unitsManager
        valueDisp = unitMgr.convert(
            value,
            unitMgr.internalUnits,
            unitMgr.defaultLengthUnits)
        
        return f'{valueDisp}{unitMgr.defaultLengthUnits}'


    def _create_occ(
        self,
        name: str) -> fusion.Occurrence:
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

    def _get_union_body(
        self,
        bodyLst: list) -> fusion.BRepBody:
        '''
        ブーリアン和のボディ取得
        '''

        return self._get_boolean_body(
            bodyLst,
            fusion.BooleanTypes.UnionBooleanType
        )


    def _get_boolean_body(
        self,
        bodyLst: list,
        booleanType: fusion.BooleanTypes) -> fusion.BRepBody:
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
        axisEntity) -> core.InfiniteLine3D:
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
        self,) -> fusion.BRepFace:
        '''
        シリンダー面の取得
        '''

        bBox: core.OrientedBoundingBox3D = self._get_boundingBox(
            self.body,
            self.axis.direction
        )

        interPoint: core.Point3D = self._get_intersect_point_from_infinite(
            bBox.centerPoint,
            self.axis,
        )

        p1, p2 = self._get_length_range_points(bBox, interPoint)

        cylinderBody: fusion.BRepBody = self._get_cylinder_body(
            p1,
            p2,
            self.largeValue
        )

        return cylinderBody.faces[0], cylinderBody.faces[1], cylinderBody.faces[2]


    def _get_cylinder_body(
        self,
        startPoint: core.Point3D,
        endPoint: core.Point3D,
        radius:float) -> fusion.BRepBody:
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
        refPoint: core.Point3D) -> set:
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
        axis: core.Vector3D) -> core.OrientedBoundingBox3D:
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

        tmpVec: core.Vector3D = core.Vector3D.create(1,0,0)
        if vector.isParallelTo(tmpVec):
            tmpVec = core.Vector3D.create(0,1,0)

        return vector.crossProduct(tmpVec)


    def _draw_bodies(
        self,
        bodyLst: list,
        targetOcc: fusion.Occurrence = None) -> list:
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

