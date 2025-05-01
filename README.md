# 漫画翻译器

一个简单的基于LLM的漫画翻译工具，可以将漫画中的文字翻译成中文。

## 功能

- 粘贴漫画图片（Ctrl+V）
- 自动检测文字并翻译成中文
- 显示原文和翻译结果
- 实时显示LLM的流式输出
- 支持API设置（端点、模型名称、API密钥）

## 安装

1. 克隆仓库
2. 安装依赖：

```bash
pip install -r requirements.txt
```

或者使用uv：

```bash
uv pip install -r requirements.txt
```

## 使用方法

1. 运行程序：

```bash
python comic_translator.py
```

2. 设置OpenAI API密钥
3. 使用Ctrl+V粘贴漫画图片
4. 点击"Translate"按钮开始翻译

## 要求

- Python 3.8+
- OpenAI API密钥（支持GPT-4 Vision）
- Pillow库用于图像处理 