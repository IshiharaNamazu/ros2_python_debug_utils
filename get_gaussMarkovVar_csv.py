import pandas as pd
from get_gaussMarkovVar_csv_param import file_name, col_name, limit_col_name, lower_limit, upper_limit


def calculate_diff_variance():
    try:
        # CSVを読み込む
        df = pd.read_csv(file_name)
        
        # 指定した列を取得
        data_series = df[col_name]
        
        # .diff() で「前の行との差」を計算 (最初の行は NaN になります)
        diff_series = data_series.diff()
        
        # 指定された範囲内に収まるデータのみを抽出
        if limit_col_name!='' and limit_col_name in df.columns:
            mask = (df[limit_col_name] >= lower_limit) & (df[limit_col_name] <= upper_limit)
            diff_series = diff_series[mask]
            df = df[mask]
        
        print(f"データ数: {len(diff_series.dropna())}")
        # NaNを除外して分散を計算 (ddof=1 で不偏分散)
        variance = diff_series.dropna().var()
        ser_var = df[col_name].var()
        # print(diff_series.dropna())
        
        return ser_var,variance
    
    except KeyError:
        print(f"エラー: 列 '{col_name}' が見つかりません。")
    except Exception as e:
        print(f"エラーが発生しました: {e}")

ser_var, variance = calculate_diff_variance()
print(f"1ステップあたりの分散: {variance}")
print(f"全体の分散: {ser_var}")