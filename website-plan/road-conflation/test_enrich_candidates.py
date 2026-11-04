"""Failure-mode tests for tag association, access decisions and grouped review."""
import json
import unittest

import geopandas as gpd
from shapely.geometry import LineString
from shapely.strtree import STRtree

from enrich_candidates import (A,B,C,classify_enriched,effective_access,geometry_evidence,
                               grouping_partition,link_one,make_groups,make_review_batches,service_evidence)


class EnrichmentTests(unittest.TestCase):
    def base(self,**kwargs):return {'tags_applied':True,'road_class':'service',**kwargs}

    def test_id_requires_geometric_support(self):
        self.assertFalse(geometry_evidence(LineString([(0,10),(100,10)]),LineString([(0,0),(100,0)]))['accepted'])

    def test_fragment_can_map_to_part_of_a_long_way(self):
        self.assertTrue(geometry_evidence(LineString([(20,0),(80,0)]),LineString([(0,0),(100,0)]))['accepted'])

    def test_perpendicular_crossing_does_not_validate_id(self):
        self.assertFalse(geometry_evidence(LineString([(50,-20),(50,20)]),LineString([(0,0),(100,0)]))['accepted'])

    def test_reversed_fragment_still_links(self):
        self.assertTrue(geometry_evidence(LineString([(80,0),(20,0)]),LineString([(0,0),(100,0)]))['accepted'])

    def test_unique_geometry_fallback_does_not_trust_wrong_id(self):
        ways=gpd.GeoDataFrame([dict(way_id=1,highway='service',name='Lane',all_tags_json='{"highway":"service"}',node_ids_json='[]',osm_version=1,osm_timestamp='',geometry=LineString([(0,10),(100,10)])),
                               dict(way_id=2,highway='service',name='Lane',all_tags_json='{"highway":"service","access":"private"}',node_ids_json='[]',osm_version=1,osm_timestamp='',geometry=LineString([(0,0),(100,0)]))],crs=3414)
        row=gpd.GeoDataFrame([dict(source_id='1',road_class='service',name='Lane',fragment_uid='a',geometry=LineString([(10,0),(90,0)]))],crs=3414).iloc[0]
        match=link_one(row,ways,{1:0,2:1},STRtree(ways.geometry.to_numpy()))
        self.assertEqual(match['match_method'],'unique_spatial_fallback')
        self.assertEqual(match['matched_way_id'],2)
        self.assertEqual(match['osm_access'],'private')

    def test_missing_access_does_not_promote_service(self):
        category,_=classify_enriched(self.base(),{'highway':'service','name':'Computing Drive','lanes':'2','sidewalk':'both'})
        self.assertEqual(category,C)

    def test_positive_access_and_route_evidence_can_promote(self):
        category,_=classify_enriched(self.base(),{'highway':'service','access':'permissive','lanes':'2'})
        self.assertEqual(category,A)

    def test_parking_aisle_stays_review_even_with_positive_access(self):
        category,_=classify_enriched(self.base(),{'highway':'service','service':'parking_aisle','access':'yes','lanes':'2'})
        self.assertEqual(category,C)

    def test_private_driveway_remains_review_not_deleted(self):
        category,_=classify_enriched(self.base(),{'highway':'service','service':'driveway','access':'private'})
        self.assertEqual(category,C)

    def test_foot_no_can_downgrade_a_residential_candidate(self):
        category,_=classify_enriched(self.base(road_class='residential'),{'highway':'residential','foot':'no'})
        self.assertEqual(category,C)

    def test_effective_motor_access_uses_specific_tag_first(self):
        self.assertEqual(effective_access({'access':'yes','vehicle':'destination','motor_vehicle':'no'},['motor_vehicle','vehicle','access']),('no','motor_vehicle'))

    def test_conflicting_private_general_access_not_silently_public(self):
        category,_=classify_enriched(self.base(),{'highway':'service','access':'private','motor_vehicle':'yes','lanes':'2'})
        self.assertEqual(category,C)

    def test_geometry_uncertainty_overrides_positive_permission(self):
        category,_=classify_enriched(self.base(spatial_flag='possible_parallel'),{'highway':'service','access':'yes','lanes':'2'})
        self.assertEqual(category,C)

    def test_barrier_restriction_overrides_permission(self):
        self.assertEqual(classify_enriched(self.base(barrier_restriction=True),{'highway':'service','access':'yes','lanes':'2'})[0],C)

    def test_no_trusted_link_means_no_tag_classification(self):
        self.assertEqual(classify_enriched(self.base(tags_applied=False),{'highway':'service','access':'yes','lanes':'2'})[0],C)

    def test_highway_change_requires_review(self):
        self.assertEqual(classify_enriched(self.base(class_conflict=True),{'highway':'footway'})[0],C)

    def test_named_campus_unknown_is_prioritised_not_called_public(self):
        self.assertEqual(service_evidence({'highway':'service','name':'Computing Drive'},True),'service_purpose_or_access_insufficient')

    def test_road_grouping_reduces_connected_named_fragments(self):
        rows=[]
        for n,(a,b) in enumerate([(0,40),(40,80)]):
            rows.append(dict(fragment_uid=f'f{n}',matched_way_id=n+1,source_id=str(n+1),osm_name='Computing Drive',name='Computing Drive',
                             osm_node_ids_json=json.dumps([n,n+1]),osm_layer='',osm_bridge='',osm_tunnel='',
                             osm_service='',osm_access='',enrichment_decision='no_positive_motor_access_tag',barrier_restriction=False,match_max_offset_m=0.,
                             enriched_category=C,service_group='service_purpose_or_access_insufficient',effective_motor_access='unknown',effective_foot_access='unknown',
                             match_method='identifier_plus_geometry',spatial_flag='',parallel_evidence=False,length_m=b-a,geometry=LineString([(a,0),(b,0)])))
        data=gpd.GeoDataFrame(rows,crs=3414)
        members,groups,ways=make_groups(data)
        self.assertEqual(len(groups),1)
        self.assertEqual(groups.iloc[0].interval_count,2)
        self.assertEqual(groups.iloc[0].priority,1)
        self.assertEqual(members.fragment_uid.tolist(),['f0','f1'])

    def test_non_general_foot_restriction_requires_review(self):
        self.assertEqual(classify_enriched(self.base(road_class='residential'),{'highway':'residential','foot':'customers'})[0],C)

    def test_multiple_qualifying_fallbacks_do_not_supply_tags(self):
        rows=[]
        for way_id,y in [(1,10),(2,0),(3,0)]:
            rows.append(dict(way_id=way_id,highway='service',name='Lane',all_tags_json='{"highway":"service","access":"private"}',
                             node_ids_json='[]',osm_version=1,osm_timestamp='',geometry=LineString([(0,y),(100,y)])))
        ways=gpd.GeoDataFrame(rows,crs=3414)
        row=gpd.GeoDataFrame([dict(source_id='1',road_class='service',name='Lane',fragment_uid='x',geometry=LineString([(10,0),(90,0)]))],crs=3414).iloc[0]
        link=link_one(row,ways,{1:0,2:1,3:2},STRtree(ways.geometry.to_numpy()))
        self.assertFalse(link['tags_applied'])
        self.assertEqual(link['fallback_qualified_count'],2)
        self.assertEqual(link['osm_access'],'')

    def test_distinct_private_parking_and_driveway_partitions(self):
        common=dict(enriched_category=C,review_name='',service_group='explicit_access_restriction',effective_motor_access='private',
                    effective_foot_access='private',match_method='identifier_plus_geometry',spatial_flag='',parallel_evidence=False,
                    geometry=LineString([(0,0),(10,0)]))
        a=gpd.GeoDataFrame([{**common,'osm_service':'driveway'}],crs=3414).iloc[0]
        b=gpd.GeoDataFrame([{**common,'osm_service':'parking_aisle'}],crs=3414).iloc[0]
        self.assertNotEqual(grouping_partition(a),grouping_partition(b))

    def test_policy_batch_membership_keeps_every_uncertain_interval(self):
        rows=[]
        for n,x in enumerate([0,100]):
            rows.append(dict(fragment_uid=f'f{n}',matched_way_id=n+1,source_id=str(n+1),osm_name='',name='',osm_node_ids_json='[]',
                             osm_layer='',osm_bridge='',osm_tunnel='',osm_service='driveway',osm_access='private',
                             enriched_category=C,service_group='explicit_access_restriction',effective_motor_access='private',effective_foot_access='private',
                             match_method='identifier_plus_geometry',spatial_flag='',parallel_evidence=False,length_m=10.,
                             enrichment_decision='explicit_motor_access_private',barrier_restriction=False,match_max_offset_m=0.,geometry=LineString([(x,0),(x+10,0)])))
        data=gpd.GeoDataFrame(rows,crs=3414)
        data,groups,_=make_groups(data)
        self.assertEqual(len(groups),2)
        members,groups,batches=make_review_batches(data,groups)
        self.assertEqual(len(batches),1)
        self.assertEqual(batches.iloc[0].interval_count,2)
        self.assertEqual(members.fragment_uid.tolist(),['f0','f1'])
        self.assertTrue(members.review_batch_id.nunique()==1)

    def test_grouping_does_not_mix_access_regimes(self):
        rows=[]
        for n,access in enumerate(['unknown','private']):
            rows.append(dict(enriched_category=C,review_name='Campus Road',service_group='service_purpose_or_access_insufficient',
                             effective_motor_access=access,effective_foot_access='unknown',match_method='identifier_plus_geometry',
                             spatial_flag='',parallel_evidence=False,geometry=LineString([(n*10,0),(n*10+10,0)])))
        self.assertNotEqual(grouping_partition(gpd.GeoDataFrame(rows,crs=3414).iloc[0]),grouping_partition(gpd.GeoDataFrame(rows,crs=3414).iloc[1]))


if __name__=='__main__':unittest.main(verbosity=2)
