# 安装和配置

## 系统要求

- Python 3.8+
- 足够的磁盘空间 (处理时有临时文件)
- 足够的内存 (推荐 4GB+ for 1小时 4轨道音频)

## 快速安装

### 1. 安装 Python 依赖

```bash
cd /Users/cresiihyperion/podcast_editor/podcastcut-skills/多人背景处理/scripts
pip install -r requirements.txt
```

### 2. 验证安装

```bash
python3 -c "import librosa, numpy, soundfile; print('✓ All dependencies installed')"
```

### 3. 运行测试 (可选)

```bash
python3 test_modules.py
```

## 详细安装步骤

### macOS

```bash
# 1. 确保安装了 Python 3
python3 --version

# 2. 升级 pip
python3 -m pip install --upgrade pip

# 3. 安装依赖
cd 多人背景处理/scripts
pip install -r requirements.txt

# 4. 测试
python3 -c "import librosa; print('✓ librosa installed')"
```

### Linux (Ubuntu/Debian)

```bash
# 1. 安装系统依赖
sudo apt-get install python3-pip libsndfile1

# 2. 升级 pip
pip3 install --upgrade pip

# 3. 安装 Python 依赖
cd 多人背景处理/scripts
pip3 install -r requirements.txt
```

### Windows

```bash
# 1. 使用 PowerShell 或 Command Prompt
python --version

# 2. 升级 pip
python -m pip install --upgrade pip

# 3. 安装依赖
cd 多人背景处理/scripts
pip install -r requirements.txt
```

## 依赖说明

### librosa (>=0.10.0)
- 音频分析库
- 用于: MFCC、ZCR、RMS 能量、spectral 特征计算
- GitHub: https://librosa.org/

### numpy (>=1.24.0)
- 数值计算库
- 用于: 矩阵运算、统计计算、信号处理

### soundfile (>=0.12.0)
- 音频 I/O 库
- 用于: 读写 WAV 文件

## 虚拟环境 (推荐)

如果你有多个 Python 项目，推荐使用虚拟环境隔离依赖：

### 创建虚拟环境

```bash
cd /Users/cresiihyperion/podcast_editor/podcastcut-skills/多人背景处理
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# 或
venv\Scripts\activate  # Windows
```

### 在虚拟环境中安装依赖

```bash
pip install -r scripts/requirements.txt
```

### 退出虚拟环境

```bash
deactivate
```

## 故障排除

### 问题: "No module named 'librosa'"

**解决**:
```bash
pip install librosa --upgrade
```

### 问题: "soundfile: Error loading library"

这通常在 Linux 上发生，需要安装系统库：

```bash
# Ubuntu/Debian
sudo apt-get install libsndfile1

# Fedora
sudo dnf install libsndfile

# macOS
brew install libsndfile
```

### 问题: pip 安装缓慢

**解决**: 使用国内镜像 (以阿里云为例):

```bash
pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
```

或修改 `~/.pip/pip.conf`:

```ini
[global]
index-url = https://mirrors.aliyun.com/pypi/simple/
```

### 问题: 内存不足

如果处理大文件时出现内存不足：

1. 关闭其他应用程序
2. 使用 `--skip-laugh` 选项减少内存占用
3. 分批处理更小的文件

## 升级依赖

### 升级单个依赖

```bash
pip install librosa --upgrade
```

### 升级所有依赖

```bash
pip install -r requirements.txt --upgrade
```

## Docker (可选)

如果你使用 Docker 容器化应用：

```dockerfile
FROM python:3.11-slim

# 安装系统依赖
RUN apt-get update && apt-get install -y libsndfile1

# 复制代码
WORKDIR /app
COPY scripts/ .

# 安装 Python 依赖
RUN pip install -r requirements.txt

# 默认命令
ENTRYPOINT ["python3", "main.py"]
```

构建和运行：

```bash
docker build -t podcast-cleaner .
docker run -v /path/to/audio:/data podcast-cleaner full -i /data/s*.wav -o /data/output.wav
```

## 开发环境设置

如果你想修改代码，推荐安装额外的开发工具：

```bash
pip install pytest pytest-cov black flake8 mypy
```

### 运行代码检查

```bash
# 代码格式
black *.py

# Linting
flake8 *.py

# 类型检查
mypy *.py --ignore-missing-imports

# 单元测试
pytest test_modules.py -v
```

## 更新检查

定期检查并更新依赖以获得最新功能和安全补丁：

```bash
pip list --outdated
pip install -r requirements.txt --upgrade
```

## 卸载

如果需要完全卸载：

```bash
pip uninstall librosa numpy soundfile
```

或如果使用虚拟环境，直接删除虚拟环境目录即可：

```bash
rm -rf venv
```

## 许可证和归属

- librosa: BSD License
- numpy: BSD License
- soundfile: BSD License

## 支持

如遇到问题，请：

1. 检查 Python 版本 >= 3.8
2. 确保依赖正确安装
3. 参考 SKILL.md 的故障排除部分
4. 运行 `test_modules.py` 验证安装
