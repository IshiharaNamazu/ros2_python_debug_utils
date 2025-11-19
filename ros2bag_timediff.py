# 指定したメッセージのタイムスタンプと受信時刻の差分を計算し、CSVに保存

#param
from ros2bag_timediff_param import bag_path_str
from ros2bag_timediff_param import target_topics_list
#from ros2bagtimediff_param import topic_type
from ros2bag_timediff_param import output_filename

import sys
import csv
from pathlib import Path
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message
from rosbag2_py import SequentialReader, StorageOptions, ConverterOptions, StorageFilter

# plot
import matplotlib.pyplot as plt

def export_time_differences():
    bag_path = Path(bag_path_str)

    # 1. SequentialReaderのセットアップ
    storage_options = StorageOptions(
        uri=str(bag_path),
        # 拡張子 .db3 に基づいてストレージIDを切り替える
        storage_id='sqlite3' if bag_path.suffix == '.db3' else 'mcap'
    )
    converter_options = ConverterOptions(
        input_serialization_format="cdr",
        output_serialization_format="cdr"
    )

    reader = SequentialReader()
    try:
        reader.open(storage_options, converter_options)
    except RuntimeError as e:
        print(f"エラー: rosbagファイルを開けませんでした。パスを確認してください: {bag_path_str}")
        print(f"詳細: {e}")
        sys.exit(1)

    # 2. トピック情報の取得
    all_topic_types = reader.get_all_topics_and_types()
    
    # フィルタリング
    topic_types = [
        t for t in all_topic_types 
        if t.name in target_topics_list
    ]
    
    # トピックが見つからない場合のチェック
    if not topic_types:
        print(f"エラー: rosbag内に指定されたトピック {target_topics_list} が見つかりませんでした。")
        sys.exit(1)

    type_map = {topic.name: topic.type for topic in topic_types}
    
    try:
        message_types = {
            topic_name: get_message(topic_type) 
            for topic_name, topic_type in type_map.items()
        }
    except ImportError as e:
        print(f"エラー: メッセージ型のインポートに失敗しました。必要なROS 2パッケージがインストールされているか確認してください。")
        print(f"詳細: {e}")
        sys.exit(1)

    # SequentialReaderにフィルタを適用
    reader.set_filter(
        StorageFilter(topics=target_topics_list)
    )
    # 3. CSVファイルへの書き出し準備
    with open(output_filename, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['topic_name', 'topic_type', 'reception_timestamp_ns', 'message_timestamp_ns', 'time_difference_ms']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        print(f"rosbagの読み込みと差分計算を開始 (対象トピック: {target_topics_list})...")

        # 4. メッセージの読み込みと計算
        while reader.has_next():
            topic_name, serialized_data, timestamp_ns = reader.read_next()
            
            # 余分なデータが入っていないか念の為最終チェック
            if topic_name not in target_topics_list:
                continue

            reception_timestamp_ns = timestamp_ns 

            topic_type = type_map.get(topic_name)
            msg_type = message_types.get(topic_name)

            if msg_type is None:
                continue

            try:
                msg = deserialize_message(serialized_data, msg_type)
            except Exception as e:
                print(f"警告: トピック {topic_name} のメッセージのデシリアライズに失敗しました: {e}")
                continue
            
            # タイムスタンプの抽出 ('Header'フィールドを想定)
            if hasattr(msg, 'header') and hasattr(msg.header, 'stamp'):
                message_stamp = msg.header.stamp
                message_timestamp_ns = message_stamp.sec * 1_000_000_000 + message_stamp.nanosec
                
                # 時間差の計算 (ミリ秒)
                time_difference_ms = (reception_timestamp_ns - message_timestamp_ns) / 1_000_000.0
                
                # CSVへの書き込み
                writer.writerow({
                    'topic_name': topic_name,
                    'topic_type': topic_type,
                    'reception_timestamp_ns': reception_timestamp_ns,
                    'message_timestamp_ns': message_timestamp_ns,
                    'time_difference_ms': time_difference_ms
                })
                


        print(f"rosbagの読み込みが完了しました。")
        print(f"結果は '{output_filename}' に出力されました。")

def main():
    export_time_differences()

if __name__ == '__main__':
    main()