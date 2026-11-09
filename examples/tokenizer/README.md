# Case · 从占位符到四张配图

同一篇分词器短文里，有的段落需要停下来查 ID，有的需要看数据如何移动。对照[配图前](before.md)和[配图后](after.md)，两份文件只有四行图片引用不同。

| 占位符 | 素材怎么选 | 打开成品 |
| --- | --- | --- |
| 一句话究竟多少 Token | 左边截取 DeepSeek 官方文档，右边独立标注本地测量条件，方便核对空格和 ID | [说明与测量 PNG](images/usage.png) |
| 文字如何进出模型 | 用手绘底图保持整套机制可见，沿箭头演示「选一个 → 接回上下文 → 再预测」 | [15 秒机制 GIF](images/generation.gif) |
| 整词、字节、子词有何不同 | 三栏都用「人工智能」，静态比较同一输入 | [三栏手绘 PNG](images/compare.png) |
| 第几个字节能显示「𠮷」 | 实测分词结果驱动演示页面，依次点击，捕获五个稳定状态；帧间停留便于阅读 | [8 秒 Case GIF](images/rare-character.gif) |

## 离线复现回填

在仓库根目录运行。只使用 Python 3 标准库和随仓库附带的成品。

```bash
cd examples/tokenizer
python3 ../../skills/wanger-hand-drawn-image/scripts/render_article.py before.md assets.json > replay.md
diff -u after.md replay.md
```

`diff` 无输出表示与仓库中的成稿逐字一致。两个 Markdown 文件在同一目录，里面的相对图片链接都能直接打开。

## 打开交互演示

在本 Case 目录执行 `python3 -m http.server 8000 --bind 127.0.0.1`。打开 [Token 编号对照](http://127.0.0.1:8000/) 或 [逐步解码](http://127.0.0.1:8000/#decode)，逐次点击「读入下一个」。前三步显示等待，第四步显示「𠮷」。演示数据取自同目录的 `results.json`。结束后用 Ctrl+C 关闭本地服务。

## 复核数据和动画

[测量结果](results.json)来自官方模型仓库固定版本的 `tokenizer.json`。编码只包含这句话，不添加聊天模板或特殊 Token。示例四的完整序列由分词器解码回原字，中间的「等待后续字节」由流式 UTF-8 解码呈现。[官方 Token 用量说明](https://api-docs.deepseek.com/zh-cn/quick_start/token_usage/) · [固定版本分词器](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash/blob/314113f8a7dadb388215396ba5fbee2c610a04d6/tokenizer.json)

如需重新测量，在本 Case 目录运行以下命令。测量脚本先核对下载内容的 Git blob ID，再写出 `results.json`。

```bash
curl -fL 'https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash/resolve/314113f8a7dadb388215396ba5fbee2c610a04d6/tokenizer.json' -o tokenizer.json
uv run --with tokenizers measure.py tokenizer.json
```

机制图的[手绘底图](scene/master.png)和[动画配置](scene/scene.json)也随仓库提供。macOS 安装 Swift、FFmpeg（含 ffprobe）后，可在本 Case 目录重新渲染到新的目录。

```bash
python3 ../../skills/wanger-hand-drawn-image/scripts/render_gif.py scene/scene.json --output render-output
```

脚本导出 GIF、静音 MP4、抽帧联系表和尺寸记录。检查两张现成的 GIF 可运行 `python3 ../../skills/wanger-hand-drawn-image/scripts/verify_gif.py images/generation.gif`，依赖 Pillow。
