# ヘッダ行付きのCSVをプロット
import pandas as pd
import matplotlib.pyplot as plt
from plot_csv_param import file_name, x_col, y_col, show_line
import numpy as np

try:
    # CSV読み込み
    df = pd.read_csv(file_name)

    # x軸とy軸の列名（タイトル）を取得
    x_label = df.columns[x_col]
    y_label = df.columns[y_col]

    # x軸とy軸のデータをインデックスで抽出
    x_data = df.iloc[:, x_col]
    y_data = df.iloc[:, y_col]

except IndexError:
    print("エラー: 指定された列インデックスがファイルの列数を超えています。x_colとy_colを確認してください。")
    print("利用可能な列名 (ヘッダー):", df.columns.tolist())
    exit()
except FileNotFoundError:
    print(f"エラー: ファイル '{file_name}' が見つかりません。")
    exit()
except Exception as e:
    print(f"データの読み込み中に予期せぬエラーが発生しました: {e}")
    exit()


print("min:", np.min(y_data), "max", np.max(y_data), "mean:", np.mean(y_data), "variance:", np.var(y_data))
plt.figure(figsize=(10, 6))
if(show_line):
    plt.plot(x_data, y_data)
else:
    plt.scatter(x_data, y_data, s=6)

# ラベルとタイトルにヘッダー行の値を使用
plt.title(f'Plot of {y_label} vs {x_label}')

plt.xlabel(x_label)
plt.ylabel(y_label)

# グリッド表示
plt.grid(True)

# プロットを画面に表示（ファイル保存はしない）
plt.show()

print("プロットの表示が完了しました。")