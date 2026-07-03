# Job Seeker - 本地浏览器抓取工具

## 前置条件

1. Python 3.10+（需 `pip`）
2. Google Chrome 浏览器
3. BOSS直聘账号（已登录）

## 安装

```bash
pip install playwright httpx
playwright install chromium
```

## 使用

### 1. 启动 Chrome 远程调试模式

**Linux (WSL):**
```bash
google-chrome --remote-debugging-port=9222
```
或
```bash
chrome --remote-debugging-port=9222
```

**Windows:**
```cmd
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222
```

**macOS:**
```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222
```

### 2. 在浏览器中登录 BOSS直聘

打开 <https://www.zhipin.com>，扫码登录。

### 3. 运行抓取脚本

```bash
cd job_seeker
python3 local_crawler.py "Python后端" 北京
```

脚本会自动：
- 连上你的 Chrome
- 打开 BOSS直聘搜索页
- 提取岗位列表
- 提交到系统（`POST /admin/jobs/crawl-submit`）

### 4. 在管理端查看

打开 <http://localhost:51668/jobs> → 点击「刷新」即可看到抓取的岗位。

## 注意事项

- Chrome 远程调试端口 `9222` 不能被其他程序占用
- 抓取过程中不要关闭 Chrome
- 如果未登录，脚本会提示你在浏览器中扫码
