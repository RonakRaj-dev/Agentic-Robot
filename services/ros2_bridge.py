import time
from typing import Optional, Dict, Any
from loguru import logger

try:
    import rclpy
    from rclpy.node import Node
    from std_msgs.msg import String
    ROS2_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    rclpy = None
    Node = object
    String = None
    ROS2_AVAILABLE = False


class ROS2ExpressionBridge:
    """
    ROS2 Expression Bridge for Edu-Bot hardware.
    Publishes string messages to topic '/edubot/expression' to synchronize physical
    eye displays (32.5mm TFT), mouth LED matrix (8x8 sine wave), and Dynamixel head servos.
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(ROS2ExpressionBridge, cls).__new__(cls, *args, **kwargs)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, topic_name: str = "/edubot/expression") -> None:
        if self._initialized:
            return
        
        self.topic_name = topic_name
        self.last_expression: Optional[str] = None
        self.last_publish_time: float = 0.0
        self.node = None
        self.publisher = None
        self.ros2_available = ROS2_AVAILABLE

        self._init_ros2()
        self._initialized = True

    def _init_ros2(self) -> None:
        if self.ros2_available:
            try:
                if not rclpy.ok():
                    rclpy.init()
                self.node = Node("edubot_expression_bridge")
                self.publisher = self.node.create_publisher(String, self.topic_name, 10)
                logger.info(f"ROS2ExpressionBridge connected to topic '{self.topic_name}'.")
            except Exception as e:
                logger.warning(f"Failed to initialize ROS2 node ({e}). Using mock bridge logger.")
                self.ros2_available = False
        else:
            logger.info("ROS2 (rclpy) is not installed. ROS2ExpressionBridge running in mock fallback mode.")

    def publish_expression(self, expression_code: str) -> bool:
        """
        Publishes a ROS2 expression message to topic '/edubot/expression'.
        Valid Expression Codes:
          - ACTIVE: EXPRESSION_THINKING, EXPRESSION_NOD, EXPRESSION_SHAKE, EXPRESSION_TALKING
          - PASSIVE: EXPRESSION_BLINK, EXPRESSION_LONG_BLINK, EXPRESSION_LOOK_AROUND
        """
        now = time.time()
        self.last_expression = expression_code
        self.last_publish_time = now

        logger.info(f"🤖 [ROS2 BRIDGE PUBLISH] Topic: '{self.topic_name}' -> Payload: '{expression_code}'")

        if self.ros2_available and self.publisher:
            try:
                msg = String()
                msg.data = expression_code
                self.publisher.publish(msg)
                return True
            except Exception as e:
                logger.error(f"Error publishing ROS2 expression message: {e}")
                return False

        return True

    def get_status(self) -> Dict[str, Any]:
        return {
            "ros2_available": self.ros2_available,
            "topic_name": self.topic_name,
            "last_expression": self.last_expression,
            "last_publish_time": round(self.last_publish_time, 3) if self.last_publish_time > 0 else None
        }


# Global Singleton
ros2_bridge = ROS2ExpressionBridge()
