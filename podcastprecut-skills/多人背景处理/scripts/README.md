# 多人播客背景音处理 - 脚本说明

## 项目结构

```
多人背景处理/
├── SKILL.md                           # 完整文档和使用指南
└── scripts/
    ├── main.py                        # 主入口（所有命令统一入口）
    ├── audio_alignment.py             # Phase 0: 音频对齐预处理
    ├── podcast_background_cleanup.py  # Phase 1-2: 主处理管道
    ├── background_detection.py        # Phase 2: 背景音检测
    ├── laugh_detection.py             # Phase 3: 笑声检测
    ├── dynamic_compression.py         # Phase 4: 笑声压缩
    ├── requirements.txt               # Python依赖
    └── README.md                      # 本文件
```

## 脚本说明

### main.py - 主入口
所有操作的统一入口，提供三个子命令:
- `align` - 对齐多个音频文件
- `process` - 处理已对齐的音频（背景+笑声）
- `full` - 完整管道（对齐+处理）

### audio_alignment.py - 音频对齐 (Phase 0)
**目的**: 确保多个音轨同步
- 加载所有音频，统一到16kHz
- 检测每个音轨的实际音频起点
- 对齐所有音轨到同一起点
- 补齐长度差异

**关键函数**:
- `load_and_align_audio()` - 加载并对齐音频
- `detect_silence_start()` - 检测音频起点

### podcast_background_cleanup.py - 主处理管道 (Phase 1-2)
**目的**: 协调所有处理模块的主类

**关键类**:
- `MultiTrackAudioProcessor` - 主处理器，集成所有步骤

**关键方法**:
- `load_tracks()` - 加载已对齐的音轨
- `create_mixed_audio()` - 生成混合音频
- `detect_background_noise()` - 检测背景音
- `suppress_background_noise()` - 静音背景音
- `detect_laugh_sounds()` - 检测笑声
- `apply_laugh_dynamic_compression()` - 压缩笑声
- `create_final_mixed_audio()` - 生成最终音频

### background_detection.py - 背景音检测 (Phase 2)
**目的**: 识别"说话人不说话但音轨有背景音"的段落

**算法**:
1. 计算RMS能量时间序列（100ms窗口）
2. 基于中位数和标准差设置阈值
3. 找到能量低于阈值的连续段
4. 合并相邻段，过滤短段

**关键函数**:
- `detect_background_segments()` - 检测所有音轨的背景音
- `detect_background_in_track()` - 单音轨检测
- `calculate_energy_time_series()` - 计算能量时间序列

**可调参数**:
- `energy_window_ms` - 能量计算窗口 (100ms)
- `silence_threshold_factor` - 阈值因子 (0.5)
- `min_silence_duration_ms` - 最小段长 (100ms)
- `merge_gap_ms` - 合并间隙 (200ms)

### laugh_detection.py - 笑声检测 (Phase 3)
**目的**: 在混合音频中找到笑声，判断谁在笑

**特征**:
- MFCC (13系数) - 频域特征
- ZCR (Zero Crossing Rate) - 高频指示
- 能量突变 - 快速变化
- 频谱中心 - 频率分布

**关键函数**:
- `detect_laugh_segments()` - 检测笑声段
- `analyze_speaker_participation()` - 判断哪些人在笑
- `extract_features()` - 特征提取
- `detect_laugh_frames()` - 帧级笑声检测
- `calculate_energy_bursts()` - 检测能量突变

**可调参数**:
- `window_ms` - 特征窗口 (50ms)
- `min_duration_ms` - 最小笑声长度 (200ms)
- `merge_gap_ms` - 合并间隙 (150ms)

### dynamic_compression.py - 笑声压缩 (Phase 4)
**目的**: 根据笑声人数应用动态衰减

**压缩规则**:
- 1人: 0dB (无处理)
- 2人: -3dB (衰减50%)
- 3人: -6dB (衰减75%)
- 4人: -9dB (衰减87%)

**关键函数**:
- `apply_laugh_compression()` - 应用压缩到多轨道
- `create_gain_envelope()` - 创建时间变化的增益
- `get_compression_gain_db()` - 根据人数获取压缩量
- `apply_smooth_envelope()` - 平滑增益变化

**可调参数**:
- `fade_duration_ms` - 淡入淡出时长 (200ms)

## 使用示例

### 例1: 完整管道 (推荐)

```bash
python3 main.py full \
  -i speaker1.wav speaker2.wav speaker3.wav speaker4.wav \
  -o processed.wav \
  -r report.json
```

### 例2: 分步处理（用于调试）

```bash
# 步骤1: 对齐
python3 main.py align \
  -i s1.wav s2.wav s3.wav s4.wav \
  -o aligned/

# 检查对齐结果
# ffplay aligned/mixed_aligned.wav

# 步骤2: 处理
python3 main.py process \
  -i aligned/ \
  -o processed.wav \
  -r report.json
```

### 例3: 只做背景处理

```bash
python3 main.py process \
  -i aligned/ \
  -o bg_only.wav \
  --skip-laugh
```

### 例4: 只做笑声处理

```bash
python3 main.py process \
  -i aligned/ \
  -o laugh_only.wav \
  --skip-background
```

## 模块依赖关系

```
main.py
├── align 命令
│   └── audio_alignment.py
│       ├── librosa.load()
│       ├── soundfile.write()
│       └── numpy
│
└── process/full 命令
    └── podcast_background_cleanup.py
        ├── background_detection.py
        │   └── librosa (RMS, split)
        ├── laugh_detection.py
        │   └── librosa (MFCC, ZCR, centroid)
        ├── dynamic_compression.py
        │   └── numpy
        └── soundfile.write()
```

## 性能优化建议

### 内存优化
如果处理大文件 (>1小时):
1. 使用较大的 `energy_window_ms` (150-200ms) 来减少计算
2. 考虑分段处理（自定义脚本）

### 速度优化
1. 对齐步骤是最快的 (~0.03s/min)
2. 笑声检测是最慢的 (~0.13s/min) - 特征提取开销
3. 可以并行处理不同频率段（高级优化）

## 调试技巧

### 查看中间结果

```python
from pathlib import Path
import soundfile as sf
from audio_alignment import load_and_align_audio

# 查看对齐后的音频
aligned, sr, meta = load_and_align_audio(['s1.wav', 's2.wav', 's3.wav', 's4.wav'])
sf.write('debug_track0.wav', aligned[0], sr)
sf.write('debug_mixed.wav', aligned.mean(axis=0), sr)
```

### 查看检测结果

```python
import json
from background_detection import detect_background_segments

# 在 podcast_background_cleanup.py 的 process 步骤中
# 检查 processor.background_segments
print(json.dumps(processor.background_segments, indent=2))

# 检查 processor.laugh_segments
print(json.dumps([s for s in processor.laugh_segments], indent=2, default=str))
```

### 调整参数进行实验

```python
processor.detect_background_noise(
    energy_window_ms=150,         # 试试更大的窗口
    silence_threshold_factor=0.3, # 试试更激进的阈值
)
```

## 常见错误

### "File not found" 错误

确保:
1. 输入文件路径正确
2. 使用绝对路径或确保在正确的工作目录

### "Metadata file not found" 错误

必须先运行 `align` 步骤生成 `alignment_metadata.json`

### 输出音频太安静

1. 检查检测到的背景段数量（可能过度静音）
2. 检查输入文件的音量
3. 调整压缩参数

## 修改和扩展

### 修改背景音检测算法

编辑 `background_detection.py` 的 `detect_laugh_frames()` 函数

### 修改笑声检测算法

编辑 `laugh_detection.py` 的 `detect_laugh_frames()` 函数

### 添加新的音频处理步骤

1. 创建新模块 (如 `echo_removal.py`)
2. 在 `podcast_background_cleanup.py` 中添加方法
3. 在 `main.py` 中添加命令行选项

### 修改压缩规则

编辑 `dynamic_compression.py` 的 `get_compression_gain_db()` 函数

## 测试

项目包含每个模块的独立 demo 脚本：

```bash
# 测试背景检测
python3 background_detection.py

# 测试笑声检测
python3 laugh_detection.py

# 测试压缩
python3 dynamic_compression.py
```

## 许可证

MIT
