# """
# 快速转换脚本 - 一键将YOLOv8模型转换为ONNX
# """

# from ultralytics import YOLO
# from pathlib import Path

# def quick_convert():
#     """快速转换函数"""
    
#     # 模型路径
#     model_path = '/Users/nilianshu/Downloads/best0217.pt'
#     output_path = './models/gesture_segmentation5.onnx'
    
#     # 检查模型是否存在
#     if not Path(model_path).exists():
#         print(f"❌ 模型文件不存在: {model_path}")
#         return False
    
#     # 创建输出目录
#     Path('./models').mkdir(exist_ok=True)
    
#     try:
#         # 加载模型
#         print("🔍 加载YOLOv8模型...")
#         model = YOLO(model_path)
        
#         # 导出为ONNX
#         print("🔄 转换为ONNX格式...")
#         model.export(
#             format='onnx',
#             imgsz=640,      # 与训练时相同的尺寸
#             opset=12,       # ONNX算子集版本
#             simplify=True,  # 简化模型
#             dynamic=False,  # 固定输入尺寸
#             device='cpu'    # 在CPU上导出
#         )
        
#         # 重命名文件
#         exported_path = model_path.replace('.pt', '.onnx')
#         if Path(exported_path).exists():
#             Path(exported_path).rename(output_path)
#             print(f"✅ 转换成功!")
#             print(f"📁 ONNX模型保存到: {output_path}")
            
#             # 文件大小信息
#             file_size = Path(output_path).stat().st_size / (1024 * 1024)  # MB
#             print(f"📊 文件大小: {file_size:.2f} MB")
            
#             return True
#         else:
#             print("❌ 转换失败，ONNX文件未生成")
#             return False
            
#     except Exception as e:
#         print(f"❌ 转换过程中出错: {str(e)}")
#         return False

# if __name__ == "__main__":
#     print("🚀 YOLOv8快速转换为ONNX")
#     print("=" * 30)
    
#     if quick_convert():
#         print("\\n🎉 转换完成！")
#         print("现在你可以使用ONNX模型进行推理了。")
#     else:
#         print("\\n❌ 转换失败，请检查错误信息。")

from ultralytics import YOLO

# Load a model
model = YOLO("/Users/nilianshu/Downloads/tp_detect/model/blindpath_seg_annotation_model.pt")  # load an official model

# Export the model
model.export(format="onnx")