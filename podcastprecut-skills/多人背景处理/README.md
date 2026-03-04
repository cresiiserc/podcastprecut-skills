# 多人播客背景音处理 Skill

完整的Python工具套件，用于处理多人播客录音中的背景音和笑声问题。

## 🎯 功能

- **音频对齐** - 自动对齐多个说话人的分离录音
- **背景音清理** - 智能检测并静音背景声音
- **笑声检测** - 识别播客中的笑声段落
- **笑声压缩** - 自动降低多人同时笑的音量，避免爆音

## ⚡ 快速开始

### 1. 安装依赖

```bash
cd scripts
pip install -r requirements.txt
```

### 2. 处理您的播客

```bash
python3 main.py full \
  -i speaker1.wav speaker2.wav speaker3.wav speaker4.wav \
  -o processed.wav \
  -r report.json
```

完成！查看 `processed.wav` 获得清理后的音频。

## 📖 文档

- **[SKILL.md](SKILL.md)** - 完整功能文档和使用指南 (推荐首先阅读)
- **[INSTALL.md](INSTALL.md)** - 详细安装步骤
- **[CONFIG.md](CONFIG.md)** - 参数调整指南
- **[scripts/README.md](scripts/README.md)** - 脚本和模块说明

## 🛠️ 命令

### align - 对齐多个音频文件

```bash
python3 main.py align \
  -i speaker1.wav speaker2.wav speaker3.wav speaker4.wav \
  -o aligned_audio/
```

输出对齐后的音轨和混合音频。

### process - 处理已对齐的音频

```bash
python3 main.py process \
  -i aligned_audio/ \
  -o output.wav \
  -r report.json
```

可选:
- `--skip-background` - 跳过背景音处理
- `--skip-laugh` - 跳过笑声处理

### full - 完整管道

```bash
python3 main.py full \
  -i s1.wav s2.wav s3.wav s4.wav \
  -o output.wav \
  -r report.json
```

一条命令完成对齐+处理。

## 📊 工作原理

### Phase 0: 音频对齐
确保所有音轨从同一时刻开始，长度相同。

### Phase 2: 背景音检测与静音
使用RMS能量分析，识别"说话人不说话但音轨有背景"的段落，并软静音。

### Phase 3: 笑声检测
通过MFCC、ZCR等特征，识别播客中的笑声，并判断谁在笑。

### Phase 4: 动态压缩
根据笑声中的参与人数自动降低音量：
- 1人: 无处理
- 2人: -3dB
- 3人: -6dB  
- 4人: -9dB

## 🔧 配置

基本参数已预设合理默认值。如需微调，参考 [CONFIG.md](CONFIG.md)。

常见调整:
- **背景音过多未清理** → 降低 `silence_threshold_factor` (0.3)
- **过度清理/误检** → 提高 `silence_threshold_factor` (0.7)
- **笑声检测不足** → 降低 `min_duration_ms` (150)

## 📋 输出

```
processed.wav           # 最终处理后的音频（单声道混合）
report.json            # 处理报告（检测到的背景段、笑声位置等）
```

## 🧪 测试

运行单元测试验证安装:

```bash
cd scripts
python3 test_modules.py
```

## 📈 性能

处理 60 分钟 4 轨道播客 (M1 Mac):
- 对齐: ~2 秒
- 背景检测: ~5 秒
- 笑声检测: ~8 秒
- 总计: ~15-20 秒

内存占用: ~500MB 峰值

## 📚 技术栈

- **Python 3.8+**
- librosa - 音频分析
- numpy - 数值计算
- soundfile - 音频 I/O

## ⚠️ 系统要求

- Python 3.8+
- 4GB+ RAM
- 足够的磁盘空间

## 🐛 故障排除

### "No module named 'librosa'"

```bash
pip install librosa --upgrade
```

### 处理大文件时内存不足

1. 关闭其他应用
2. 使用 `--skip-laugh` 减少内存占用
3. 考虑分段处理

详见 [INSTALL.md](INSTALL.md) 的故障排除部分。

## 💡 使用场景

### 对话型播客
默认参数即可，背景清理和笑声压缩都效果很好。

### 高互动播客（多笑）
可能需要降低 `laugh_min_duration_ms` 以捕捉所有笑声。

### 专业录音棚
可提高 `silence_threshold_factor` 以减少误检。

## 📝 许可证

MIT

## 🔗 相关资源

- [podcastcut-skills](../) - 播客剪辑工具集
- [librosa 文档](https://librosa.org/)

## 📧 反馈

如有问题或建议，请参考项目文档或修改源代码。

---

**提示**: 第一次使用建议先看 [SKILL.md](SKILL.md) 了解完整功能。
