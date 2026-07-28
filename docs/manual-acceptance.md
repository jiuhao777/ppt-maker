# PPT Maker 首版人工验收

## 1. 启动

```bat
conda activate AI
streamlit run src/pptmaker/ui/app.py
```

浏览器应只打开 `http://127.0.0.1:8501`。API Key 只在当前标签页有效，刷新后应清空。

## 2. 完整用户流程

1. 新建项目，填写主题或上传材料。
2. 完成必要追问，批准概略大纲。
3. 按项目联网策略完成博查核验；检查来源可打开，排除的来源不再出现。
4. 生成详细施工大纲，检查 Deck Bible、结论式标题、每页内容、布局、备注与衔接。
5. 为图片页选择素材，核对作者、原链接、许可证；无合格素材时改为无图版式。
6. 批准详细大纲并生成 PPTX。
7. 刷新页面，确认仍可下载同一版本。

## 3. PowerPoint 验收

先关闭所有 PowerPoint 窗口，再运行：

```bat
conda activate AI
set PYTHONIOENCODING=utf-8
python -m pytest tests/powerpoint/test_worker_integration.py -v
```

必须 4 项全部通过：逐页渲染、超时清理、预启动取消和心跳。随后用 Windows 11 PowerPoint 打开生成文件，确认：

- 文件可正常打开，页数和顺序正确；
- 无严重越界、遮挡、裁切、占位框或低清水印图；
- 文字、表格和图表数据可编辑；
- 图片不变形，来源、作者和许可可追溯；
- 演讲者备注存在，简单淡入动画可用；
- 全局色彩、字体、页脚统一，复杂页与轻量页有节奏变化。

## 4. 在线能力验收

- 在侧边栏输入临时模型 Key，连接测试成功并显示能力探测；
- 输入博查 Key，搜索连接测试成功；
- 使用具有时效性的主题，确认 `AUTO` 会联网，`NEVER` 不联网，`ALWAYS` 无 Key 时阻止生成；
- 检查日志、SQLite、导出 JSON、PPTX 和错误提示中不存在 API Key。

刷新 DeepSeek 的 M0 证据时使用隐藏输入脚本，Key 不会写入命令历史：

```bat
conda activate AI
python scripts\run_deepseek_probe_secure.py
python scripts\check_m0_gate.py
```

## 5. 人工质量评分

对一份 10–15 页真实任务按 1–5 分评分：叙事连续性、结论清晰度、视觉层级、图片相关性、编辑便利性、首稿可用性。每项应不低于 4 分；任何严重事实错误、无来源公共数据、严重遮挡或文件无法打开均直接不通过。
