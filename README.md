# nl2stata — 自然语言控制 Stata 的 AI 插件

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

nl2stata 是一个 Stata 插件，允许你用自然语言指令操控 Stata。
它借助 DeepSeek 大模型将你的日常语言（中/英文）翻译成准确的 Stata 命令，并直接在 Stata 中执行。

## ✨ 功能亮点

- 命令行 + 图形对话框双模式，操作直观
- 支持多步骤复杂指令（循环、条件、回归、绘图等）
- 自动清洗模型输出，确保命令可直接执行
- 采用 `#delimit ;` 机制安全运行多行命令，告别换行符错误
- 记住模型选择，下次调用更快捷
- 完全本地化 Python 翻译核心，无需 Stata Python 集成

## 📦 安装

1. 下载本仓库，将以下三个文件放置到 Stata 的 personal 目录（可通过 `sysdir` 查看）下的 `n/` 文件夹中：
nl2stata.ado
nl2stata.py
nl2stata_dlg.ado


默认路径为：
- Windows: `C:\Users\用户名\ado\personal\n\`
- Mac/Linux: `~/ado/personal/n/`

2. **安装 Python 依赖**（需要 Python 3.8+）：

```bash
pip install openai

🚀 快速上手
命令行模式
在 Stata 命令窗口输入：

nl2stata "使用 auto 数据，做 price 的描述统计，并用 mpg 预测 price"
程序会显示翻译后的命令并询问是否执行。若要直接执行，可加 EXECute 选项：

nl2stata "summarize price; regress price mpg", execute
对话框模式
直接输入 db nl2stata 启动图形界面，在输入框中写需求点击提交即可。

指定模型或 API Key
nl2stata "ttest price==5000", model(deepseek-chat) apikey(sk-xxxx)
🔧 配置
默认模型：deepseek-v4-pro，可通过 model() 选项或 char _dta[_nl2stata_model] 修改。

API Key：优先读取 DEEPSEEK_API_KEY 环境变量；命令行中通过 apikey() 传入的优先级更高。

模型记忆：最后使用的模型会被保存到当前数据集的特性中，下次打开同一数据会自动沿用。

📚 示例
自然语言	翻译结果（示例）
加载 auto 数据，计算 price 均值和标准差	sysuse auto, clear; egen mean_price = mean(price); egen sd_price = sd(price);
把 price > 10000 的车标记为 expensive，然后只保留这些车	sysuse auto, clear; gen expensive = (price > 10000); keep if expensive;
用 mpg 和 weight 做 price 的回归，并画残差图	sysuse auto, clear; regress price mpg weight; predict resid, residuals; scatter resid mpg;
注意：所有命令以 ; 结尾，多行结构（如循环）也会自动以 ; 结束。

⚙️ 工作原理
用户通过命令行或对话框输入自然语言指令

Stata 调用内部子程序将指令写入临时文件

使用 shell python 运行 nl2stata.py，传入输入文件、输出文件、模型和 API Key

Python 脚本向 DeepSeek API 发送精心设计的 system prompt 和用户指令，获取翻译结果

翻译结果经过去污染、补全分号等后处理，返回 Stata

Stata 端采用 #delimit ; 模式将多命令写入临时 do 文件并执行，确保所有命令被正确解析

🛠️ 依赖
Stata 16.0 或更高版本

Python 3.8+ 及 openai 包

DeepSeek API Key（需在 DeepSeek 平台 申请）

❗ 注意事项
Python 脚本必须在系统环境变量中可直接调用（即 python --version 能在 Stata shell 中运行）

翻译结果有时可能不完美，建议先在对话框模式下预览命令再执行（去掉 execute 选项是安全的）

避免在指令中使用 clear 除非你真的想清空内存；插件已要求模型谨慎使用
