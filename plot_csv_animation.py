import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from plot_csv_animation_param import (
    file_name, x_col, y_col, show_line, skip_count,
    total_duration_sec, output_filename, fps,
    show_extra_display, display_col
)
import numpy as np

def create_animation():
    """CSVデータからアニメーション動画を作成する"""
    plt.rcParams["font.size"] = 16

    # テキスト表示が可能かどうかを管理するローカル変数
    is_text_display_enabled = show_extra_display

    try:
        # CSV読み込み
        df = pd.read_csv(file_name)

        # x軸とy軸の列名（タイトル）を取得
        x_label = df.columns[x_col]
        y_label = df.columns[y_col]

        # x軸とy軸のデータをインデックスで抽出
        x_data = df.iloc[skip_count:, x_col]
        y_data = df.iloc[skip_count:, y_col]

        # 追加表示用のデータを取得
        display_data = None
        display_label = ''
        if is_text_display_enabled:
            try:
                display_label = df.columns[display_col]
                display_data = df.iloc[skip_count:, display_col]
            except IndexError:
                print(f"警告: 追加表示用の列インデックス {display_col} が範囲外です。テキスト表示は無効になります。")
                is_text_display_enabled = False

    except IndexError:
        print(f"エラー: 指定された列インデックスがファイルの列数を超えています。x_col={x_col}, y_col={y_col}")
        print("利用可能な列名 (ヘッダー):", df.columns.tolist())
        return
    except FileNotFoundError:
        print(f"エラー: ファイル '{file_name}' が見つかりません。")
        return
    except Exception as e:
        print(f"データの読み込み中に予期せぬエラーが発生しました: {e}")
        return

    # プロットのセットアップ
    fig, ax = plt.subplots(figsize=(12, 8))

    # 軸の範囲をデータの最小値・最大値に設定
    ax.set_xlim(x_data.min(), x_data.max())
    # Y軸は少し余裕を持たせる
    y_margin = (y_data.max() - y_data.min()) * 0.1
    ax.set_ylim(y_data.min() - y_margin, y_data.max() + y_margin)

    # ラベルとタイトル
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    ax.set_title(f'Animation of {y_label} vs {x_label}')
    ax.grid(True)

    # --- ここでテキストのフォーマットを直接指定 ---
    # {label} には列名が、{value} には現在の値が入ります
    # 例: 'Time: {value:.2f} s', 'Frame: {value:d}'
    display_format = '{label}: {value:.2f}'

    plot_artists = []
    # プロットオブジェクトの初期化
    if show_line:
        line, = ax.plot([], [], lw=2)
        plot_artists.append(line)
    else:
        scatter = ax.scatter([], [], s=10)
        plot_artists.append(scatter)

    # 追加表示用のテキストオブジェクトを初期化
    if is_text_display_enabled:
        text_obj = ax.text(0.95, 0.95, '', transform=ax.transAxes,
                           fontsize=14, verticalalignment='top', horizontalalignment='right',
                           bbox=dict(boxstyle='round,pad=0.5', fc='yellow', alpha=0.5))
        plot_artists.append(text_obj)
    num_data_points = len(x_data)
    if num_data_points == 0:
        print("エラー: スキップ後のデータが0件です。")
        return

    # 動画の総フレーム数を計算
    total_video_frames = int(total_duration_sec * fps)

    # アニメーションの更新関数
    def update(frame):
        # 現在の動画フレームに対応するデータインデックスを計算
        progress = frame / (total_video_frames - 1) if total_video_frames > 1 else 1.0
        data_index = int(progress * (num_data_points - 1))

        current_x = x_data[:data_index + 1]
        current_y = y_data[:data_index + 1]
        if show_line:
            line.set_data(current_x, current_y)
        else:
            # scatterの場合は、(x, y)のペアの配列を渡す
            scatter.set_offsets(np.c_[current_x, current_y])

        if is_text_display_enabled:
            current_display_value = display_data.iloc[data_index]
            text_obj.set_text(display_format.format(label=display_label, value=current_display_value))
        return tuple(plot_artists)
    # インターバルを計算
    interval_ms = 1000 / fps

    # アニメーションの作成
    ani = animation.FuncAnimation(
        fig, update, frames=total_video_frames,
        interval=interval_ms, blit=True, repeat=False
    )

    # 動画として保存
    try:
        print(f"アニメーションを '{output_filename}' に保存しています... (時間がかかる場合があります)")
        ani.save(output_filename, writer='ffmpeg', fps=fps)
        print("保存が完了しました。")
    except Exception as e:
        print(f"動画の保存中にエラーが発生しました: {e}")
        print("ffmpegがインストールされ、パスが通っているか確認してください。")
        print("例: 'conda install -c conda-forge ffmpeg' または 'sudo apt-get install ffmpeg'")

if __name__ == '__main__':
    create_animation()