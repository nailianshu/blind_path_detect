from ultralytics import YOLO
import cv2
import numpy as np

print("load model...")
model = YOLO("./model/blindpath_seg_annotation_model_pretrained.pt")
print("model loaded...")

# 打开视频流
cap = cv2.VideoCapture('./video/walk_demo.mp4')

cv2.namedWindow('belt', cv2.WINDOW_NORMAL)

# 视频帧循环读取
while cap.isOpened():
    ret, frame = cap.read()  # ret是否读到帧，frame就是当前图片帧
    if not ret:
        break  # 读到视频末尾退出循环

    # 对每一帧做推理，传入的是frame（numpy图像数组）不是cap对象
    results = model.predict(frame, device="mps",conf=0.7,verbose=False)
    print('length of results:', len(results))
    result = results[0]

    boxes = result.boxes
    xyxy = boxes.xyxy
    cls = boxes.cls
    conf = boxes.conf
    print('xyxy:', xyxy)
    print('cls:', cls)
    print('conf:', conf)

    # mask必须判空，没有分割mask不要访问.xy，否则报错
    if result.masks is not None:
        masks = result.masks
        print('length of mask:', len(masks.xy))
        pixel_coords = masks.xy

        for i in range(len(pixel_coords)):
            # 如果需要过滤类别可以打开注释
            # if int(cls[i].item()) == 0:
            pts = np.asarray(pixel_coords[i], dtype=np.int32)
            cv2.polylines(frame, [pts], True, (0, 0, 255), thickness=2)

    cv2.imshow("belt", frame)

    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
