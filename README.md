# 网易云音乐VIP歌曲管理工具

自动扫描网易云音乐"我喜欢的音乐"列表，识别VIP专属歌曲，将其添加到指定歌单并取消喜欢标记。

## ✨ 功能特性

- 🔐 **多种登录方式**：支持二维码扫码登录、手机号验证码登录
- 🎵 **智能识别**：自动识别VIP专属歌曲和VIP高音质歌曲
- 📋 **批量操作**：批量添加歌曲到歌单，批量取消喜欢标记
- 🔄 **增量更新**：避免重复添加已存在的歌曲
- 🧪 **Dry-Run模式**：先预览再操作，安全可靠
- 📊 **进度显示**：美观的终端界面，实时显示操作进度
- 📝 **日志记录**：详细的操作日志，便于追踪和调试

## 📦 安装步骤

### 1. 克隆或下载项目

```bash
cd d:\Project\Self\tool_by_python
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置（可选）

复制配置文件模板并根据需要修改：

```bash
copy config.ini.example config.ini
```

配置文件说明：

```ini
[auth]
# 登录方式: qr_code (推荐) / phone
login_method = qr_code

[settings]
# VIP歌单ID（留空则自动创建）
vip_playlist_id = 

# VIP歌单名称
vip_playlist_name = VIP专属歌曲

# dry-run模式（建议首次运行启用）
dry_run = false

# API请求间隔
request_delay = 0.5

[logging]
log_level = INFO
save_to_file = true
```

## 🚀 使用方法

### 基础用法

```bash
# 使用默认配置运行（二维码登录）
python -m netease_vip_manager.main
```

### Dry-Run模式（推荐首次使用）

```bash
# 仅预览操作，不实际修改
python -m netease_vip_manager.main --dry-run
```

### 指定登录方式

```bash
# 使用手机号验证码登录
python -m netease_vip_manager.main --login-method phone
```

### 自定义VIP歌单

```bash
# 指定歌单名称
python -m netease_vip_manager.main --playlist-name "我的VIP收藏"

# 使用现有歌单ID
python -m netease_vip_manager.main --playlist-id 123456789
```

### 跳过确认提示

```bash
# 直接执行，不询问确认
python -m netease_vip_manager.main --no-confirm
```

### 查看所有参数

```bash
python -m netease_vip_manager.main --help
```

## 📖 使用流程

1. **登录认证**
   - 首次运行会提示登录
   - 推荐使用二维码扫码登录（更安全）
   - 登录状态会缓存到本地，下次运行无需重复登录

2. **扫描歌曲**
   - 自动获取"我喜欢的音乐"列表
   - 分析每首歌曲的付费类型
   - 识别VIP专属歌曲

3. **预览结果**
   - 显示找到的VIP歌曲清单
   - 展示歌名、歌手、专辑、付费类型等信息

4. **确认操作**
   - 提示即将执行的操作
   - 等待用户确认（除非使用`--no-confirm`）

5. **执行操作**
   - 创建或获取VIP歌单
   - 批量添加歌曲到歌单
   - 批量取消喜欢标记
   - 显示操作结果统计

## ⚠️ 注意事项

### 安全提示

- 登录凭证保存在本地 `.cache` 目录，请勿分享给他人
- 建议首次运行使用 `--dry-run` 模式预览操作
- 取消喜欢的操作**不可批量撤销**，请谨慎操作

### VIP歌曲识别

工具会识别以下类型的歌曲：
- `fee = 1`：VIP专属歌曲
- `fee = 8`：VIP高音质（低音质免费，高音质需VIP）

### API限流

- 工具已内置请求延迟，避免触发API限流
- 如遇到频繁失败，可在配置文件中增加 `request_delay` 值

## 📁 项目结构

```
tool_by_python/
├── netease_vip_manager/
│   ├── __init__.py          # 包初始化
│   ├── main.py              # 主程序入口
│   ├── auth.py              # 登录认证模块
│   ├── music_scanner.py     # 音乐扫描模块
│   ├── playlist_manager.py  # 歌单管理模块
│   └── utils.py             # 工具函数
├── config.ini.example       # 配置文件模板
├── requirements.txt         # 依赖列表
└── README.md               # 本文件
```

## 🐛 常见问题

### Q: 登录失败怎么办？

A: 
- 检查网络连接是否正常
- 删除 `.cache/auth.json` 文件，重新登录
- 尝试其他登录方式

### Q: 找不到"我喜欢的音乐"歌单？

A: 
- 确保你的账号有"我喜欢的音乐"歌单
- 检查是否登录了正确的账号

### Q: 部分歌曲操作失败？

A: 
- 查看 `logs` 目录下的日志文件
- 失败的歌曲ID会保存到 `failed_songs.txt`
- 可能是网络问题或API限流，稍后重试

### Q: 如何撤销操作？

A: 
- 添加到歌单的操作可以手动移除歌曲
- 取消喜欢的操作需要手动重新点喜欢
- 建议使用 `--dry-run` 模式提前预览

## 📝 更新日志

### v1.0.0 (2025-11-24)

- ✨ 初始版本发布
- 🔐 支持二维码和手机号登录
- 🎵 支持VIP歌曲识别和批量操作
- 📊 美观的终端界面
- 📝 完整的日志记录

## 📄 许可证

本项目仅供学习交流使用，请勿用于商业用途。

## 🙏 致谢

- [pyncm](https://github.com/mos9527/pyncm) - 网易云音乐API库
- [rich](https://github.com/Textualize/rich) - 终端美化库
