# 上传到自己的阿里云 OSS

本地图片可以直接随文章保存。需要 CDN 链接时，在文章项目中准备一个未纳入 Git 的配置文件，例如 `.env`。使用自己的 Bucket、地域 Endpoint、可公开读图片的域名，以及能写入目标前缀的凭据。脚本依赖 Node.js 标准库。

```dotenv
OSS_AK=your-access-key-id
OSS_SK=your-access-key-secret
OSS_ENDPOINT=https://oss-cn-hangzhou.aliyuncs.com
OSS_BUCKET=your-bucket
OSS_HOST=https://cdn.example.com
```

下面的命令从 Skill 目录执行。第一条只验证配置并预览目标地址，第二条才会上传。

```bash
node scripts/upload-oss.js --env /path/to/.env --image /path/to/article.png --name article --dry-run
node scripts/upload-oss.js --env /path/to/.env --image /path/to/article.png --name article --json
```

默认对象前缀是 `articles`，可用 `--prefix` 修改。取实际上传返回的 `cdnUrl`，下载后比对原文件，再回填 Markdown。循环 GIF 可运行 `python3 scripts/verify_gif.py /path/to/article.gif --cdn-url URL` 同时校验类型与字节。其它图床可沿用自己的上传流程。
