# SpokenDialogueSum 导入规则

## 资源粒度

每个 `EmoDialogueSum_<split>/dialogue_<n>/dialogue_<n>_overlap.wav` 导入为一条 `audio_resources` 记录，资源类型为 `overlap_dialogue`。这是网站展示、受控播放和检索的唯一首版音频粒度。

`utt_*.wav` 与 `dialogue_*_full.wav` 不导入为独立资源：它们保留在只读数据集挂载中，既不复制，也不写入资源表。这样避免同一对话出现重复可播放条目。

## 元数据映射

- `storage_key` 保存相对 `DATASET_ROOT` 的路径，例如 `EmoDialogueSum_test/dialogue_0/dialogue_0_overlap.wav`；绝不复制原始音频或保存宿主绝对路径。
- `text` 为按 CSV 顺序拼接的 `说话人: transcript` 全文，便于后续检索。
- `metainfo.fact_summary` 和 `metainfo.emotional_summary` 取 `segmentation_overlap.csv` 首条数据的 `summary`、`emotional_summary`。
- `metainfo.segments` 保存每段的说话人、开始/结束时间、转写、情绪、音高标准差与语速。
- `metainfo.speakers` 保存 `speaker_prompt_meta.tsv` 中每位说话人的性别与年龄。

## 可扩展分片

扫描所有 `EmoDialogueSum_<split>` 目录；当前的 `test` 以及未来加入的 `dev`、`train` 使用同一规则。重复运行会按 `(dataset_name, storage_key)` 更新元数据，保持幂等。
