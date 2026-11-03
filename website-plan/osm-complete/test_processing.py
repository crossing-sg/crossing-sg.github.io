import unittest
from shapely.geometry import LineString
from build import difference, grade


class Deduplication(unittest.TestCase):
    def test_partial_duplicate_keeps_missing_tail(self):
        result = difference(LineString([(0, 0), (20, 0)]), [LineString([(0, 0), (10, 0)])])
        self.assertAlmostEqual(result.length, 10)

    def test_reverse_duplicate_is_removed(self):
        self.assertTrue(difference(LineString([(0, 0), (20, 0)]), [LineString([(20, 0), (0, 0)])]).is_empty)

    def test_intersections_and_parallel_paths_are_retained(self):
        source = LineString([(0, 0), (20, 0)])
        for other in [LineString([(10, -20), (10, 20)]), LineString([(0, 2), (20, 2)])]:
            self.assertAlmostEqual(difference(source, [other]).length, 20)

    def test_near_alignment_and_grade_separation(self):
        source, ref = LineString([(0, 0), (20, 0)]), LineString([(0, .5), (20, .5)])
        self.assertTrue(difference(source, [ref]).is_empty)
        self.assertAlmostEqual(difference(source, [ref], fuzzy=False).length, 20)
        self.assertNotEqual(grade({'bridge': 'yes'}), grade({}))
        self.assertEqual(grade({'bridge': 'no', 'layer': '0'}), grade({}))


if __name__ == '__main__':
    unittest.main()
