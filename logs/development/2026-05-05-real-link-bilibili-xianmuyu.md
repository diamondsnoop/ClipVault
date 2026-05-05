# 2026-05-05: Real-Link Validation — Bilibili 闲木鱼《大明王朝》

## Target

Validate the current single-video transcript pipeline with the updated Bilibili
manual sample. This validation intentionally processes one video only, not the
whole series.

## Video

- Platform: Bilibili
- Creator: 一条闲木鱼
- Series: 《大明王朝》
- URL: `https://www.bilibili.com/video/BV16G411973A`
- Title: `《大明王朝》你真看懂了吗？国产第一神剧深度拆解！第一回`
- Video id: `BV16G411973A`
- Duration: `1991.978` seconds
- Upload date: `20230903`
- Validation library root:
  `.tmp/manual-validation/2026-05-05-bilibili-xianmuyu`

## Commands

Check subtitle availability:

```powershell
.\.venv\Scripts\python.exe -m yt_dlp --list-subs "https://www.bilibili.com/video/BV16G411973A/"
```

Result:

- Only `danmaku xml` was available without login.
- `yt-dlp` reported that Bilibili subtitles require login.

Run ClipVault:

```powershell
.\clipvault.ps1 video "https://www.bilibili.com/video/BV16G411973A" `
  --library ".tmp\manual-validation\2026-05-05-bilibili-xianmuyu" `
  --series "大明王朝" `
  --model small `
  --device auto
```

## Result

The platform subtitle path correctly reported no available subtitles, then
ClipVault fell back to local ASR and completed successfully.

```json
{
  "status": "ok",
  "source": "asr:faster-whisper",
  "platform": "bilibili",
  "series": "大明王朝",
  "series_source": "manual",
  "segments": 1290
}
```

Manifest fields:

- `subtitle_source`: `asr:faster-whisper`
- `asr_model`: `small`
- `asr_device`: `cuda`
- `output_files`: `transcript.srt`, `transcript.txt`, `transcript.md`

Output file sizes:

- `transcript.srt`: `82866` bytes
- `transcript.txt`: `43985` bytes
- `transcript.md`: `46820` bytes

## Observations

- First metadata attempt timed out once; retry succeeded.
- `tiny` model was not usable from local cache. This is expected under the
  current local-only ASR rule because ClipVault does not download models
  automatically.
- `small` model was available locally and completed with CUDA.
- The generated outputs were stored under:
  `.tmp/manual-validation/2026-05-05-bilibili-xianmuyu/bilibili/一条闲木鱼/大明王朝/...`
- Generated transcripts remain under `.tmp/` and are not committed.

## Conclusion

The single-video Bilibili chain is stable for the tested scenario:

```text
metadata -> platform detection -> subtitle lookup -> ASR fallback -> srt/txt/md export -> manifest -> creator/series index
```

This validates the project can acquire a transcript for one real Bilibili video
from the updated 闲木鱼《大明王朝》 sample without requiring series-wide ingestion.
