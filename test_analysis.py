import unittest
from pathlib import Path
import pandas as pd
from analysis import read_csv_bytes, guess, ALIASES, prepare, number, safe_csv

class CSVTests(unittest.TestCase):
    def test_sample_total_and_top10(self):
        df = read_csv_bytes(Path(__file__).with_name('サンプル.csv').read_bytes())
        mapping = {key: guess(df.columns, key) for key in ALIASES}
        original, metrics, count = prepare(df, mapping)
        self.assertEqual(count, 1)
        self.assertEqual(len(original), 12)
        top = metrics.sort_values('再生数', ascending=False).head(10)
        self.assertEqual(len(top), 10)
        self.assertEqual(top.iloc[0]['再生数'], 48000)
        self.assertEqual(metrics['再生数'].sum(), 364800)

    def test_english_and_quoted_numeric(self):
        df = read_csv_bytes(b'Video title,Views,Impressions click-through rate (%)\nTotal,2000,6\nExample,"1,234",6.5%\n')
        original, metrics, count = prepare(df, {k: guess(df.columns,k) for k in ALIASES})
        self.assertEqual(count, 1)
        self.assertEqual(metrics.iloc[0]['再生数'], 1234)
        self.assertEqual(metrics.iloc[0]['クリック率（%）'], 6.5)

    def test_encodings_and_delimiters(self):
        for enc in ('cp932', 'utf-16', 'utf-8-sig'):
            with self.subTest(encoding=enc):
                df = read_csv_bytes('動画のタイトル;視聴回数\n父の手紙;123\n'.encode(enc))
                self.assertEqual(df.iloc[0,0], '父の手紙')
                self.assertEqual(df.shape, (1,2))

    def test_cp932_even_length(self):
        df = read_csv_bytes('動画のタイトル,視聴回数\n父,12\n'.encode('cp932'))
        self.assertEqual(df.iloc[0,0], '父')

    def test_missing_values_not_zero(self):
        values = number(pd.Series(['', '-', 'abc', '0', '1,234', '５.５％', '-1', 'inf']))
        self.assertEqual(values.isna().sum(), 5)
        self.assertEqual(values.iloc[3], 0)
        self.assertEqual(values.iloc[4], 1234)
        self.assertEqual(values.iloc[5], 5.5)

    def test_bad_inputs_and_mapping(self):
        for data in (b'', b'a,b\n', b' ' * (20*1024*1024+1)):
            with self.assertRaises(ValueError):
                read_csv_bytes(data)
        df = pd.DataFrame({'a':['x'], 'b':['2']})
        with self.assertRaises(ValueError):
            prepare(df, {'動画タイトル':None})
        with self.assertRaises(ValueError):
            prepare(df, {'動画タイトル':'a', '再生数':'a'})

    def test_csv_formula_safety(self):
        content = safe_csv(pd.DataFrame({'名前':['=1+1', '通常', ' @SUM(A1)']})).decode('utf-8-sig')
        self.assertIn("'=1+1", content)
        self.assertIn("' @SUM(A1)", content)
        self.assertIn('通常', content)

if __name__ == '__main__':
    unittest.main()
