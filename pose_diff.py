import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseStamped
import time
import csv
from tf_transformations import quaternion_inverse, quaternion_multiply, quaternion_conjugate

from pose_diff_param import source_topic_name, source_topic_type, target_topic_name, target_topic_type, output_topic_name, output_topic_type
from pose_diff_param import rotate_diff
from pose_diff_param import is_use_sim_time

from ros2bag_timediff_param import output_filename
class PoseDifferenceCalculator(Node):
    """
    PoseStamped メッセージの位置の差を計算し、新しいトピックに送信するノード。
    """

    def __init__(self):
        # ノードの初期化
        super().__init__('pose_difference_calculator')

        # use_sim_time
        self.set_parameters([
        rclpy.parameter.Parameter('use_sim_time', rclpy.parameter.Parameter.Type.BOOL, is_use_sim_time)
        ])

        # 最後に受信したPoseStampedメッセージを保存する変数
        self.last_target_pose = None
        self.last_source_pose = None

        # CSVファイルへの書き出し準備
        self.csv_file = None
        self.csv_writer = None
        try:
            # 注意: output_filenameはros2bag_timediff_paramからインポートされています。
            # 別のスクリプトと共有すると、ファイルが上書きされる可能性があります。
            # pose_diff.py専用のファイル名をpose_diff_param.pyで定義することを推奨します。
            self.csv_file = open(output_filename, 'w', newline='', encoding='utf-8')
            fieldnames = [
                'timestamp_sec', 'timestamp_nanosec',
                'pos_x', 'pos_y', 'pos_z', 'ori_x', 'ori_y', 'ori_z', 'ori_w'
            ]
            self.csv_writer = csv.DictWriter(self.csv_file, fieldnames=fieldnames)
            self.csv_writer.writeheader()
            self.get_logger().info(f"CSV output is enabled. Writing to '{output_filename}'.")
        except IOError as e:
            self.get_logger().error(f"Could not open CSV file '{output_filename}': {e}")

        # 受信トピックの購読設定
        self.target_subscriber = self.create_subscription(
            target_topic_type,
            target_topic_name,
            self.target_callback,
            10)
        self.target_subscriber  # unused variable warning対策

        self.source_subscriber = self.create_subscription(
            source_topic_type,
            source_topic_name,
            self.source_callback,
            10)
        self.source_subscriber # unused variable warning対策

        # 送信トピックの作成設定
        self.difference_publisher = self.create_publisher(
            output_topic_type,
            output_topic_name,
            10)

        self.get_logger().info('PoseDifferenceCalculator Node has started.')
        self.get_logger().info(f'Subscribing to {target_topic_name} and {source_topic_name}.')
        self.get_logger().info(f'Publishing difference to {output_topic_name}.')

    def target_callback(self, msg):
        # 最新のターゲット姿勢を保存
        self.last_target_pose = msg
        
        # 差の計算と送信
        self.calculate_and_publish_difference()

    def source_callback(self, msg):
        self.last_source_pose = msg
        # このトピック受信時ではなく、target_callbackでのみ差を計算・送信する

    def calculate_and_publish_difference(self):
        if self.last_target_pose is None or self.last_source_pose is None:
            self.get_logger().warn('Waiting for both PoseStamped data...')
            return

        # --- 1. ワールド座標系での位置の差分ベクトル V_D を計算 ---
        
        diff_x = self.last_target_pose.pose.position.x - self.last_source_pose.pose.position.x
        diff_y = self.last_target_pose.pose.position.y - self.last_source_pose.pose.position.y
        diff_z = self.last_target_pose.pose.position.z - self.last_source_pose.pose.position.z

        # V_Dを純粋四元数 (0, x, y, z) の形式に変換
        v_diff = [0.0, diff_x, diff_y, diff_z]

        # --- 2. ローカライゼーション姿勢の四元数を Q_L として取得 ---
        
        q_l = self.last_source_pose.pose.orientation
        # Q_Lを配列 [x, y, z, w] の形式に変換 (tf_transformations の形式)
        q_l_array = [q_l.x, q_l.y, q_l.z, q_l.w]
        
        # ターゲット姿勢の四元数を Q_T として取得
        q_t = self.last_target_pose.pose.orientation
        q_t_array = [q_t.x, q_t.y, q_t.z, q_t.w]

        # --- 3. 逆回転 (共役四元数 Q_L*) を計算 ---
        
        # ローカル座標系への変換には、Q_L の共役 (conjugate) を使用
        q_l_conj = quaternion_conjugate(q_l_array)
        
        # --- 4. 座標変換 (V_Local = Q_L* * V_D * Q_L) を実行 ---
        
        # (Q_L* * V_D) の計算
        v_rotated_part1 = quaternion_multiply(q_l_conj, v_diff)
        
        # (Q_L* * V_D) * Q_L の計算
        # 結果 v_local は純粋四元数形式 [0, dx_local, dy_local, dz_local]
        v_local = quaternion_multiply(v_rotated_part1, q_l_array)

        # --- 4b. 回転の差分を計算 (q_diff = q_l_inv * q_t) ---
        # 単位クォータニオンなので、逆クォータニオンは共役クォータニオン(q_l_conj)と同じ
        q_diff = quaternion_multiply(q_l_conj, q_t_array)

        # --- 5. 差分メッセージを作成し、ローカルベクトル V_Local を格納 ---
        
        diff_msg = PoseStamped()
        
        # ヘッダーは GNSS のものを使用
        diff_msg.header.stamp = self.last_target_pose.header.stamp
        # フレームIDをローカライゼーションのフレームに設定するのが適切
        diff_msg.header.frame_id = self.last_source_pose.header.frame_id

        if not rotate_diff:
            # 位置にはワールド座標系での差分を格納
            diff_msg.pose.position.x = diff_x
            diff_msg.pose.position.y = diff_y
            diff_msg.pose.position.z = diff_z
        else:
            # 位置には計算したローカル差分ベクトルを格納
            # v_local は [0, x, y, z] の形式なので、要素 1, 2, 3 を取得
            diff_msg.pose.position.x = v_local[1]
            diff_msg.pose.position.y = v_local[2]
            diff_msg.pose.position.z = v_local[3]

        # 姿勢(Orientation)には、sourceから見たtargetの相対的な回転を格納
        diff_msg.pose.orientation.x = q_diff[0]
        diff_msg.pose.orientation.y = q_diff[1]
        diff_msg.pose.orientation.z = q_diff[2]
        diff_msg.pose.orientation.w = q_diff[3]

        # 計算結果の送信
        self.difference_publisher.publish(diff_msg)
        # CSVへの書き込み
        self.write_to_csv(diff_msg)

    def write_to_csv(self, msg):
        if not self.csv_writer:
            return
        try:
            row = {
                'timestamp_sec': msg.header.stamp.sec, 'timestamp_nanosec': msg.header.stamp.nanosec,
                'pos_x': msg.pose.position.x, 'pos_y': msg.pose.position.y, 'pos_z': msg.pose.position.z,
                'ori_x': msg.pose.orientation.x, 'ori_y': msg.pose.orientation.y, 'ori_z': msg.pose.orientation.z, 'ori_w': msg.pose.orientation.w
            }
            self.csv_writer.writerow(row)
            self.csv_file.flush()
        except Exception as e:
            self.get_logger().warn(f"Failed to write to CSV file: {e}")

    def destroy_node(self):
        """ノード終了時にCSVファイルを閉じる"""
        if self.csv_file:
            self.get_logger().info(f"Closing CSV file '{output_filename}'.")
            self.csv_file.close()
        super().destroy_node()

def main(args=None):
    rclpy.init(args=args)

    pose_difference_calculator = PoseDifferenceCalculator()

    # ノードの実行（コールバックを待機）
    try:
        rclpy.spin(pose_difference_calculator)
    except KeyboardInterrupt:
        pass
    finally:
        # 終了処理
        pose_difference_calculator.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
