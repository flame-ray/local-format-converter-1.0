# 本地格式转换助手 1.0

一款无需联网、无需登录、无需 AI 调用的 Windows 本地格式转换工具。视频、音频和图片均在本机通过 FFmpeg 处理，不上传任何文件。

## 支持格式

- 视频输入：MP4、MKV、MOV、AVI、WMV、FLV、WebM、M4V、MPEG、MPG、3GP、TS
- 视频输出：MP4、MKV、MOV、AVI、WebM、FLV、GIF
- 音频输入：MP3、WAV、M4A、AAC、FLAC、OGG、OPUS、WMA、AIFF、AMR
- 音频输出：MP3、WAV、M4A、AAC、FLAC、OGG、OPUS、WMA
- 图片输入/输出：JPG、PNG、WebP、BMP、TIFF、GIF、ICO

## 功能

- 批量队列与文件夹导入
- 视频转音频、视频首帧转图片
- 高清、标准、小体积三档质量预设
- 1080P、720P、480P 视频尺寸预设
- 自定义输出目录、实时进度和停止按钮

## 下载

请在本仓库的 [Releases](../../releases) 页面下载 Windows 单文件 EXE。

## 本地运行

需要 Python 3.11+、Pillow 和 FFmpeg：

```powershell
pip install pillow
python app.py
```
