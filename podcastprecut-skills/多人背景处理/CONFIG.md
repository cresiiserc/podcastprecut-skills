# 参数配置指南

## 快速开始

大多数用户可以使用默认参数直接运行：

```bash
python3 main.py full \
  -i speaker1.wav speaker2.wav speaker3.wav speaker4.wav \
  -o output.wav
```

如果需要微调效果，按照以下指南修改参数。

## 背景音检测参数

### energy_window_ms (默认: 100)

能量计算的时间窗口，以毫秒为单位。

**影响**:
- 较大的值 (150-200ms): 检测更稳定，但可能遗漏短背景段
- 较小的值 (50-75ms): 更敏感，可能导致过度检测

**建议**:
- 对话式播客: 100ms (默认，平衡)
- 快速语速: 75ms (更敏感)
- 闲适风格: 150ms (更稳定)

**调整方法**:

编辑 `podcast_background_cleanup.py`:

```python
processor.detect_background_noise(
    energy_window_ms=150,  # 改这里
)
```

### silence_threshold_factor (默认: 0.5)

背景音阈值因子。值越小，检测越激进；值越大，检测越保守。

**公式**: 阈值 = 中位数能量 - factor × 标准差

**影响**:
- 0.3: 激进检测，可能误检语音间隙
- 0.5: 平衡 (推荐)
- 0.7: 保守检测，可能遗漏背景音

**调整步骤**:

1. 检查输出的检测报告
2. 如果背景音太多未被检测，降低值 (如 0.3)
3. 如果频繁误检，提高值 (如 0.7)

**示例**:

```python
# 激进模式（清楚更多背景）
processor.detect_background_noise(
    silence_threshold_factor=0.3,
)

# 保守模式（避免误检）
processor.detect_background_noise(
    silence_threshold_factor=0.8,
)
```

### min_silence_duration_ms (默认: 100)

检测背景段的最小时长，以毫秒为单位。

**影响**:
- 100ms: 检测所有背景段，包括短暂的
- 200ms: 忽略<200ms的短段
- 500ms: 只检测较长的背景段

**建议**:
- 对于短暂背景： 50-100ms
- 标准设置： 100ms (默认)
- 只处理明显背景： 200-300ms

**调整方法**:

```python
processor.detect_background_noise(
    min_silence_duration_ms=200,  # 改这里
)
```

### merge_gap_ms (默认: 200)

合并相邻背景段的最大间隙，以毫秒为单位。

如果两个背景段相距小于此值，将被合并为一个。

**影响**:
- 100ms: 严格分开
- 200ms: 平衡 (推荐)
- 300-500ms: 更容易合并成大段

**建议**:
- 通常保持默认值 200ms

**调整方法**:

```python
processor.detect_background_noise(
    merge_gap_ms=300,  # 改这里
)
```

## 笑声检测参数

### window_ms (默认: 50)

特征提取的时间窗口。

**影响**:
- 较小的值 (30-50ms): 更高时间分辨率，可能检测更多短笑
- 较大的值 (75-100ms): 更稳定，但可能遗漏短笑

**建议**: 通常保持默认 50ms

### min_duration_ms (默认: 200)

笑声段的最小时长。

**影响**:
- 100ms: 检测所有笑，包括短暂的
- 200ms: 标准笑声
- 500ms: 只检测长笑

**建议**:
- 标准播客: 200ms (默认)
- 高互动播客: 150ms (更敏感)
- 专业播客: 300ms (更稳定)

### merge_gap_ms (默认: 150)

合并相邻笑声段的最大间隙。

**建议**: 通常保持默认值

## 笑声压缩参数

### 压缩量规则

当前规则在 `dynamic_compression.py` 中定义：

```python
def get_compression_gain_db(num_speakers: int) -> float:
    if num_speakers <= 1:
        return 0.0    # 单人：无处理
    elif num_speakers == 2:
        return -3.0   # 2人：-3dB
    elif num_speakers == 3:
        return -6.0   # 3人：-6dB
    else:
        return -9.0   # 4+人：-9dB
```

**调整方法**:

修改返回值以改变压缩量。例如，要让压缩更温和：

```python
def get_compression_gain_db(num_speakers: int) -> float:
    if num_speakers == 2:
        return -2.0   # 改为 -2dB（从 -3dB）
    elif num_speakers == 3:
        return -4.0   # 改为 -4dB（从 -6dB）
    # ...
```

### fade_duration_ms (默认: 200)

压缩增益变化的淡入淡出时长。

**影响**:
- 较短 (100ms): 压缩过渡更快
- 较长 (300-400ms): 过渡更平滑

**建议**: 200ms (默认，平衡)

**调整方法**:

```python
processor.apply_laugh_dynamic_compression()
# 需要修改源代码中的 fade_duration_ms
```

## 对齐参数

### sample_rate (默认: 16000)

目标采样率，以 Hz 为单位。

**常见值**:
- 16000 Hz (16kHz): 标准语音处理采样率 (默认)
- 22050 Hz: CD 质量的一半
- 44100 Hz: CD 质量（占用更多资源）

**建议**: 保持 16000 (语音处理标准)

**调整方法**:

```bash
python3 main.py full \
  -i s1.wav s2.wav s3.wav s4.wav \
  -o output.wav \
  -sr 44100  # 改采样率
```

## 配置预设

### 预设 1: 标准对话播客 (推荐)

```bash
python3 main.py full \
  -i s1.wav s2.wav s3.wav s4.wav \
  -o output.wav
# 使用所有默认参数
```

相当于：
```python
processor.detect_background_noise(
    energy_window_ms=100,
    silence_threshold_factor=0.5,
    min_silence_duration_ms=100,
    merge_gap_ms=200,
)
processor.detect_laugh_segments(window_ms=50, min_duration_ms=200)
processor.apply_laugh_dynamic_compression(fade_duration_ms=200)
```

### 预设 2: 激进背景清理

适合背景音较多的录音。

编辑脚本或自定义调用：

```python
processor.detect_background_noise(
    energy_window_ms=75,
    silence_threshold_factor=0.3,
    min_silence_duration_ms=75,
    merge_gap_ms=150,
)
```

### 预设 3: 保守处理

适合担心误检的情况。

```python
processor.detect_background_noise(
    energy_window_ms=150,
    silence_threshold_factor=0.7,
    min_silence_duration_ms=200,
    merge_gap_ms=300,
)
processor.detect_laugh_segments(min_duration_ms=300)
```

### 预设 4: 只清理背景

跳过笑声处理：

```bash
python3 main.py process \
  -i aligned/ \
  -o output.wav \
  --skip-laugh
```

### 预设 5: 只处理笑声

跳过背景清理：

```bash
python3 main.py process \
  -i aligned/ \
  -o output.wav \
  --skip-background
```

## 调试和验证

### 1. 生成处理报告

```bash
python3 main.py full \
  -i s1.wav s2.wav s3.wav s4.wav \
  -o output.wav \
  -r report.json
```

检查 `report.json` 了解：
- 检测到的背景段数量和总时长
- 检测到的笑声段数量和位置
- 各段的参与人数和置信度

### 2. 分步验证

```bash
# 步骤1: 对齐并检查
python3 main.py align -i s1.wav s2.wav s3.wav s4.wav -o aligned/
# 听 aligned/mixed_aligned.wav 检查对齐

# 步骤2: 只清理背景
python3 main.py process -i aligned/ -o bg_only.wav --skip-laugh
# 听 bg_only.wav 检查背景清理效果

# 步骤3: 添加笑声处理
python3 main.py process -i aligned/ -o final.wav
```

### 3. A/B 对比

生成不同参数的版本对比：

```bash
# 版本1: 激进背景清理
python3 main.py process -i aligned/ -o v1_aggressive.wav

# 版本2: 保守处理
python3 main.py process -i aligned/ -o v2_conservative.wav --skip-laugh

# 手动对比听取效果，选择最好的
```

## 常见场景的推荐参数

### 专业播客工作室录音

```python
processor.detect_background_noise(
    silence_threshold_factor=0.7,  # 更保守
    min_silence_duration_ms=150,
)
```

### 家庭录音（有一定背景音）

```python
processor.detect_background_noise(
    silence_threshold_factor=0.4,  # 更激进
    min_silence_duration_ms=80,
)
```

### 高能量/欢乐播客（笑声多）

```python
processor.detect_laugh_segments(window_ms=50, min_duration_ms=150)
# 笑声检测更敏感
```

### 严肃话题播客（笑声少）

```python
# 使用默认笑声参数，或
python3 main.py process --skip-laugh  # 直接跳过
```

## 如何找到最优参数

### 推荐流程

1. **用默认参数处理一小段** (1-2分钟)
2. **听取效果**
   - 背景音清理是否充分？
   - 是否误检了有效语音？
   - 笑声是否被正确处理？
3. **根据问题调整**
   - 背景音太多未清 → 降低 `silence_threshold_factor`
   - 误检语音间隙 → 提高 `silence_threshold_factor`
   - 笑声太少被检测 → 降低 `min_duration_ms`
4. **重复处理完整文件**

### 参数调整建议

```
问题 → 解决方案

背景音太多未被清理
├─ 降低 silence_threshold_factor (0.5 → 0.3)
├─ 降低 energy_window_ms (100 → 75)
└─ 降低 min_silence_duration_ms (100 → 50)

背景音过度清理（误检）
├─ 提高 silence_threshold_factor (0.5 → 0.7)
├─ 提高 energy_window_ms (100 → 150)
└─ 提高 min_silence_duration_ms (100 → 200)

笑声检测不足
├─ 降低 min_duration_ms (200 → 150)
└─ 降低 energy burst threshold (修改源代码)

笑声误检太多
├─ 提高 min_duration_ms (200 → 300)
└─ --skip-laugh (直接跳过)
```

## 性能与质量的权衡

- **更多检测** = 更好的清理但可能误检
- **更少检测** = 更安全但可能遗漏背景音
- **更大窗口** = 更稳定但时间分辨率更低
- **更小窗口** = 更高分辨率但可能不稳定

## 建议的工作流程

1. 用默认参数处理一期完整播客
2. 如果满意，保持默认参数
3. 如果不满意，记下问题，调整参数
4. 记录最终的最优参数，用于后续剧集

## 许可证

MIT
