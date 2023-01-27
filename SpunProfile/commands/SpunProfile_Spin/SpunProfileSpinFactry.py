import traceback
import adsk
import adsk.core as core
import adsk.fusion as fusion
import math
import time

class SpunProfileFactry():
    def __init__(self) -> None:
        self.app: core.Application = core.Application.get()
        self.tmpMgr: fusion.TemporaryBRepManager = fusion.TemporaryBRepManager.get()

        des: fusion.Design = self.app.activeProduct
        self.root: fusion.Component = des.rootComponent

        self.largeValue = 1000000
        self.body: fusion.BRepBody = None
        self.cylinder: fusion.BRepFace = None
        self.axis: core.InfiniteLine3D = None
        self.sideVector: core.Vector3D = None

    def has_axis(
        self,
        entity) -> bool:
        '''
        軸となる要素か？
        '''

        return True if self._get_axis(entity) else False

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
            vectorZ
        )

        fromMat.invert()

        return fromMat

    def _get_profile_base_faces(
        self,
        faceBody: fusion.BRepBody,
        matrixList: list
    ) -> list:

        faces = [self.tmpMgr.copy(faceBody) for _ in matrixList]
        [self.tmpMgr.transform(face, mat) for face, mat in zip(faces, matrixList)]

        return faces


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


    def get_spun_profile_body(
        self,
        body: fusion.BRepBody,
        axisEntity,
        pitch: float
    ) -> None:

        '''
        回転ボディの取得
        '''

        startTime = time.time()

        self.body = body
        self.axisEntity = axisEntity
        self.axis = self._get_axis(self.axisEntity)

        bBox: core.OrientedBoundingBox3D = self._get_boundingBox(
            self.body,
            self.axis.direction
        )
        self.sideVector = bBox.widthDirection

        (self.cylinder, edgeface1, edgeface2) = self._get_cylinder_face(
            bBox,
            self.axis,
            self.largeValue
        )

        startPoint: core.Point3D = self.axis.intersectWithSurface(edgeface1.geometry)[0]
        # endPoint: core.Point3D = self.axis.intersectWithSurface(edgeface2.geometry)[0]
        # vector: core.Vector3D = startPoint.vectorTo(endPoint)

        toOriginMat: core.Matrix3D = self._get_matrix_to_origin(
            startPoint,
            self.sideVector,
            self.axis.direction
            # vector
        )

        # sectionFace: fusion.BRepBody = self._get_large_face(
        #     self.root.yConstructionAxis.geometry,
        #     core.Point3D.create(
        #         self.largeValue,
        #         0,
        #         0,
        #     )
        # )
        # self._draw_bodies([sectionFace])

        sectionMats: list = self._get_rotation_matrix_list(
            [0, 90, 180, 270]
        )

        sectionFaces: list = self._get_profile_base_faces(
            # sectionFace,
            self._get_large_face(
                self.root.yConstructionAxis.geometry,
                core.Point3D.create(
                    self.largeValue,
                    0,
                    0,
                )
            ),
            sectionMats
        )
        # self._draw_bodies(sectionFaces)

        count = 90
        mat: core.Matrix3D = core.Matrix3D.create()
        mat.setToRotation(
            math.radians(90 / count),
            self.root.yConstructionAxis.geometry.direction,
            self.root.originConstructionPoint.geometry,
        )

        toolBaseBody: fusion.BRepBody = self.tmpMgr.copy(self.body)
        self.tmpMgr.transform(toolBaseBody, toOriginMat)

        for idx in range(count):
            toolAngBody: fusion.BRepBody = self.tmpMgr.copy(toolBaseBody)
            for sectIdx, sectionFace in enumerate(sectionFaces):
                toolBody: fusion.BRepBody = self.tmpMgr.copy(toolAngBody)
                try:
                    self.tmpMgr.booleanOperation(
                        sectionFace,
                        toolBody,
                        fusion.BooleanTypes.DifferenceBooleanType
                    )
                except:
                    print(f'ng:{idx}-{sectIdx}')
            self.tmpMgr.transform(
                toolBaseBody,
                mat
            )

        self._draw_bodies(sectionFaces)

        # resBody: fusion.BRepBody = self._get_large_face(
        #         self.root.yConstructionAxis.geometry,
        #         core.Point3D.create(
        #             self.largeValue,
        #             0,
        #             0,
        #         )
        #     )

        # self.tmpMgr.booleanOperation(
        #     resBody,
        #     sectionFace,
        #     fusion.BooleanTypes.DifferenceBooleanType
        # )

        # fromOriginMat: core.Matrix3D = toOriginMat
        # fromOriginMat.invert()

        # self.tmpMgr.transform(
        #     resBody,
        #     fromOriginMat
        # )

        # self._draw_bodies([resBody])

        self.app.log(
            f'spun_profile_spin time:{time.time() - startTime}s'
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


    def _get_diff_body(
        self,
        bodyLst: list) -> fusion.BRepBody:
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
        self,
        bBox: core.OrientedBoundingBox3D,
        axis,
        radius: float) -> fusion.BRepFace:
        '''
        シリンダー面の取得
        '''

        # bBox: core.OrientedBoundingBox3D = self._get_boundingBox(
        #     self.body,
        #     self.axis.direction
        # )

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


    def _get_large_face(
        self,
        axis: core.InfiniteLine3D, 
        point: core.Point3D) -> fusion.BRepBody:
        '''
        巨大な平面の取得
        '''

        try:
            vec: core.Vector3D = axis.direction.copy()

            verificationPnt: core.Point3D = point.copy()
            insPnt: core.Point3D = self._get_intersect_point_from_infinite(
                verificationPnt,
                axis
            )
            largeVec: core.Vector3D = insPnt.vectorTo(verificationPnt)
            verificationPnt.translateBy(largeVec)

            points = []

            vec.scaleBy(self.largeValue)
            p: core.Point3D = verificationPnt.copy()
            p.translateBy(vec)
            points.append(p)

            vec.scaleBy(-1)
            p: core.Point3D = verificationPnt.copy()
            p.translateBy(vec)
            points.append(p)

            points.append(self._get_intersect_point_from_infinite(points[1], axis))
            points.append(self._get_intersect_point_from_infinite(points[0], axis))
            points.append(points[0])

            lines = [core.Line3D.create(p1, p2) for p1, p2 in zip(points, points[1:])]

            wireBody: fusion.BRepBody = None
            wireBody, _ = self.tmpMgr.createWireFromCurves(lines)

            return self.tmpMgr.createFaceFromPlanarWires([wireBody])
        except:
            self.app.log('Failed:\n{}'.format(traceback.format_exc()))
