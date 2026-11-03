"""Tests for classification safety and the independent NUS matching audit."""
import unittest
import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString

from refine_candidates import A,B,C,classify,decide,spatial_audit


class ClassificationTests(unittest.TestCase):
    def test_residential_road_is_provisionally_eligible(self):
        self.assertEqual(decide({'road_class':'residential'})[0],A)

    def test_nonroad_modes_are_excluded(self):
        for kind in ['footway','cycleway','steps','pedestrian','path']:
            with self.subTest(kind=kind):self.assertEqual(decide({'road_class':kind})[0],B)

    def test_unknown_service_is_reviewed(self):
        self.assertEqual(decide({'road_class':'service'})[0],C)

    def test_campus_name_does_not_prove_service_access(self):
        self.assertEqual(decide({'road_class':'service','name':'Computing Drive'})[0],C)

    def test_parking_aisle_is_reviewed_not_deleted(self):
        self.assertEqual(decide({'road_class':'service'},{'service':'parking_aisle','access':'yes'})[0],C)

    def test_private_residential_is_not_accepted(self):
        self.assertEqual(decide({'road_class':'residential'},{'access':'private'})[0],C)

    def test_private_driveway_is_reviewed(self):
        self.assertEqual(decide({'road_class':'service'},{'service':'driveway','access':'private'})[0],C)

    def test_clear_access_and_supported_service_subtype_can_be_eligible(self):
        self.assertEqual(decide({'road_class':'service'},{'access':'yes','service':'alley'})[0],A)

    def test_positive_access_alone_does_not_establish_service_subtype(self):
        self.assertEqual(decide({'road_class':'service'},{'access':'yes'})[0],C)

    def test_parallel_evidence_keeps_a_road_for_review(self):
        self.assertEqual(decide({'road_class':'residential','parallel_evidence':True})[0],C)

    def test_spatial_flag_overrides_a_residential_class(self):
        self.assertEqual(decide({'road_class':'residential','spatial_flag':'possible_displacement'})[0],C)

    def test_unresolved_parent_not_accepted_based_on_missing_fragment_alone(self):
        self.assertEqual(decide({'road_class':'residential','parent_uncertain_m':20})[0],C)

    def test_grade_and_boundary_concerns_are_reviewed(self):
        for field in [{'bridge':True},{'layer':1},{'boundary':True}]:
            self.assertEqual(decide({'road_class':'residential',**field})[0],C)

    def test_unknown_and_ramp_classes_are_reviewed(self):
        for kind in ['primary_link','secondary_link','unknown','track']:
            self.assertEqual(decide({'road_class':kind})[0],C)

    def test_wide_parallel_alignment_is_flagged_for_review(self):
        source=gpd.GeoDataFrame({'fragment_uid':['x'],'geometry':[LineString([(0,25),(100,25)])]},crs=3414)
        reference=gpd.GeoDataFrame({'geometry':[LineString([(0,0),(100,0)])]},crs=3414)
        result=spatial_audit(source,reference).iloc[0]
        self.assertEqual(result.spatial_flag,'possible_wide_displacement_or_parallel_within_30m')

    def test_crossing_at_right_angles_is_not_a_parallel_duplicate(self):
        source=gpd.GeoDataFrame({'fragment_uid':['x'],'geometry':[LineString([(50,-50),(50,50)])]},crs=3414)
        reference=gpd.GeoDataFrame({'geometry':[LineString([(0,0),(100,0)])]},crs=3414)
        self.assertEqual(spatial_audit(source,reference).iloc[0].spatial_flag,'')

    def test_genuinely_distant_road_is_not_spatially_flagged(self):
        source=gpd.GeoDataFrame({'fragment_uid':['x'],'geometry':[LineString([(0,100),(100,100)])]},crs=3414)
        reference=gpd.GeoDataFrame({'geometry':[LineString([(0,0),(100,0)])]},crs=3414)
        self.assertEqual(spatial_audit(source,reference).iloc[0].spatial_flag,'')

    def test_close_existing_representation_is_not_accepted(self):
        source=gpd.GeoDataFrame({'fragment_uid':['x'],'geometry':[LineString([(0,2),(100,2)])]},crs=3414)
        reference=gpd.GeoDataFrame({'geometry':[LineString([(0,0),(100,0)])]},crs=3414)
        self.assertEqual(spatial_audit(source,reference).iloc[0].spatial_flag,'possible_duplicate_existing_road')


if __name__=='__main__':
    unittest.main(verbosity=2)
