# 多人播客背景音处理 Skill

## 功能概述

这个 Skill 处理多人播客录音中的常见问题：

**场景**: 4个人分别用各自的麦克风录制播客，在同一物理空间录制。虽然某个人没有说话，但该音轨仍会录到其他人较小的声音（背景音），导致最终混音后有过多的环境音。

**解决方案**:
1. **背景音静音** - 识别并软静音这些背景声音段（保留应对音 "嗯、对、是的")
2. **笑声动态压缩** - 检测笑声，当多人同时笑时降低音量以避免爆音

## 快速开始

### 安装依赖

```bash
cd 多人背景处理/scripts
pip install -r requirements.txt
```

### 基本用法

#### 方式1: 完整管道 (推荐快速使用)

```bash
python3 main.py full \
  --input speaker1.wav speaker2.wav speaker3.wav speaker4.wav \
  --output processed_podcast.wav \
  --report report.json
```

#### 方式2: 分步处理

**步骤1: 对齐音频轨道**

```bash
python3 main.py align \
  --input speaker1.wav speaker2.wav speaker3.wav speaker4.wav \
  --output aligned_audio/
```

输出:
- `aligned_audio/track_00_aligned.wav` - 对齐后的第1个说话人音轨
- `aligned_audio/track_01_aligned.wav` - 对齐后的第2个说话人音轨
- `aligned_audio/track_02_aligned.wav` - 对齐后的第3个说话人音轨
- `aligned_audio/track_03_aligned.wav` - 对齐后的第4个说话人音轨
- `aligned_audio/mixed_aligned.wav` - 混合音频（用于检查）
- `aligned_audio/alignment_metadata.json` - 对齐元数据

**步骤2: 处理（背景静音 + 笑声压缩）**

```bash
python3 main.py process \
  --input aligned_audio/ \
  --output processed_podcast.wav \
  --report report.json
```

### 选项说明

#### align 子命令
- `-i, --input` - 输入音频文件路径（至少2个）
- `-o, --output` - 输出目录 (默认: `./aligned_audio`)
- `-sr, --sample-rate` - 目标采样率 (默认: 16000Hz)

#### process 子命令
- `-i, --input` - 对齐后的音频目录
- `-o, --output` - 最终输出音频文件路径 (WAV格式)
- `-r, --report` - JSON报告输出路径 (可选)
- `--skip-background` - 跳过背景音检测和静音
- `--skip-laugh` - 跳过笑声检测和压缩

#### full 子命令
- `-i, --input` - 输入音频文件路径（至少2个）
- `-o, --output` - 最终输出文件路径
- `-r, --report` - 报告输出路径 (可选)
- `-sr, --sample-rate` - 目标采样率 (默认: 16000Hz)
- `--temp-dir` - 临时文件目录 (默认: `./.temp_aligned`)
- `--skip-background` - 跳过背景音静音
- `--skip-laugh` - 跳过笑声压缩

## 工作原理

### Phase 0: 音频对齐预处理 (`audio_alignment.py`)

**目标**: 确保所有音轨从同一时刻开始，长度相同

**算法**:
1. 加载所有音频文件，统一采样率到16kHz
2. 对每个音轨检测实际音频开始点（跳过开头静音）
3. 找到最早的音频开始时刻
4. 所有音轨对齐到该时刻（早的补零，晚的修剪）
5. 补齐长度差异（短的末尾补零）

### Phase 1: 混音与基础分析 (`podcast_background_cleanup.py`)

**功能**: 创建多声道音频对象，生成混合音频用于后续分析

### Phase 2: 背景声音检测 (`background_detection.py`)

**目标**: 识别"说话人没有说话，但音轨中有他人声音"的段落

**算法**:
1. 对每个音轨计算 RMS 能量时间序列（100ms窗口）
2. 计算能量的统计值（中位数、标准差）
3. 设置自适应阈值 = 中位数 - 1σ
4. 能量低于阈值的段 = 背景音
5. 合并间隙<200ms的段，过滤<100ms的短段

**输出**: 每个音轨的背景段列表
```json
{
  "0": [
    {"start": 1.23, "end": 2.45, "duration": 1.22, "energy_ratio": 0.15}
  ]
}
```

### Phase 3: 笑声特征检测 (`laugh_detection.py`)

**目标**: 在混合音频中找到所有笑声段，并判断谁在笑

**特征提取**:
- **MFCC** (13系数) - 捕捉频域特征
- **ZCR** (Zero Crossing Rate) - 检测高频成分（笑声特征）
- **能量突变** - 笑声的快速起伏
- **频谱中心** - 笑声的频率分布特征

**笑声判别**:
- 高能量突变 (快速up/down)
- 高频成分比例高 (ZCR > 50th percentile)
- 足够的能量（避免误检噪音）
- 频谱在笑声范围 (>800Hz)

**多人笑声检测**:
在笑声时间段内，统计各音轨能量，确定谁在笑

**输出**:
```json
{
  "laugh_segments": [
    {
      "start": 12.50,
      "end": 15.30,
      "duration": 2.80,
      "speaker_tracks": [0, 1, 3],
      "num_speakers": 3,
      "confidence": 0.87
    }
  ]
}
```

### Phase 4: 笑声动态压缩 (`dynamic_compression.py`)

**策略**:
- 单人笑 (1人) → 无处理（保留自然声音）
- 2人同时笑 → -3dB (衰减50%)
- 3人同时笑 → -6dB (衰减75%)
- 4人同时笑 → -9dB (衰减87%)

**实现**:
1. 创建时间变化的增益包络（gain envelope）
2. 根据笑声时刻和参与人数计算增益
3. 使用200ms平滑淡入/淡出避免突兀
4. 应用到所有音轨

### Phase 5: 背景音静音处理 (在 `podcast_background_cleanup.py` 中)

**方法**:
1. 对检测到的背景段，应用软淡出（fade-out）
2. 使用50ms淡出曲线，然后零音（静音）
3. 250ms淡出保证平滑过渡

## 参数配置

### 背景音检测参数

在 `podcast_background_cleanup.py` 中调用 `detect_background_noise()` 时:

```python
processor.detect_background_noise(
    energy_window_ms=100,           # 能量窗口 (ms)
    silence_threshold_factor=0.5,   # 阈值因子
    min_silence_duration_ms=100,    # 最小段长 (ms)
    merge_gap_ms=200,               # 合并间隙 (ms)
)
```

**调优建议**:
- 如果背景音检测不足，降低 `silence_threshold_factor` (如0.3)
- 如果过度检测，提高 `silence_threshold_factor` (如0.7)
- 如果遗漏短段，降低 `min_silence_duration_ms`
- 如果检测出碎片，提高 `merge_gap_ms`

### 笑声检测参数

在 `laugh_detection.py` 中调用 `detect_laugh_segments()` 时:

```python
detect_laugh_segments(
    audio,
    sr=16000,
    window_ms=50,              # 特征窗口 (ms)
    min_duration_ms=200,       # 最小笑声长度 (ms)
    merge_gap_ms=150,          # 合并间隙 (ms)
)
```

### 笑声压缩参数

在 `dynamic_compression.py` 中:

```python
apply_laugh_compression(
    tracks,
    sr,
    laugh_segments,
    fade_duration_ms=200,      # 淡入淡出时长
)
```

## 输出文件

### 对齐后的文件 (align 步骤)

```
aligned_audio/
├── track_00_aligned.wav      # 说话人1
├── track_01_aligned.wav      # 说话人2
├── track_02_aligned.wav      # 说话人3
├── track_03_aligned.wav      # 说话人4
├── mixed_aligned.wav         # 混合音频（用于检查）
└── alignment_metadata.json   # 对齐信息
```

### 最终输出文件 (process 步骤)

```
processed_podcast.wav          # 最终处理后的音频（单声道混合）
report.json                    # 处理报告（可选）
```

### 报告内容 (report.json)

```json
{
  "metadata": {
    "target_sample_rate": 16000,
    "num_tracks": 4,
    "total_length_samples": 960000,
    "total_length_seconds": 60.0
  },
  "processing": {
    "background_suppression": {
      "segments_found": 23,
      "total_duration_suppressed_seconds": 8.5
    },
    "laugh_detection": {
      "segments_found": 5,
      "segments": [
        {
          "start": 12.5,
          "end": 15.3,
          "duration": 2.8,
          "speaker_tracks": [0, 1, 3],
          "num_speakers": 3,
          "confidence": 0.87
        }
      ]
    }
  }
}
```

## 常见问题

### Q: 为什么检测出的背景音太多/太少？

**A**: 调整 `silence_threshold_factor` 参数:
- 太少: 降低该值 (如 0.3) 使阈值更低
- 太多: 提高该值 (如 0.7) 使阈值更高

### Q: 如何只做背景音处理，跳过笑声处理？

**A**: 使用 `--skip-laugh` 选项:
```bash
python3 main.py process --input aligned/ --output out.wav --skip-laugh
```

### Q: 为什么输出音频变得很安静？

**A**: 这可能是因为:
1. 背景音过度静音 - 检查 `detection_metadata.json` 的背景段数量
2. 笑声过度压缩 - 增加压缩增益 (在 `dynamic_compression.py` 中修改)
3. 输入文件本身很小 - 检查输入音频的音量

### Q: 可以处理超过4个人的播客吗？

**A**: 可以！脚本支持任意数量的音轨，但压缩公式针对4人设计。
如需调整，编辑 `dynamic_compression.py` 中的 `get_compression_gain_db()` 函数。

## 技术细节

### 依赖库

- **librosa** - 音频分析 (MFCC, ZCR, 能量计算)
- **numpy** - 数值计算和信号处理
- **soundfile** - 音频I/O (WAV格式)

### 采样率

所有处理统一为 16kHz（业界标准语音处理采样率）。
如需不同采样率，使用 `-sr` 参数。

### 音频精度

- 输入: 支持任何格式 (librosa 自动转换)
- 处理: float32 (保证数值精度)
- 输出: WAV float32

## 进阶用法

### 自定义处理参数

修改脚本中的参数:

```python
# background_detection.py 中
processor.detect_background_noise(
    energy_window_ms=150,           # 更长窗口 = 更平滑
    silence_threshold_factor=0.4,   # 更严格的背景检测
)

# laugh_detection.py 中
processor.detect_laugh_sounds()  # 使用默认参数

# dynamic_compression.py 中
processor.apply_laugh_dynamic_compression()  # 使用默认参数
```

### 只输出单个处理步骤

可以创建自定义脚本调用各模块:

```python
from audio_alignment import load_and_align_audio
from background_detection import detect_background_segments
import numpy as np

# 加载和对齐
aligned, sr, metadata = load_and_align_audio([...])

# 仅检测背景音
tracks = np.array(aligned)
backgrounds = detect_background_segments(tracks, sr)

# 只输出检测结果
import json
with open('backgrounds.json', 'w') as f:
    json.dump(backgrounds, f)
```

## 性能

**处理时间** (参考, 基于MacBook Pro M1):
- 60分钟4轨道播客
  - 对齐: ~2秒
  - 背景检测: ~5秒
  - 笑声检测: ~8秒
  - 压缩应用: ~3秒
  - **总计: ~18秒**

**内存使用**:
- 60分钟 @ 16kHz 原始PCM: ~57MB/轨 = ~228MB (4轨)
- 处理过程中峰值: ~500MB

## 常见使用场景

### 场景1: 快速处理一期播客

```bash
# 一条命令，自动对齐+处理
python3 main.py full \
  -i s1.wav s2.wav s3.wav s4.wav \
  -o final.wav
```

### 场景2: 调试和逐步验证

```bash
# 步骤1: 对齐并检查
python3 main.py align -i s1.wav s2.wav s3.wav s4.wav -o aligned/
# 检查 aligned/mixed_aligned.wav

# 步骤2: 只做背景处理，不压缩笑声
python3 main.py process -i aligned/ -o bg_only.wav --skip-laugh

# 步骤3: 检查效果后，再加上笑声处理
python3 main.py process -i aligned/ -o final.wav -r report.json
```

### 场景3: 批量处理多期

```bash
# 创建批处理脚本
for ep in episode*/; do
  python3 main.py full \
    -i "$ep"/s1.wav "$ep"/s2.wav "$ep"/s3.wav "$ep"/s4.wav \
    -o "$ep"/processed.wav \
    -r "$ep"/report.json
done
```

## 后续改进方向

- [ ] 支持应对音（"嗯"、"对"等）的自动保留配置
- [ ] Web UI 用于参数调整和可视化
- [ ] 支持声道级别的压缩（而非整体压缩）
- [ ] 集成到 podcastcut-skills 作为标准 Skill
- [ ] 支持实时处理流

## 许可证

MIT
