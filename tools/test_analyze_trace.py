import unittest
import analyze_trace as subject


class InputLogTests(unittest.TestCase):
    def test_counts_use_new_sample_denominator(self):
        rows = subject.parse_trace("0,1,1,900\n50,0,1,1\n100,1,0,0\n150,1,1,200\n200,0,0,0\n")
        result = subject.summarize(rows, "synthetic")
        self.assertEqual(result["valid_new_sample_count"], 2)
        self.assertEqual(result["invalid_new_sample_count"], 1)
        self.assertEqual(result["no_new_sample_rows"], 2)
        self.assertEqual(result["invalid_fraction_of_new_samples"], 1 / 3)
        self.assertEqual(result["largest_valid_sample_interval_ms"], 150)
        self.assertEqual(result["tail_after_last_valid_ms"], 50)
        self.assertEqual(result["distance_mm"], {"minimum": 200, "maximum": 900, "median": 550})

    def test_no_valid_data_is_unknown_not_zero(self):
        result = subject.summarize(subject.parse_trace("0,0,0,0\n50,0,0,0\n"))
        self.assertIsNone(result["invalid_fraction_of_new_samples"])
        self.assertIsNone(result["distance_mm"]["minimum"])
        self.assertIsNone(result["largest_valid_sample_interval_ms"])

    def test_single_row_has_no_interval(self):
        result = subject.summarize(subject.parse_trace("99,1,1,65535"))
        self.assertEqual(result["observation_span_ms"], 0)
        self.assertIsNone(result["largest_record_interval_ms"])

    def test_bom_comments_and_bounds(self):
        rows = subject.parse_trace("\ufeff# sample\n\n 4294967295 , 1 , 1 , 65535\n")
        self.assertEqual(rows, [(4294967295, 1, 1, 65535)])

    def test_reject_ambiguous_or_corrupt_input(self):
        for content in ("", "# only comment", "-1,1,1,2", "0,2,1,2", "0,1,1,65536",
                        "4294967296,1,1,2", "0,1,1,2,3", "0,1,1,2\x00junk",
                        "0,1,1,2\n0,1,1,2", "1,1,1,2\n0,1,1,2", "0,1,1,2\v1,1,1,2",
                        "0,1,1," + "9" * 200):
            with self.subTest(content=content[:40]):
                with self.assertRaises(ValueError):
                    subject.parse_trace(content)

    def test_source_label_and_metadata_cannot_end_code_block(self):
        result = subject.summarize(subject.parse_trace("0,1,1,1"), "synthetic", "```\nmisleading")
        result["source_sha256"] = "test"
        text = subject.markdown(result)
        self.assertIn("模拟数据（不得作为实物证据）", text)
        self.assertEqual(text.count("```"), 2)


if __name__ == "__main__":
    unittest.main()
