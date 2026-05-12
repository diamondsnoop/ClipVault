# 认证访问程序日志

当平台需要登录态访问时，ClipVault 可以使用本地 cookies 文件。日志必须明确说明是否启用了认证访问，但绝不能暴露凭据内容。

当前运行时日志示例：

- `[认证] 已从 ClipVault 凭据文件生成临时 cookies：<path>`
  表示从 ClipVault 的凭据文件读取了已保存登录态，并为当前进程生成了临时 Netscape cookies 文件。
- `[认证] 已启用 cookies 文件：<path>`
  表示某个 cookies 文件路径已被接受，并传给 `yt-dlp` 使用。
- `[认证] HTTP 请求已加载 cookies：<path>`
  表示某个 cookies 文件已用于直接字幕下载等 HTTP 请求。
- `[错误][流程] 未找到 cookies 文件：<path>`
  表示配置的 cookies 路径不存在，或者不是一个有效文件。
- `[错误][流程] 加载 cookies 文件失败：<path>（<reason>）`
  表示文件存在，但不能按 Netscape cookies 文件解析。

日志规则：

- 绝不能打印 Cookie 值。
- 绝不能把 cookies 文件内容写进 bug 报告。
- 可以打印本地文件路径，因为这有助于用户排查过期、误放或路径写错的凭据文件。
- ClipVault 生成的临时 cookies 缓存文件必须在 CLI 结束或 Python 进程退出时清理。
- 如果已经启用 cookies，但平台仍然拒绝访问，下一步检查应是：
  - 文件是否为 Netscape 格式
  - Cookie 是否为最新导出
  - 当前账号能否在浏览器里正常打开该视频
  - `yt-dlp` 是否需要更新
