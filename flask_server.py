"""
Flask 实时视频流服务器
用于远程监视盲道检测界面
"""
import threading
import time
from flask import Flask, Response, render_template

app = Flask(__name__)

# 全局帧缓冲（线程安全）
class FrameBuffer:
    def __init__(self):
        self._frame = None
        self._lock = threading.Lock()
        self._metrics = {}
    
    def update(self, frame, metrics=None):
        """更新当前帧"""
        with self._lock:
            self._frame = frame
            if metrics:
                self._metrics = metrics
    
    def get_frame(self):
        """获取当前帧"""
        with self._lock:
            return self._frame, self._metrics.copy()

frame_buffer = FrameBuffer()


def generate_frames():
    """MJPEG 视频流生成器"""
    while True:
        frame, metrics = frame_buffer.get_frame()
        if frame is not None:
            # 将 numpy 数组编码为 JPEG
            import cv2
            import numpy as np
            
            # 在帧上叠加指标信息
            if metrics and metrics.get('valid', False):
                overlay = frame.copy()
                h, w = overlay.shape[:2]
                
                # 显示偏移和角度
                offset = metrics.get('offset', 0)
                angle = metrics.get('angle', 0)
                state = metrics.get('state', '未知')
                
                # 左上角信息面板
                info_text = [
                    f"State: {state}",
                    f"Offset: {offset*100:.1f}%",
                    f"Angle: {angle:.1f}°",
                ]
                
                y_offset = 30
                for text in info_text:
                    cv2.putText(overlay, text, (10, y_offset),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                    y_offset += 25
                
                frame = overlay
            
            # 编码为 JPEG
            ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if ret:
                frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        
        # 控制帧率（约 15 FPS）
        time.sleep(0.067)


@app.route('/')
def index():
    """主页：显示监控界面"""
    return render_template('index.html')


@app.route('/video_feed')
def video_feed():
    """MJPEG 视频流端点"""
    return Response(
        generate_frames(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )


@app.route('/api/status')
def api_status():
    """API：获取当前指标"""
    _, metrics = frame_buffer.get_frame()
    return metrics


def start_flask_server(host='0.0.0.0', port=5000):
    """启动 Flask 服务器（在后台线程中运行）"""
    # 尝试多个端口（5000-5010）
    ports_to_try = list(range(port, port + 11))
    actual_port = None
    
    for test_port in ports_to_try:
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((host, test_port))
            sock.close()
            actual_port = test_port
            break
        except OSError:
            continue
    
    if actual_port is None:
        print(f"\n❌ 错误：无法找到可用端口（尝试了 {ports_to_try[0]}-{ports_to_try[-1]}）")
        return
    
    print(f"\n{'='*50}")
    print(f"🌐 Flask 远程监视服务器已启动！")
    print(f"📡 本地访问: http://localhost:{actual_port}")
    print(f" 远程访问: http://<你的IP>:{actual_port}")
    print(f"💡 提示：在浏览器中打开上面的地址即可看到实时画面")
    print(f"{'='*50}\n")
    
    # 关闭 Flask 的默认日志
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    
    app.run(host=host, port=actual_port, threaded=True, use_reloader=False)


def start_flask_in_background(host='0.0.0.0', port=5000):
    """在后台线程启动 Flask"""
    flask_thread = threading.Thread(
        target=start_flask_server,
        args=(host, port),
        daemon=True
    )
    flask_thread.start()
    return flask_thread