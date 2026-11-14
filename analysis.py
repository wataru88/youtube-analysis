"""YouTube Studio CSVの読み込みと集計。外部通信やファイル保存は行わない。"""
import csv
import io
import unicodedata
import pandas as pd

ALIASES = {
    '動画タイトル': ['動画のタイトル', '動画タイトル', 'タイトル', 'Video title', 'Title'],
    '動画ID': ['コンテンツ', '動画ID', '動画 ID', 'Video', 'Video ID', 'Content'],
    '再生数': ['視聴回数', '再生数', 'Views'],
    'クリック率（%）': ['インプレッションのクリック率 (%)', 'インプレッションのクリック率（%）', 'インプレッションのクリック率', 'Impressions click-through rate (%)', 'Impressions click-through rate'],
    '平均視聴時間': ['平均視聴時間', 'Average view duration'],
    '平均再生率（%）': ['平均再生率 (%)', '平均再生率（%）', '平均再生率', 'Average percentage viewed (%)', 'Average percentage viewed'],
    'インプレッション数': ['インプレッション数', 'Impressions'],
    '総再生時間（時間）': ['総再生時間（単位: 時間）', '総再生時間 (単位: 時間)', '総再生時間（時間）', 'Watch time (hours)'],
}

def norm(value):
    return ''.join(unicodedata.normalize('NFKC', str(value)).lower().split())

def guess(columns, metric):
    aliases = {norm(x) for x in ALIASES[metric]}
    return next((c for c in columns if norm(c) in aliases), None)

def read_csv_bytes(data):
    if not data or len(data) > 20 * 1024 * 1024:
        raise ValueError('空のファイル、または20MBを超えるファイルです。')
    decoded = None
    encodings = ('utf-16',) if data.startswith((b'\xff\xfe', b'\xfe\xff')) else ('utf-8-sig', 'cp932')
    for encoding in encodings:
        try:
            decoded = data.decode(encoding)
            break
        except UnicodeError:
            continue
    if decoded is None:
        raise ValueError('文字コードを読み取れません。UTF-8のCSVとして保存し直してください。')
    try:
        dialect = csv.Sniffer().sniff(decoded[:16384], delimiters=',;\t')
        separator = dialect.delimiter
    except csv.Error:
        separator = ','
    try:
        df = pd.read_csv(io.StringIO(decoded), sep=separator, dtype=str, keep_default_na=False)
    except (pd.errors.ParserError, pd.errors.EmptyDataError) as error:
        raise ValueError('CSVの形式を確認してください。ZIPは展開し、動画別の表データを選んでください。') from error
    df.columns = [str(c).strip() for c in df.columns]
    if len(set(df.columns)) != len(df.columns):
        raise ValueError('同じ名前の列があります。列名を一意にして保存し直してください。')
    df = df.loc[~df.apply(lambda r: r.str.strip().eq('').all(), axis=1)].reset_index(drop=True)
    if df.empty:
        raise ValueError('動画の行が含まれていません。')
    return df

def number(series):
    text = series.astype(str).map(lambda x: unicodedata.normalize('NFKC', x))
    text = text.str.replace(',', '', regex=False).str.replace('%', '', regex=False).str.strip()
    result = pd.to_numeric(text, errors='coerce')
    return result.where(result.ge(0) & result.lt(float('inf')))

def total_mask(df, mapping):
    mask = pd.Series(False, index=df.index)
    for field in ('動画タイトル', '動画ID'):
        col = mapping.get(field)
        if col:
            mask |= df[col].map(norm).isin({'合計', '総計', '総合計', 'total', 'totals'})
    return mask

def prepare(df, mapping, exclude_totals=True):
    selected = [c for c in mapping.values() if c]
    if len(selected) != len(set(selected)):
        raise ValueError('同じ列が複数の項目に選ばれています。列の対応を変更してください。')
    if not mapping.get('動画タイトル'):
        raise ValueError('「動画タイトル」に対応する列を選んでください。日付別のCSVではなく、動画別の表を使用します。')
    mask = total_mask(df, mapping)
    result = df.loc[~mask if exclude_totals else pd.Series(True, index=df.index)].copy()
    # 元の全列を残し、表示用の数値だけを別に作る。
    metrics = pd.DataFrame(index=result.index)
    for field, col in mapping.items():
        if col:
            metrics[field] = number(result[col]) if field not in ('動画タイトル', '動画ID', '平均視聴時間') else result[col]
    return result, metrics, int(mask.sum())

def protect_csv_cell(value):
    """数式開始文字、先頭の制御文字を文字列として扱わせる。"""
    if not isinstance(value, str):
        return value
    if (value.lstrip().startswith(('=', '+', '-', '@'))
            or (value and ord(value[0]) < 32)):
        return "'" + value
    return value


def safe_csv(df):
    """セルと列名を保護する。再インポート時にも保護用の引用符を保持する。"""
    safe = df.copy()
    # dtypeに依存せず処理し、カテゴリ型等の文字列も保護する。
    for col in safe.columns:
        safe[col] = safe[col].map(protect_csv_cell)
    safe.columns = [protect_csv_cell(str(c)) for c in safe.columns]
    return safe.to_csv(index=False).encode('utf-8-sig')
