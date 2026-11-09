# 动画配置

坐标为基底图片像素，原点左上。`base_image` 相对 scene.json 解析，脚本自动使用真实图片尺寸。渲染需 macOS 的 Swift/AppKit 和 PATH 上的 ffmpeg、ffprobe。

```json
{
  "base_image": "master.png",
  "fps": 15,
  "duration": 12,
  "captions": [
    {"start": 0, "end": 6, "text": "新任务经过过滤和分派"},
    {"start": 6, "end": 12, "text": "后续事件沿已建立的路径直达"}
  ],
  "caption_position": [40, 1434],
  "caption_size": 29,
  "indicator_position": [440, 1500],
  "overlays": [
    {"kind": "bead", "start": 0, "end": 2, "color": "#0957eb",
     "points": [[100, 200], [100, 400], [250, 400]], "radius": 11},
    {"kind": "focus", "start": 2, "end": 5, "color": "#0957eb",
     "rect": [250, 400, 300, 120]},
    {"kind": "progress", "start": 0, "end": 12, "color": "#57c763",
     "rect": [300, 940, 150, 16],
     "keyframes": [[0, 0], [4, 0], [7, 0.7], [9, 1], [12, 1]]}
  ]
}
```

区间为 `[start,end)`，单位秒。`duration*fps` 必须为整数。分辨率来自基底图；MP4会补齐奇数尺寸的最后一行/列。

`captions` 按时间排序且不重叠。分别省略 `caption_position`、`indicator_position` 可关闭底部文字、阶段点。文字须在真实留白内，脚本拒绝超出画面的文字，不自动缩小中文。

| kind | 必要配置 | 行为 |
| --- | --- | --- |
| bead | `points`（至少两个点） | 按折线长度移动；`curve:"cubic"` 时恰好四点，为起点、两个控制点、终点 |
| focus | `rect:[x,y,w,h]` | 矩形节点轮廓轻微呼吸高亮 |
| ellipse | `rect` | 椭圆轮廓轻微呼吸高亮 |
| progress | `rect`,`keyframes:[[time,value],…]` | 可见期间重画轨道，再按关键帧线性插值填充；value 为0到1 |

通用字段：`start`、`end`、`color`（六位十六进制色）。bead可选 `radius`（默认11）、`easing`（`smooth`默认、`linear`匀速）；focus/ellipse可选 `line_width`（默认6）。progress可选 `track_color`（默认浅蓝）。关键帧时间递增，前后时刻保持首尾值。暂停可重复value；返工可显式下降，不能意外倒放。

列表按顺序绘制：先进度轨道，再高亮/移动点。坐标需根据实际主图重新标定。配置不包含文章正文、密钥、浏览器状态或生成提示词。
