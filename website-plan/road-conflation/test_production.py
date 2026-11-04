import tempfile
import unittest
from pathlib import Path
import sqlite3

from shapely.geometry import LineString
from conflate import Road,Config,Index
from production_policy import AUTO,REVIEW,NOT,eligibility
from production_match import global_connectivity,match_context
from production_registry import Registry


class FinalPolicyTests(unittest.TestCase):
    def test_named_nus_connector_can_be_supported_without_claiming_public(self):
        category,reason,evidence=eligibility('service',{'highway':'service','name':'Computing Drive','lanes':'2'},True,
                                             campus=True,connected=True,endpoint_links=2)
        self.assertEqual(category,AUTO);self.assertTrue(evidence['access_unknown']);self.assertFalse(evidence['public_access_certified'])

    def test_corridor_evidence_keeps_short_internal_connectors_in_scope(self):
        self.assertEqual(eligibility('service',{'highway':'service','name':'Research Link'},True,campus=True,connected=True,
                                     endpoint_links=2,corridor_supported=True)[0],AUTO)

    def test_supported_named_campus_dead_end_can_take_crossing_proposals(self):
        self.assertEqual(eligibility('service',{'highway':'service','name':'Science Drive 4','lanes':'2'},True,
                                     campus=True,connected=True,endpoint_links=1)[0],AUTO)

    def test_campus_does_not_override_private(self):
        self.assertEqual(eligibility('service',{'highway':'service','name':'Research Link','access':'private'},True,
                                     campus=True,connected=True,endpoint_links=2,corridor_supported=True)[0],REVIEW)

    def test_missing_access_and_generic_service_does_not_prove_permission(self):
        self.assertEqual(eligibility('service',{'highway':'service','lanes':'2'},True,connected=True,endpoint_links=2)[0],REVIEW)

    def test_parking_aisles_are_not_automatic(self):
        self.assertEqual(eligibility('service',{'highway':'service','service':'parking_aisle','access':'yes'},True,connected=True)[0],NOT)

    def test_private_driveway_is_not_automatic(self):
        self.assertEqual(eligibility('service',{'highway':'service','service':'driveway','access':'private'},True,connected=True)[0],NOT)

    def test_permissive_driveway_stays_review(self):
        self.assertEqual(eligibility('service',{'highway':'service','service':'driveway','access':'permissive'},True,connected=True)[0],REVIEW)

    def test_pedestrian_only_and_expressway_are_not_automatic(self):
        for kind in ['footway','cycleway','steps','motorway','motorway_link']:
            self.assertEqual(eligibility(kind,{'highway':kind},True,connected=True)[0],NOT)

    def test_explicit_foot_restriction_is_conservative(self):
        self.assertEqual(eligibility('residential',{'highway':'residential','foot':'no'},True,connected=True)[0],REVIEW)

    def test_parallel_geometry_remains_review(self):
        self.assertEqual(eligibility('residential',{'highway':'residential'},True,connected=True,
                                     match_reason='independent_parallel_source_topology')[0],REVIEW)

    def test_building_passage_is_grade_review(self):
        self.assertEqual(eligibility('residential',{'highway':'residential','tunnel':'building_passage'},True,connected=True)[0],REVIEW)

    def test_unverified_primary_identifier_not_automatic(self):
        self.assertEqual(eligibility('residential',{},False,connected=True)[0],REVIEW)


class TopologyTests(unittest.TestCase):
    def roads(self):
        ground=Road('g','osm','1',LineString([(0,0),(100,0)]),'residential',layer=0,bridge=False,tunnel=False)
        tunnel=Road('t','osm','2',LineString([(100,0),(200,0)]),'residential',layer=-1,bridge=False,tunnel=True)
        reference=Road('web','website','0',LineString([(0,0),(100,0)]),seg_id=0)
        return ground,tunnel,reference

    def test_shared_osm_node_connects_portal_without_collapsing_grade(self):
        ground,tunnel,reference=self.roads()
        topology={'g':{'node_ids':[1,42],'endpoint_nodes':[[1],[42]]},'t':{'node_ids':[42,3],'endpoint_nodes':[[42],[3]]}}
        index,connected,portals=global_connectivity([ground,tunnel],Index([reference]),Config(),topology)
        self.assertTrue(connected['t']);self.assertGreater(portals,0)

    def test_coordinate_only_grade_junction_does_not_connect(self):
        ground,tunnel,reference=self.roads()
        _,connected,portals=global_connectivity([ground,tunnel],Index([reference]),Config(),{})
        self.assertFalse(connected['t']);self.assertEqual(portals,0)

    def test_separated_crossing_is_not_noded(self):
        ground,_,reference=self.roads()
        bridge=Road('b','osm','3',LineString([(50,-50),(50,50)]),'residential',layer=1,bridge=True)
        _,connected,_=global_connectivity([ground,bridge],Index([reference]),Config(),{})
        self.assertFalse(connected['b'])

    def test_parallel_chunk_match_preserves_partial_extension(self):
        ground,_,reference=self.roads()
        source=Road('x','osm','4',LineString([(0,0),(200,0)]),'residential',layer=0)
        index,connected,_=global_connectivity([source],Index([reference]),Config(),{})
        p,f=match_context([source],Index([reference]),index,connected,Config())
        self.assertAlmostEqual(sum(r['length_m'] for r in f if r['fragment_kind']=='missing'),100)
        self.assertEqual(p[0]['status'],'partially_matched')


class PersistentRegistryTests(unittest.TestCase):
    def setUp(self):
        self.workspace=Path(__file__).resolve().parents[2]/'local-outputs/conflation/production-tests'
        self.workspace.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=self.workspace)
        self.assertTrue(Path(self.temp.name).resolve().is_relative_to(self.workspace.resolve()))
        self.registry=Registry(Path(self.temp.name)/'ids.sqlite')
        self.existing=[dict(uid='existing:0',seg_id=0,geometry_sha256='g0',source='existing'),dict(uid='existing:2',seg_id=2,geometry_sha256='g2',source='existing')]
        self.new=[dict(uid='b',geometry_sha256='gb',source='osm'),dict(uid='a',geometry_sha256='ga',source='osm')]
    def tearDown(self):self.registry.close();self.temp.cleanup()

    def test_no_reuse_of_existing_holes_and_sorted_allocation(self):
        ids,added=self.registry.allocate(self.existing,self.new,'run1')
        self.assertEqual(ids['a'],3);self.assertEqual(ids['b'],4);self.assertEqual(added,2)

    def test_repeated_run_retains_all_ids_without_allocations(self):
        a,_=self.registry.allocate(self.existing,self.new,'run1')
        b,added=self.registry.allocate(self.existing,list(reversed(self.new)),'run1')
        self.assertEqual(a,b);self.assertEqual(added,0)

    def test_retired_ids_never_reused(self):
        self.registry.allocate(self.existing,self.new,'run1')
        ids,_=self.registry.allocate(self.existing,[dict(uid='c',geometry_sha256='gc',source='osm')],'run2')
        self.assertEqual(ids['c'],5)

    def test_geometry_mutation_rejects_and_rolls_back(self):
        self.registry.allocate(self.existing,self.new,'run1')
        with self.assertRaises(ValueError):self.registry.allocate(self.existing,[dict(uid='a',geometry_sha256='changed',source='osm')],'run2')
        self.assertEqual(self.registry.db.execute("SELECT geometry_sha256 FROM segments WHERE uid='a'").fetchone()[0],'ga')

    def test_numeric_collision_is_rejected(self):
        self.registry.allocate(self.existing,self.new,'run1')
        with self.assertRaises(sqlite3.IntegrityError):self.registry.allocate(self.existing+[dict(uid='other',seg_id=3,geometry_sha256='x',source='existing')],self.new,'run2')

    def test_duplicate_candidate_uid_is_rejected(self):
        with self.assertRaises(ValueError):self.registry.allocate(self.existing,[self.new[0],self.new[0]],'run1')


if __name__=='__main__':unittest.main(verbosity=2)
