import sys
import csv
from pathlib import Path

# ROS 2 関連
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message
from rosbag2_py import SequentialReader, StorageOptions, ConverterOptions, StorageFilter

# 姿勢計算用
from tf_transformations import quaternion_multiply, quaternion_conjugate

from ros2bag_timediff_param import bag_path_str, bag_dir, output_filename, source_topic_name, target_topic_name, rotate_diff


def calculate_pose_difference(source_pose, target_pose, rotate_diff):
    # 差分ベクトル
    diff_x = target_pose.pose.position.x - source_pose.pose.position.x
    diff_y = target_pose.pose.position.y - source_pose.pose.position.y
    diff_z = target_pose.pose.position.z - source_pose.pose.position.z

    v_diff = [0.0, diff_x, diff_y, diff_z]

    # ソースの姿勢取得
    q_l = source_pose.pose.orientation
    q_l_array = [q_l.x, q_l.y, q_l.z, q_l.w]
    
    # ターゲット姿勢取得
    q_t = target_pose.pose.orientation
    q_t_array = [q_t.x, q_t.y, q_t.z, q_t.w]

    # 逆クォータニオン
    q_l_conj = quaternion_conjugate(q_l_array)
    
    # 差分位置ベクトル回転
    v_rotated_part1 = quaternion_multiply(q_l_conj, v_diff)
    v_local = quaternion_multiply(v_rotated_part1, q_l_array)

    # 回転の差分を計算
    q_diff = quaternion_multiply(q_l_conj, q_t_array)

    # 5. 結果の格納用辞書を作成
    result = {
        'pos_x': 0.0, 'pos_y': 0.0, 'pos_z': 0.0,
        'ori_x': q_diff[0], 'ori_y': q_diff[1], 'ori_z': q_diff[2], 'ori_w': q_diff[3]
    }

    if not rotate_diff:
        # ワールド座標系での差分
        result['pos_x'] = diff_x
        result['pos_y'] = diff_y
        result['pos_z'] = diff_z
    else:
        # ローカル差分ベクトル (v_local は [0, x, y, z])
        result['pos_x'] = v_local[1]
        result['pos_y'] = v_local[2]
        result['pos_z'] = v_local[3]

    return result

def process_bag_and_export_csv():
    # 対象トピックのリスト
    target_topics_list = [source_topic_name, target_topic_name]

    # パスの解決
    if bag_path_str != '':
        bag_path = Path(bag_path_str)
    else:
        p = Path(bag_dir)
        folders = [x for x in p.iterdir() if x.is_dir()]
        if folders:
            folders.sort(reverse=True)
            bag_path = folders[0]
            print(f'loading bag from: {bag_path.name}')
        else:
            print("エラー: 指定された bag_dir にフォルダがありません。")
            sys.exit(1)

    # ストレージIDの判定
    storage_id = 'mcap'
    if bag_path.suffix == '.db3':
        storage_id = 'sqlite3'
    elif bag_path.is_dir() and any(bag_path.glob('*.db3')):
        storage_id = 'sqlite3'

    # SequentialReaderのセットアップ
    storage_options = StorageOptions(uri=str(bag_path), storage_id=storage_id)
    converter_options = ConverterOptions(
        input_serialization_format="cdr",
        output_serialization_format="cdr"
    )

    reader = SequentialReader()
    try:
        reader.open(storage_options, converter_options)
    except RuntimeError as e:
        print(f"エラー: rosbagファイルを開けませんでした: {e}")
        sys.exit(1)

    # トピック情報の取得とフィルタリング
    all_topic_types = reader.get_all_topics_and_types()
    topic_types = [t for t in all_topic_types if t.name in target_topics_list]
    
    if len(topic_types) < 2:
        print(f"警告: rosbag内に指定されたトピックの一部または全部が見つかりません: {target_topics_list}")
        # そのまま進めるとエラーになる可能性があるので終了するか確認が必要ですが、ここでは続行します

    type_map = {topic.name: topic.type for topic in topic_types}
    
    try:
        message_types = {
            topic_name: get_message(topic_type) 
            for topic_name, topic_type in type_map.items()
        }
    except ImportError as e:
        print(f"エラー: メッセージ型のインポートに失敗しました: {e}")
        sys.exit(1)

    # フィルタの適用
    reader.set_filter(StorageFilter(topics=target_topics_list))

    # 状態保持用の変数
    last_source_pose = None

    # CSV出力の準備
    with open(output_filename, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = [
            'timestamp_sec', 'timestamp_nanosec',
            'pos_x', 'pos_y', 'pos_z', 'ori_x', 'ori_y', 'ori_z', 'ori_w'
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        print(f"rosbagの読み込みと差分計算を開始します...")
        print(f"Source: {source_topic_name}")
        print(f"Target: {target_topic_name}")

        count = 0
        # メッセージの読み込みループ
        while reader.has_next():
            topic_name, serialized_data, timestamp_ns = reader.read_next()
            
            msg_type = message_types.get(topic_name)
            if msg_type is None:
                continue

            try:
                msg = deserialize_message(serialized_data, msg_type)
            except Exception as e:
                print(f"警告: {topic_name} のデシリアライズ失敗: {e}")
                continue

            # sourceを受信した場合は最新値を更新するのみ
            if topic_name == source_topic_name:
                last_source_pose = msg
            
            # targetを受信した場合、最新のsourceが存在すれば計算してCSVへ出力
            elif topic_name == target_topic_name:
                last_target_pose = msg
                
                if last_source_pose is None:
                    # まだsourceを受信していない場合はスキップ
                    continue
                
                # 計算処理
                diff_result = calculate_pose_difference(last_source_pose, last_target_pose, rotate_diff)
                
                # タイムスタンプの取得 (Targetのヘッダー時間を採用)
                if hasattr(last_target_pose, 'header') and hasattr(last_target_pose.header, 'stamp'):
                    t_sec = last_target_pose.header.stamp.sec
                    t_nanosec = last_target_pose.header.stamp.nanosec
                else:
                    # ヘッダーが無い場合は受信時刻(bagの記録時間)から算出
                    t_sec = int(timestamp_ns // 1_000_000_000)
                    t_nanosec = int(timestamp_ns % 1_000_000_000)

                # CSV行の構築
                row = {
                    'timestamp_sec': t_sec,
                    'timestamp_nanosec': t_nanosec,
                    'pos_x': diff_result['pos_x'],
                    'pos_y': diff_result['pos_y'],
                    'pos_z': diff_result['pos_z'],
                    'ori_x': diff_result['ori_x'],
                    'ori_y': diff_result['ori_y'],
                    'ori_z': diff_result['ori_z'],
                    'ori_w': diff_result['ori_w']
                }
                writer.writerow(row)
                count += 1

    print(f"完了しました。合計 {count} 件の差分データが '{output_filename}' に出力されました。")

def main():
    process_bag_and_export_csv()

if __name__ == '__main__':
    main()