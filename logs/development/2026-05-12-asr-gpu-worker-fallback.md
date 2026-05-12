# 2026-05-12 ASR GPU Worker Fallback

## Target

定位并修复 Windows GPU ASR 在真实 Bilibili 样本上以 `0xC0000409` 崩溃的问题，确保：

- `device=auto` 不再因为 GPU 子进程硬崩而整条视频处理失败
- GPU 可用时仍优先走 CUDA
- 即使 GPU 路径出错，也能可靠回退到 CPU

## Steps

1. 读取 Web 任务日志，确认两条真实失败样本都在 `平台字幕不可用 -> 下载音频成功 -> ASR 开始后进程退出码 3221226505` 这一阶段失败。
2. 用最小复现实验确认：
   - GPU 模型初始化成功
   - GPU 转写本身可完成
   - 崩溃发生在 `WhisperModel` / 相关迭代器释放阶段，而不是转写中途
3. 新增独立 GPU worker：
   - 父进程通过 `python -m clipvault.asr_worker` 调度 CUDA 转写
   - worker 写出 JSON 结果后用 `os._exit(0)` 直接退出，绕开析构崩溃
4. 在父进程里实现 `auto -> cpu` 的进程级回退：
   - CUDA worker 非 0 退出时，不再只依赖 Python `RuntimeError`
   - 改为记录 worker 失败摘要并重试 CPU
5. 修正 `process_video()` 里的 ASR 设备记录，确保 fallback 到 CPU 时，结果和 manifest 写入真实设备值。

## Changes

- 修改 [clipvault/asr.py](/C:/Users/24967/.codex/worktrees/0f02/ClipVault/clipvault/asr.py)
  - 增加 `TranscriptionResult`
  - 增加 GPU worker 调度与结果加载
  - 增加 worker 失败摘要
  - `device=auto` 时改为父进程级 CPU fallback
- 新增 [clipvault/asr_worker.py](/C:/Users/24967/.codex/worktrees/0f02/ClipVault/clipvault/asr_worker.py)
  - 独立执行 GPU 转写并写出结果 JSON
  - 成功/失败都通过 `os._exit(...)` 绕开析构阶段崩溃
- 修改 [clipvault/cli.py](/C:/Users/24967/.codex/worktrees/0f02/ClipVault/clipvault/cli.py)
  - 读取 `TranscriptionResult`
  - 将实际 ASR 设备写入返回结果和 manifest
- 新增 [tests/test_asr.py](/C:/Users/24967/.codex/worktrees/0f02/ClipVault/tests/test_asr.py)
  - 覆盖 worker 成功结果读取
  - 覆盖 `auto` 下的 CPU fallback
  - 覆盖显式 `cuda` 下的错误传播
- 修改 [tests/test_cli.py](/C:/Users/24967/.codex/worktrees/0f02/ClipVault/tests/test_cli.py)
  - 增加实际 ASR 设备写入结果与 manifest 的测试

## Verification

- `E:\myproject\ClipVault\.venv\Scripts\python.exe -m pytest tests/test_asr.py -q -p no:cacheprovider`
  - 结果：`3 passed`
- `E:\myproject\ClipVault\.venv\Scripts\python.exe -m pytest tests/test_cli.py -q -k actual_asr_device -p no:cacheprovider`
  - 结果：`1 passed, 36 deselected`
- `E:\myproject\ClipVault\.venv\Scripts\python.exe -m compileall clipvault`
  - 结果：通过
- 真实 GPU 直转写验证：
  - TED 音频：`device=auto` 返回 `device=cuda`，`segments=420`
  - 闲木鱼音频：`device=auto` 返回 `device=cuda`，`segments=1314`
- 完整 `process_video()` 验证：
  - `https://www.bilibili.com/video/BV1xK411x78c/`
  - 结果：成功导出 `transcript.srt` / `transcript.txt` / `transcript.md`
  - `result["asr_device"] == "cuda"`

## Follow-ups

- 当前环境的 `.venv` 里没有安装 OpenCC 运行时，因此仍会出现“已跳过中文转简”的警告；这与 GPU 崩溃无关，但会影响最终中文文本是否统一转简。
- `pytest` 仍不适合在当前机器上直接跑那些依赖 `tmp_path`/`tempfile` 的整文件测试；这属于本机 ACL 环境问题，和本次 ASR 修复本身无关。
