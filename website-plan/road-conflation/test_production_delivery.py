"""Delivery safety cases: partial duplicates, precision and tile boundaries."""
import json,tempfile,unittest
from pathlib import Path
from shapely.geometry import LineString,MultiLineString

from conflate import ROOT,Road
from production_delivery import audit_additions,piece_ranges,rounded_geometry,write_delivery,same_line_coordinates
from production_policy import AUTO,REVIEW


class DeliveryTests(unittest.TestCase):
    def test_gpkg_single_part_promotion_preserves_coordinates(self):
        line=LineString([(1,2),(3,4)])
        self.assertTrue(same_line_coordinates(MultiLineString([line]),line))
        self.assertFalse(same_line_coordinates(MultiLineString([LineString([(1,2),(3,4.1)])]),line))

    def test_tiny_tail_is_balanced(self):
        ranges=piece_ranges(100.001)
        self.assertEqual(len(ranges),3)
        self.assertTrue(all(2<b-a<=50 for a,b in ranges))
        self.assertAlmostEqual(sum(b-a for a,b in ranges),100.001)

    def test_precision_does_not_collapse_two_metre_road(self):
        geometry=rounded_geometry(LineString([(21000,31000),(21002,31000)]))
        self.assertEqual(len(geometry['coordinates']),2)
        self.assertNotEqual(*geometry['coordinates'])

    def test_partial_overlap_does_not_delete_missing_extension(self):
        existing=[Road('old','website','0',LineString([(0,0),(20,0)]),seg_id=0)]
        row=dict(fragment_uid='candidate',geometry=LineString([(0,.1),(100,.1)]),category=AUTO,eligibility_reason='test')
        self.assertEqual(audit_additions([row],existing),[])
        self.assertEqual(row['category'],AUTO)

    def test_near_whole_overlap_is_quarantined_and_retained(self):
        existing=[Road('old','website','0',LineString([(0,0),(100,0)]),seg_id=0)]
        row=dict(fragment_uid='candidate',geometry=LineString([(10,.1),(90,.1)]),category=AUTO,eligibility_reason='test')
        self.assertEqual(len(audit_additions([row],existing)),1)
        self.assertEqual(row['category'],REVIEW)
        self.assertEqual(row['geometry'].length,80)

    def test_parallel_road_eight_metres_away_is_not_distance_only_duplicate(self):
        existing=[Road('old','website','0',LineString([(0,0),(100,0)]),seg_id=0)]
        row=dict(fragment_uid='candidate',geometry=LineString([(10,8),(90,8)]),category=AUTO,eligibility_reason='test')
        self.assertEqual(audit_additions([row],existing),[])

    def test_transverse_crossing_is_not_duplicate(self):
        existing=[Road('old','website','0',LineString([(-50,0),(50,0)]),seg_id=0)]
        row=dict(fragment_uid='candidate',geometry=LineString([(0,-10),(0,10)]),category=AUTO,eligibility_reason='test')
        self.assertEqual(audit_additions([row],existing),[])

    def test_tile_edge_keeps_whole_feature_and_id(self):
        folder=ROOT/'local-outputs/conflation/singapore-production/test-work';folder.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=folder) as temp:
            road=Road('old','website','42',LineString([(19990,31000),(20010,31000)]),seg_id=42)
            original=dict(type='Feature',properties={'seg_id':42,'dist_m':0,'legacy':'preserve'},geometry=rounded_geometry(road.geometry))
            manifest,features=write_delivery(temp,[original],[],[road],'test')
            self.assertEqual(features,[original]);self.assertEqual(len(manifest['tiles']),2)
            for tile in manifest['tiles']:
                actual=json.loads((Path(temp)/'delivery'/tile['url']).read_text())
                self.assertEqual(actual['features'],[original])
            block=json.loads((Path(temp)/'delivery/id-blocks/0.json').read_text())
            self.assertEqual(len(block['42']['tiles']),2)


if __name__=='__main__':unittest.main(verbosity=2)
