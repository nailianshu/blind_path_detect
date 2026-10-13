# 盲路监控系统 - macOS打包指南

## 📋 打包前准备

### 1. 激活conda环境
```bash
conda activate ppe_yolo
```

### 2. 安装PyInstaller(如果还没装)
```bash
pip install pyinstaller
```

### 3. 准备图标文件(可选)
- 创建1024x1024的PNG图标
- 转换为.icns格式:
  ```bash
  mkdir icon.iconset
  sips -z 16 16 icon.png --out icon.iconset/icon_16x16.png
  sips -z 32 32 icon.png --out icon.iconset/icon_16x16@2x.png
  sips -z 32 32 icon.png --out icon.iconset/icon_32x32.png
  sips -z 64 64 icon.png --out icon.iconset/icon_32x32@2x.png
  sips -z 128 128 icon.png --out icon.iconset/icon_128x128.png
  sips -z 256 256 icon.png --out icon.iconset/icon_128x128@2x.png
  sips -z 256 256 icon.png --out icon.iconset/icon_256x256.png
  sips -z 512 512 icon.png --out icon.iconset/icon_256x256@2x.png
  sips -z 512 512 icon.png --out icon.iconset/icon_512x512.png
  cp icon.png icon.iconset/icon_512x512@2x.png
  iconutil -c icns icon.iconset -o icons/app.icns
  ```

## 🚀 打包步骤

### 使用打包脚本(唯一推荐方法)
```bash
conda activate ppe_yolo
python build_macos.py
```

**重要**: 必须使用.spec文件打包,否则资源文件不会被正确包含!

## 📦 交付物

打包完成后会生成:
- `dist/盲路监控系统.app` - 可直接运行的应用
- `dist/盲路监控系统_Installer.dmg` - 安装包

## 🎯 用户安装流程

1. 用户下载`盲路监控系统_Installer.dmg`
2. 双击DMG文件挂载
3. 拖拽`盲路监控系统.app`到`Applications`文件夹
4. 从Launchpad或Applications打开
5. 首次运行可能需要右键"打开"确认(因为未签名)

## ⚠️ 注意事项

### 路径问题已修复
- 使用`get_resource_path()`函数获取资源路径
- 兼容开发环境和打包后的.app
- 模型、图标、模板文件都会正确加载

### 语音功能
- macOS使用系统`say`命令(已内置)
- Windows回退到`pyttsx3`
- 打包后语音功能正常工作

### 首次运行提示
由于应用未签名,macOS可能提示"无法验证开发者":
1. 右键点击.app
2. 选择"打开"
3. 在弹出的对话框中点击"打开"

## 🔧 故障排除

### 问题: 找不到模型文件
**解决**: 确保打包时使用了`--add-data "model:model"`

### 问题: 应用无法打开
**解决**: 检查Console.app中的错误日志

### 问题: 语音不工作
**解决**: 检查系统设置→声音→输出,确保有输出设备

### 问题: 摄像头权限
**解决**: 首次使用摄像头时,macOS会弹出权限请求,点击"允许"

## 📝 打包原理

```
你的conda环境 (ppe_yolo):
/Users/nilianshu/miniconda3/envs/ppe_yolo/
├── bin/python
├── lib/python3.9/site-packages/
│   ├── PyQt5/
│   ├── cv2/
│   ├── ultralytics/
│   ├── numpy/
│   └── flask/
    ↓ (PyInstaller打包)
盲路监控系统.app (完全独立,无需conda环境)
├── Contents/
│   ├── MacOS/
│   │   └── 盲路监控系统  ← 独立可执行文件
│   └── Resources/
│       ├── Python运行时(已打包)
│       ├── 所有依赖库(已打包)
│       ├── model/
│       ├── icons/
│       └── templates/
```

用户拿到后**直接双击运行**,完全不需要conda环境!