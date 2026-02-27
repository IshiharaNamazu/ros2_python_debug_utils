import rclpy
from rclpy.node import Node
from rosidl_runtime_py.utilities import get_message
import csv
import os
import sys

from topic_delay_param import target_topic_name, output_file_name, topic_type

class TopicDelayNode(Node):
    def __init__(self):
        super().__init__('topic_delay_node')

        self.get_logger().info(f'Target Topic: {target_topic_name}')
        self.get_logger().info(f'Output CSV File: {output_file_name}')

        # CSVファイルの準備
        self.file_exists = os.path.isfile(output_file_name)
        try:
            self.csv_file = open(output_file_name, 'a', newline='')
            self.csv_writer = csv.writer(self.csv_file)
            if not self.file_exists:
                self.csv_writer.writerow(['reception_time_sec', 'message_time_sec', 'delay_ms'])
                self.csv_file.flush()
        except IOError as e:
            self.get_logger().error(f"Could not open CSV file '{output_file_name}': {e}")
            sys.exit(1) # エラーが発生した場合は終了

        # サブスクライバの作成（トピックの型を動的に取得）
        self.topic_type = self.get_topic_type(target_topic_name)
        if self.topic_type:
            self.subscription = self.create_subscription(
                self.topic_type,
                target_topic_name,
                self.listener_callback,
                10) # QoS history depth
            self.get_logger().info(f"Subscribing to topic '{target_topic_name}' with type '{self.topic_type.__name__}'")
        else:
            self.get_logger().error(f"Could not determine the type for topic '{target_topic_name}'. "
                                    "Please ensure the topic is active or specify its type manually.")
            self.destroy_node()
            rclpy.shutdown()
            sys.exit(1)

    def listener_callback(self, msg):
        reception_time = self.get_clock().now()

        # メッセージに 'header' と 'stamp' があるかチェック
        if hasattr(msg, 'header') and hasattr(msg.header, 'stamp'):
            message_time = rclpy.time.Time.from_msg(msg.header.stamp)
            delay_ms = (reception_time.nanoseconds - message_time.nanoseconds) / 1e6

            self.csv_writer.writerow([reception_time.nanoseconds/1e9, message_time.nanoseconds/1e9, delay_ms])
            self.csv_file.flush() # データをすぐにファイルに書き込む
        else:
            self.get_logger().warn('Message does not have a "header.stamp" field. Cannot calculate delay.')

    def on_shutdown(self):
        self.get_logger().info('Shutting down and closing CSV file.')
        # CSVファイルを閉じる
        if hasattr(self, 'csv_file') and self.csv_file:
            self.csv_file.close()

def main(args=None):
    rclpy.init(args=args)
    topic_delay_node = None
    try:
        topic_delay_node = TopicDelayNode()
        rclpy.spin(topic_delay_node)
    except KeyboardInterrupt:
        topic_delay_node.get_logger().info('KeyboardInterrupt received, shutting down.')
    except Exception as e:
        if topic_delay_node:
            topic_delay_node.get_logger().error(f"An unexpected error occurred: {e}")
        else:
            print(f"An unexpected error occurred before node initialization: {e}", file=sys.stderr)
    finally:
        if topic_delay_node:
            topic_delay_node.on_shutdown()
            topic_delay_node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()