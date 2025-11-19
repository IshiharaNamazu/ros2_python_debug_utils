#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from rclpy.duration import Duration as RclpyDuration
import rclpy.time

from std_msgs.msg import Float64  # output msg
# reference_topicとtarget_topicの時刻の差を計算する

# パラメーター
from time_diff_param import reference_topic_name
from time_diff_param import reference_topic_type
from time_diff_param import target_topic_name
from time_diff_param import target_topic_type
from time_diff_param import is_use_sim_time

class TimeDiffCalculator(Node):
    """
    センサーのタイムスタンプと現在時刻の差を計算し、
    Float64 (秒単位) でパブリッシュするノード
    """
    def __init__(self):
        super().__init__('time_diff_calculator')

        # use_sim_time
        self.set_parameters([
            rclpy.parameter.Parameter('use_sim_time', rclpy.parameter.Parameter.Type.BOOL, is_use_sim_time)
        ])

        # pub
        # referenceとclockの時刻差
        self.ref_diff_pub = self.create_publisher(
            Float64, 
            '/timediff/reference_diff', 
            10)
        # referenceとclockの時刻差のブレ
        self.ref_diffdiff_ms_pub = self.create_publisher(
            Float64, 
            '/timediff/reference_diff_diff_ms', 
            10)
        
        # targetとclockの時刻差
        self.target_diff_pub = self.create_publisher(
            Float64, 
            '/timediff/target_diff', 
            10)

        self.target_delay_ms_pub = self.create_publisher(
            Float64, 
            '/timediff/target_delay_ms', 
            10)

        # 2. サブスクライバの作成
        # IMUトピックをサブスクライブ
        self.reference_sub = self.create_subscription(
            reference_topic_type,
            reference_topic_name,
            self.reference_callback,
            10)
        
        # GNSSトピックをサブスクライブ
        self.target_sub = self.create_subscription(
            target_topic_type,
            target_topic_name,
            self.target_callback,
            10)
        
        self.reference_delay_time = None

        
        self.get_logger().info('Time Difference Calculator Node (Float) が起動しました。')

    def reference_callback(self, msg: reference_topic_type):
        try:
            now_time = self.get_clock().now()
            msg_stamp_msg = msg.header.stamp
            msg_stamp_time = rclpy.time.Time.from_msg(msg_stamp_msg)
            
            # diff計算
            diff_duration: RclpyDuration = now_time - msg_stamp_time
            diff_seconds_float = diff_duration.nanoseconds / 1e9
            
            # diffをパブリッシュ
            diff_msg = Float64()
            diff_msg.data = diff_seconds_float
            self.ref_diff_pub.publish(diff_msg)

            if self.reference_delay_time is not None:
                diffdiff_ms_msg = Float64()
                diffdiff_ms_msg.data = (self.reference_delay_time - diff_seconds_float) * 1000.0
                self.ref_diffdiff_ms_pub.publish(diffdiff_ms_msg)
            self.reference_delay_time = diff_seconds_float
            
        except Exception as e:
            self.get_logger().error(f'referenceコールバックでエラーが発生しました: {e}')

    def target_callback(self, msg: target_topic_type):
        try:
            now_time = self.get_clock().now()
            msg_stamp_msg = msg.header.stamp
            msg_stamp_time = rclpy.time.Time.from_msg(msg_stamp_msg)
            
            # diff計算
            diff_duration: RclpyDuration = now_time - msg_stamp_time
            diff_seconds_float = diff_duration.nanoseconds / 1e9
            
            # diffをパブリッシュ
            diff_msg = Float64()
            diff_msg.data = diff_seconds_float
            self.target_diff_pub.publish(diff_msg)

            # delayをパブリッシュ
            if self.reference_delay_time is not None:
                delay_ms_msg = Float64()
                delay_ms_msg.data = (diff_seconds_float - self.reference_delay_time) * 1000
                self.target_delay_ms_pub.publish(delay_ms_msg)

        except Exception as e:
            self.get_logger().error(f'targetコールバックでエラーが発生しました: {e}')

def main(args=None):
    rclpy.init(args=args)
    
    node = TimeDiffCalculator()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        # Ctrl+C
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()