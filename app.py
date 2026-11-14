from pathlib import Path
import hashlib
import altair as alt
import pandas as pd
import streamlit as st
from analysis import ALIASES, guess, read_csv_bytes, prepare, safe_csv

st.set_page_config(page_title='逆転ドラマ 動画分析', page_icon='📊', layout='wide', initial_sidebar_state='expanded')
st.markdown('''<style>html, body, [class*="css"] {font-family: sans-serif;} .stApp h1 {font-size:2.1rem;} [data-testid="stMetricValue"] {font-size:2rem;} [data-testid="stToolbar"] {display:none;}</style>''', unsafe_allow_html=True)
st.title('逆転ドラマ 動画分析')
st.write('YouTube StudioのCSVから、動画の成績と次の改善点を確認しましょう。')
st.caption('65歳以上の男性向けドラマの制作支援｜API連携なし・CSV読み込み版')
with st.expander('はじめての方へ：使い方とデータの扱い'):
    st.markdown('''1. YouTube Studioの「アナリティクス」から詳細画面を開き、期間を選びます。
2. 動画（コンテンツ）別の表に、視聴回数・クリック率・平均視聴時間などを追加してCSVに書き出します。
3. ZIPの場合は展開し、「表データ.csv」など、動画のタイトルが行に並ぶCSVを選びます。
4. 左側でCSVを読み込み、必要なら「列の対応を確認」で列を選び直します。
5. 一覧・グラフを確認し、制作メモをダウンロードします。

CSVにない指標は表示できません。平均視聴時間は元の表記を保持します。
時間ごとの視聴維持率曲線は、この版では扱いません。

アップロードしたデータは実行先のサーバーで処理します。アプリは外部サービスに送信せず、データをディスクやデータベースに保存しません。
クラウドで使う場合も、他の利用者と共有するキャッシュは使用しません。データとメモはセッション中のメモリに保持されます。ホスティング側のログ・バックアップ・メモリの消去時期までは保証しません。必要なメモはダウンロードしてください。''')

with st.sidebar:
    st.header('① データを選ぶ')
    source = st.radio('データの種類', ['サンプルで試す', '自分のCSVを読み込む'])
    upload = st.file_uploader('CSVファイルを選択（20MBまで）', type=['csv'], help='ファイルをドラッグするか、選択ボタンを押してください。') if source == '自分のCSVを読み込む' else None
    period = st.text_input('集計期間のメモ', placeholder='例：2026年10月1日〜10月31日')
    st.caption('期間メモは表示用です。CSVの数値を期間で絞り込む機能ではありません。')
if source == '自分のCSVを読み込む' and upload is None:
    st.info('左側の「CSVファイルを選択」から、YouTube Studioの動画別CSVを選んでください。スマートフォン等では左上からサイドバーを開けます。')
    st.stop()
data = upload.getvalue() if upload is not None else Path(__file__).with_name('サンプル.csv').read_bytes()
if source == 'サンプルで試す':
    st.info('サンプル表示中です。動画名・数値はすべて架空で、実際のチャンネルの分析結果ではありません。')
signature = hashlib.sha256(data).hexdigest()[:16]
try:
    raw = read_csv_bytes(data)
except ValueError as error:
    st.error(str(error))
    st.stop()
with st.sidebar:
    with st.expander('② 列の対応を確認', expanded=not bool(guess(raw.columns, '動画タイトル'))):
        mapping = {}
        options = ['（なし）'] + list(raw.columns)
        for metric in ALIASES:
            default = guess(raw.columns, metric)
            choice = st.selectbox(metric, options, index=options.index(default) if default else 0, key=f'{signature}:{metric}')
            mapping[metric] = None if choice == '（なし）' else choice
        exclude = st.checkbox('「合計」「Total」の行を除く', value=True)
    st.caption('英語CSVも主要な列名は自動判定します。元データの見出し・動画名はそのまま表示します。')
try:
    table, metrics, total_count = prepare(raw, mapping, exclude)
except ValueError as error:
    st.warning(str(error))
    st.stop()
if total_count and exclude:
    st.caption(f'合計行を{total_count}件除いています。')
if table.empty:
    st.warning('表示できる動画がありません。動画別のCSVと列の対応を確認してください。')
    st.stop()
if period:
    st.write('集計期間のメモ：', period)
st.caption('集計対象は読み込んだCSVの範囲です。65歳以上・男性などの視聴者属性による自動絞り込みは行いません。')
keyword = st.text_input('③ 動画タイトルで絞り込む', placeholder='例：職人、定年、父親')
if keyword:
    keep = metrics['動画タイトル'].str.contains(keyword, case=False, regex=False, na=False)
    table, metrics = table.loc[keep], metrics.loc[keep]
a, b = st.columns(2)
a.metric('表示中の動画数', f'{len(table):,}本')
if '再生数' in metrics and metrics['再生数'].notna().any():
    b.metric('表示中の再生数合計', f'{metrics["再生数"].sum():,.0f}回')
else:
    b.metric('表示中の再生数合計', 'データなし')
for name in ('再生数', 'クリック率（%）', '平均再生率（%）'):
    if name in metrics:
        missing = metrics[name].isna().sum()
        if missing:
            st.caption(f'{name}：空欄・数値として読めない値などが{missing}件あります。0として補完せず、集計から除いています。')

list_tab, graph_tab, memo_tab = st.tabs(['動画の成績一覧', '再生数TOP10', 'ドラマ制作メモ'])
with list_tab:
    st.subheader('動画ごとの成績')
    st.caption('上の表は対応を指定した主要指標です。クリック率は％単位です（例：6.5＝6.5％）。見出しを押すと並べ替えられます。')
    st.dataframe(metrics.reset_index(drop=True), hide_index=True, width='stretch')
    with st.expander('CSVの全項目を表示（元の値）'):
        st.dataframe(table.reset_index(drop=True), hide_index=True, width='stretch')
    st.download_button('表示中の元データをCSVで保存', safe_csv(table), '動画分析_抽出データ.csv', 'text/csv')
    st.caption('平均視聴時間・率の全動画単純平均は表示していません。動画の長さや流入元、公開後日数をそろえて比較してください。')
with graph_tab:
    st.subheader('再生数TOP10')
    st.caption('タイトルでの絞り込みを反映します。10本未満の場合は、該当する動画だけを表示します。')
    if '再生数' not in metrics:
        st.info('「列の対応を確認」で再生数に対応する列を選択してください。')
    else:
        top = metrics.dropna(subset=['再生数']).sort_values('再生数', ascending=False, kind='stable').head(10).copy()
        if top.empty:
            st.info('グラフに表示できる再生数がありません。絞り込みとCSVの値を確認してください。')
        else:
            top['順位'] = range(1, len(top) + 1)
            top['順位と動画タイトル'] = top['順位'].astype(str) + '位　' + top['動画タイトル'].str.slice(0, 34)
            graph = alt.Chart(top).mark_bar(color='#176b64', cornerRadiusEnd=4).encode(
                x=alt.X('再生数:Q', title='再生数（回）', axis=alt.Axis(format=',')),
                y=alt.Y('順位と動画タイトル:N', sort=top['順位と動画タイトル'].tolist(), title=None, axis=alt.Axis(labelLimit=400)),
                tooltip=[alt.Tooltip('順位:Q'), alt.Tooltip('動画タイトル:N'), alt.Tooltip('再生数:Q', format=',')]
            ).properties(height=max(180, len(top) * 43))
            st.altair_chart(graph, width='stretch')
            st.dataframe(top[['順位', '動画タイトル', '再生数']].reset_index(drop=True), hide_index=True, width='stretch')
with memo_tab:
    st.subheader('物語の特徴と、改善の仮説を記録する')
    st.write('主人公や逆転のきっかけを記録し、伸びた動画の共通点を探します。入力はこの画面内だけに保持されます。')
    st.caption('サンプルの各動画への仮説記入も可能です。再読み込みやCSVの変更で失われるため、作業後は必ず保存してください。')
    memo = metrics[[c for c in ('動画ID', '動画タイトル', '再生数', 'クリック率（%）', '平均視聴時間', '平均再生率（%）') if c in metrics]].copy().reset_index(drop=True)
    memo['集計期間のメモ'] = period
    fields = ['ジャンル', '主人公の設定', '対立の内容', '逆転のきっかけ', '結末', '次回の改善仮説']
    for field in fields:
        memo[field] = table[field].reset_index(drop=True) if field in table.columns else ''
    edited = st.data_editor(memo, disabled=[c for c in memo.columns if c not in fields], hide_index=True, width='stretch', key=f'memo:{signature}:{keyword}:{period}')
    st.download_button('制作メモをCSVで保存', safe_csv(edited), 'ドラマ制作メモ.csv', 'text/csv')
    st.info('制作メモCSVは、次回「自分のCSVを読み込む」から開くと、入力内容を「CSVの全項目」で確認できます。メモ欄にも復元されるので、続けて編集できます。')
    st.markdown('''**比較するときの確認ポイント**
- クリック率が低い場合：同じ流入元・似た公開後日数の動画と比べ、タイトルとサムネイルを確認します。
- 平均再生率が低い場合：似た長さの動画と比べ、冒頭や逆転までの説明を確認します。
- 再生数だけで結論を出さず、インプレッション数と集計期間も確認します。
- 視聴維持率の曲線や離脱箇所は、YouTube Studioで別途確認します。''')
st.divider()
st.caption('このツールは改善の仮説を整理するためのものです。再生数の増加を保証するものではありません。')
