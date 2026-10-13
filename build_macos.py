#!/usr/bin/env python3
"""
盲路监控系统 - macOS打包脚本
用法: conda activate ppe_yolo && python build_macos.py
"""
import os
import sys
import subprocess
import shutil
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"

def check_dependencies():
    """检查必要的依赖"""
    print("🔍 检查依赖...")
    
    try:
        import PyInstaller
        print(f"✅ PyInstaller {PyInstaller.__version__}")
    except ImportError:
        print("❌ 未安装PyInstaller")
        print("   运行: pip install pyinstaller")
        sys.exit(1)
    
    # 检查必要文件
    required_files = [
        "main.py",
        "myBlindPathMonitor.py",
        "model/best0217.pt",
        "icons/",
        "templates/"
    ]
    
    for file in required_files:
        path = PROJECT_ROOT / file
        if not path.exists():
            print(f"❌ 缺少必要文件: {file}")
            sys.exit(1)
    
    print("✅ 所有必要文件存在")

def build_app():
    """使用PyInstaller打包.app"""
    print("\n📦 开始打包.app...")
    
    # 清理旧的构建文件
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    
    # 使用.spec文件打包
    spec_file = PROJECT_ROOT / "盲路监控系统.spec"
    
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--clean",
        "--distpath", str(DIST_DIR),
        "--workpath", str(BUILD_DIR),
        str(spec_file)
    ]
    
    print(f"\n🚀 运行命令:")
    print(f"   {' '.join(cmd)}\n")
    
    result = subprocess.run(cmd, cwd=PROJECT_ROOT)
    
    if result.returncode != 0:
        print("❌ 打包失败!")
        sys.exit(1)
    
    app_path = DIST_DIR / "盲路监控系统.app"
    if app_path.exists():
        print(f"✅ 打包成功: {app_path}")
        
        # 验证资源文件
        resources = app_path / "Contents" / "Resources"
        print(f"\n🔍 验证资源文件:")
        for folder in ['model', 'icons', 'templates']:
            path = resources / folder
            if path.exists():
                print(f"   ✅ {folder}/")
            else:
                print(f"   ❌ {folder}/ - 缺失!")
        
        return app_path
    else:
        print("❌ 未找到.app文件")
        sys.exit(1)

def create_dmg(app_path):
    """创建DMG安装包"""
    print("\n💿 创建DMG安装包...")
    
    dmg_path = DIST_DIR / "盲路监控系统_Installer.dmg"
    temp_dir = DIST_DIR / "dmg_temp"
    
    # 删除旧的DMG和临时目录
    if dmg_path.exists():
        dmg_path.unlink()
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    
    # 创建临时目录
    temp_dir.mkdir()
    
    # 复制.app到临时目录
    shutil.copytree(app_path, temp_dir / app_path.name)
    
    # 创建Applications快捷方式
    os.symlink("/Applications", temp_dir / "Applications")
    
    # 使用hdiutil创建DMG
    cmd = [
        "hdiutil", "create",
        "-volname", "盲路监控系统",
        "-srcfolder", str(temp_dir),
        "-ov",
        "-format", "UDZO",
        str(dmg_path)
    ]
    
    print(f"🚀 运行命令:")
    print(f"   {' '.join(cmd)}\n")
    
    result = subprocess.run(cmd)
    
    # 清理临时目录
    shutil.rmtree(temp_dir)
    
    if result.returncode != 0:
        print("❌ DMG创建失败")
        sys.exit(1)
    
    print(f"✅ DMG创建成功: {dmg_path}")
    return dmg_path

def main():
    print("=" * 60)
    print("盲路监控系统 - macOS打包工具")
    print("=" * 60)
    
    check_dependencies()
    app_path = build_app()
    dmg_path = create_dmg(app_path)
    
    print("\n" + "=" * 60)
    print("✅ 打包完成!")
    print("=" * 60)
    print(f"\n📁 输出文件:")
    print(f"   .app应用: {app_path}")
    print(f"   .dmg安装包: {dmg_path}")
    print(f"\n📝 使用说明:")
    print(f"   1. 将 {dmg_path} 分发给用户")
    print(f"   2. 用户双击DMG文件")
    print(f"   3. 拖拽.app到Applications文件夹")
    print(f"   4. 从Launchpad或Applications运行")

if __name__ == "__main__":
    main()