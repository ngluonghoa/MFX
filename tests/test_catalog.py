import unittest
from forex_trading.catalog import ZONES, catalog_counts, validate_catalog
from forex_trading.model import ZoneDefinition, ZonePurpose as P


class CatalogTests(unittest.TestCase):
    def test_approved_catalog_counts(self):
        self.assertEqual(len(ZONES), 18)
        self.assertEqual(catalog_counts(ZONES), {
            P.ENTRY_LONG_CANDIDATE: 7,
            P.ENTRY_SHORT_CANDIDATE: 8,
            P.WATCH_ONLY: 1,
            P.EXIT_LONG_WARNING_ONLY: 2,
        })

    def test_research_only_b9_excluded(self):
        self.assertNotIn("FX-B9", {z.label for z in ZONES})

    def test_nonentry_labels(self):
        lookup = {z.label: z.purpose for z in ZONES}
        self.assertEqual(lookup["B7"], P.WATCH_ONLY)
        self.assertEqual(lookup["S3"], P.EXIT_LONG_WARNING_ONLY)
        self.assertEqual(lookup["S8"], P.EXIT_LONG_WARNING_ONLY)

    def test_duplicate_label_rejected(self):
        with self.assertRaises(ValueError):
            validate_catalog(ZONES + (ZONES[0],))

    def test_unapproved_b9_rejected(self):
        with self.assertRaises(ValueError):
            validate_catalog(ZONES + (ZoneDefinition("FX-B9", "F8", P.ENTRY_LONG_CANDIDATE),))

    def test_no_artificial_quota(self):
        proposed = ZONES + (ZoneDefinition("FUTURE-WATCH", "FUTURE", P.WATCH_ONLY),)
        self.assertEqual(catalog_counts(proposed)[P.WATCH_ONLY], 2)
