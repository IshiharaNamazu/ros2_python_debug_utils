import pandas as pd
from get_gaussMarkovVar_csv_param import file_name, col_name

def calculate_diff_variance():
    try:
        # CSVを読み込む
        df = pd.read_csv(file_name)
        
        # 指定した列を取得
        data_series = df[col_name]
        
        # .diff() で「前の行との差」を計算 (最初の行は NaN になります)
        diff_series = data_series.diff()
        
        # NaNを除外して分散を計算 (ddof=1 で不偏分散)
        variance = diff_series.dropna().var()
        
        return variance
    
    except KeyError:
        print(f"エラー: 列 '{col_name}' が見つかりません。")
    except Exception as e:
        print(f"エラーが発生しました: {e}")

print(f"1ステップあたりの分散: {calculate_diff_variance()}")