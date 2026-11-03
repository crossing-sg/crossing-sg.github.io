"""Synthetic failure-mode tests: run with the configured local Python interpreter."""
import unittest
import tempfile
from pathlib import Path
from dataclasses import replace

from shapely.geometry import LineString

from conflate import (Config, Index, Road, candidate_duplicate_review, geom_key,
                      match_stage, preview_network, validate, write_package)


def road(uid, coords, **kwargs):
    return Road(uid=uid, source='processed_lta', source_id=uid,
                geometry=LineString(coords), road_class='residential',
                layer=0, bridge=False, tunnel=False, source_geometry_key=geom_key(LineString(coords)), **kwargs)


def reference(uid, coords, **kwargs):
    return Road(uid=uid, source='website', source_id=uid, geometry=LineString(coords),
                seg_id=int(uid), **kwargs)


class MatchingTests(unittest.TestCase):
    def setUp(self):
        self.reference = [reference('1',[(0,0),(100,0)])]
        self.config = Config()

    def match(self, sources, refs=None, config=None):
        return match_stage(sources,Index(self.reference if refs is None else refs),config or self.config)

    def test_small_displacement_matches_using_direction_and_length(self):
        p,f=self.match([road('a',[(0,2),(100,2)])])
        self.assertEqual(p[0]['status'],'matched')
        self.assertAlmostEqual(sum(r['length_m'] for r in f),100)

    def test_displaced_or_parallel_is_uncertain_not_automatically_deleted(self):
        p,f=self.match([road('a',[(0,7),(100,7)])])
        self.assertEqual(p[0]['status'],'uncertain')
        self.assertIn('displacement_or_parallel',p[0]['reason'])

    def test_parallel_with_coexisting_sibling_and_connections_is_retained(self):
        sources=[road('sibling',[(0,0),(100,0)]),road('parallel',[(0,7),(100,7)]),
                 road('left',[(0,0),(0,7)]),road('right',[(100,0),(100,7)])]
        p,f=self.match(sources)
        parallel=next(r for r in p if r['uid']=='parallel')
        self.assertTrue(parallel['parallel_evidence'])
        self.assertEqual(parallel['status'],'unmatched')
        self.assertAlmostEqual(sum(r['length_m'] for r in f if r['uid']=='parallel' and r['fragment_kind']=='missing'),100)

    def test_partial_overlap_preserves_missing_extension(self):
        p,f=self.match([road('a',[(0,0),(200,0)])])
        self.assertEqual(p[0]['status'],'partially_matched')
        missing=[r for r in f if r['fragment_kind']=='missing']
        self.assertAlmostEqual(sum(r['length_m'] for r in missing),100)
        self.assertAlmostEqual(missing[0]['from_m'],100)

    def test_middle_gap_is_not_removed_by_buffers(self):
        refs=[reference('1',[(0,0),(40,0)]),reference('2',[(60,0),(100,0)])]
        p,f=self.match([road('a',[(0,0),(100,0)])],refs)
        self.assertAlmostEqual(sum(r['length_m'] for r in f if r['fragment_kind']=='missing'),20)

    def test_crossing_at_right_angle_is_not_duplicate(self):
        p,f=self.match([road('a',[(50,-50),(50,50)])])
        self.assertEqual(p[0]['matched_m'],0)

    def test_t_junction_continuation_not_matched_to_end_cap(self):
        p,f=self.match([road('a',[(100,0),(200,0)])])
        self.assertEqual(p[0]['status'],'unmatched')
        self.assertEqual(p[0]['matched_m'],0)

    def test_many_website_segments_can_cover_one_source(self):
        refs=[reference('1',[(0,0),(50,0)]),reference('2',[(50,0),(100,0)])]
        p,f=self.match([road('a',[(0,0),(100,0)])],refs)
        self.assertEqual(p[0]['status'],'matched')
        self.assertIn('website',p[0]['reference_sources'])

    def test_known_grade_separation_not_duplicate(self):
        elevated=replace(road('a',[(0,0),(100,0)]),layer=1,bridge=True)
        ground=replace(self.reference[0],layer=0,bridge=False,tunnel=False)
        p,f=self.match([elevated],[ground])
        self.assertEqual(p[0]['matched_m'],0)
        self.assertIn('no_grade_compatible_reference_connection',p[0]['reason'])

    def test_missing_website_grade_metadata_requires_review(self):
        elevated=replace(road('a',[(0,0),(100,0)]),layer=1,bridge=True)
        p,f=self.match([elevated])
        self.assertEqual(p[0]['status'],'uncertain')
        self.assertIn('reference_grade_unknown',p[0]['reason'])

    def test_footway_excluded_from_crossing_road_additions(self):
        p,f=self.match([replace(road('a',[(100,0),(200,0)]),road_class='footway')])
        self.assertEqual(p[0]['status'],'excluded')
        self.assertFalse(f)

    def test_uncertain_reference_does_not_become_confirmed(self):
        uncertain=replace(self.reference[0],confidence='uncertain',source='processed_lta')
        p,f=self.match([road('a',[(0,0),(100,0)])],[uncertain])
        self.assertEqual(p[0]['status'],'uncertain')
        self.assertIn('overlaps_unresolved_primary',p[0]['reason'])

    def test_tolerances_change_retrieval_but_not_prove_duplication(self):
        source=road('a',[(0,7),(100,7)])
        p5,_=self.match([source],config=replace(self.config,tolerance_m=5))
        p10,_=self.match([source],config=replace(self.config,tolerance_m=10))
        self.assertEqual(p5[0]['matched_m'],0)
        self.assertEqual(p10[0]['matched_m'],0)
        self.assertIn('displacement_or_parallel',p10[0]['reason'])

    def test_deterministic_uids_and_existing_id_integrity(self):
        sources=[road('a',[(0,0),(200,0)])]
        p,f=self.match(sources)
        p2,f2=self.match(sources)
        self.assertEqual([r['fragment_uid'] for r in f],[r['fragment_uid'] for r in f2])
        preview=preview_network(self.reference,f)
        result=validate(self.reference,p,f,preview,[])
        self.assertTrue(result['passed'])
        self.assertEqual([r['seg_id'] for r in preview if r['role']=='existing'],[1])

    def test_exact_source_duplicates_not_added_twice(self):
        p,f=self.match([road('a',[(100,0),(200,0)]),road('b',[(100,0),(200,0)])])
        self.assertEqual(p[1]['reason'],'exact_duplicate_in_same_source')
        self.assertAlmostEqual(sum(r['length_m'] for r in f if r['fragment_kind']=='missing'),100)

    def test_candidate_overlap_does_not_erase_long_extension(self):
        def fragment(uid,coords):
            return dict(fragment_kind='missing',dataset='processed_lta',fragment_uid=uid,
                        parent_uid=uid,geometry=LineString(coords),reason='test')
        fragments=[fragment('a',[(0,0),(20,0)]),fragment('b',[(0,0),(100,0)])]
        candidate_duplicate_review(fragments,self.config)
        self.assertEqual(fragments[1]['fragment_kind'],'missing')

    def test_tight_tolerance_has_wider_ambiguity_guard(self):
        sources=[road('offset',[(0,7),(100,7)]),road('link',[(0,0),(0,7)])]
        p,f=self.match(sources,config=replace(self.config,tolerance_m=5))
        value=next(r for r in p if r['uid']=='offset')
        self.assertEqual(value['missing_m'],0)
        self.assertIn('aligned_line_outside_match_radius',value['reason'])

    def test_preview_has_no_floating_point_zero_length_tail(self):
        line=LineString([(0,0),(50.000000000001,0)])
        fragment=dict(fragment_kind='missing',fragment_uid='tail',geometry=line)
        rows=preview_network([], [fragment])
        self.assertEqual(len(rows),1)
        self.assertTrue(rows[0]['geometry'].is_valid)

    def test_trunk_class_missing_section_requires_category_review(self):
        p,f=self.match([replace(road('a',[(100,0),(200,0)]),road_class='trunk_link')])
        self.assertEqual(p[0]['status'],'uncertain')
        self.assertIn('class_or_access_requires_review',p[0]['reason'])

    def test_empty_aoi_layers_export_and_reopen(self):
        workspace=Path(__file__).resolve().parents[2]/'local-outputs/conflation/tests'
        workspace.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=workspace) as directory:
            self.assertTrue(Path(directory).resolve().is_relative_to(workspace.resolve()))
            counts=write_package(Path(directory)/'empty.gpkg',[],[],[],[],[],[],None)
            self.assertEqual(counts['website_roads'],0)
            self.assertEqual(counts['candidate_supplements'],0)

    def test_unknown_source_tunnel_is_not_assumed_same_as_known_reference(self):
        source=replace(road('a',[(0,0),(100,0)]),tunnel=None,layer=None)
        ref=replace(self.reference[0],tunnel=True,layer=-1,bridge=False)
        p,f=self.match([source],[ref])
        self.assertEqual(p[0]['status'],'uncertain')
        self.assertIn('reference_grade_unknown',p[0]['reason'])

    def test_sparse_short_reference_stubs_do_not_cover_a_long_road(self):
        refs=[reference(str(i+1),[(i*5+1.25,0),(i*5+3.75,0)]) for i in range(20)]
        p,f=self.match([road('a',[(0,0),(100,0)])],refs)
        self.assertEqual(p[0]['matched_m'],0)
        self.assertIn('insufficient_continuous_overlap',p[0]['reason'])


if __name__=='__main__':
    unittest.main(verbosity=2)
