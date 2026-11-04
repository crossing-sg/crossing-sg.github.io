# 完整 OSM + 最新共享 main 集成

本次集成以共享仓库 `crossing-sg/crossing-sg.github.io` 的 `785b7533` 为基础。
原始本地工作区及其中未提交文件保留不动；集成在同一克隆仓库的独立 Git worktree
`local-outputs/shared-main-osm-integration` 中完成。测试通过后建立本地分支
`codex/integrate-complete-osm-satellite`。

## 上传状态

GitHub 连接和本机 Git Credential Manager 均使用 `swiftstrange`。
仓库 API 对本机凭据明确返回 `pull: true, push: false`，因此按用户要求停止上传：
没有推送分支，没有创建 PR，没有修改共享 `main`，没有部署 Apps Script。
需要仓库管理员为该账号授予 Write 权限后才能继续上传及创建目标为 `main` 的 PR。
PR 标题和正文已准备在 [PR_BODY.md](PR_BODY.md)。

## 保留的组员更新

- Proposal 继续使用 `mapbox://styles/mapbox/satellite-streets-v12`。
- Explore 保留最新 `main` 的细白色 `proposal-crossings`、半透明道路底色和选中线高亮外框，
  保留其点击事件及主题切换逻辑，并接入新的 OSM 规范几何查找。
- Home、Storytelling、规划区图表和相关脚本、Crossing Gap、Walking Detour、
  路线数据和原 `style.css` 均保持最新 `main` 的内容。
- 37 项自动化测试及隔离浏览器检查覆盖 LTA/OSM 匹配、提交、存储、旧记录兼容、
  Explore 中的实际绘制及低于发布阈值后的白线清除。

道路数据仍是同一验证过的完整发布版本：602,199 个分段，包含所有 55,115 个原始 LTA
分段、14,006 个前期补充分段及 533,078 个完整 OSM 补充分段。32 个 highway 类别均保留。
ID、几何和校验和没有因本次前端整合而改变。数据和可复现处理说明见
[OSM 处理记录](../osm-complete/README.md)。

## Proposal 卫星影像

根据用户实际下载的 `satellite_color_preview.html` 核对转换公式：
`n=brightness/100; min=Math.max(0,n); max=Math.min(1,1+n)`。

| Mapbox raster paint | 值 |
| --- | ---: |
| raster-saturation | -0.25 |
| raster-hue-rotate | 40 |
| raster-contrast | -0.30 |
| raster-brightness-min | 0 |
| raster-brightness-max | 0.5 |

`website/js/proposal-basemap.js` 只在 Proposal 的 `style.load` 时调整 raster 图层。
不对 canvas 设置 CSS filter，不修改道路/文字 vector 图层，不在 Home/Explore 加载该脚本，
不引入预览滑块。真实 Mapbox 检查比对了 85 个非栅格图层的原始 paint/layout，均一致，
并确认实际渲染出 139 个标签，且 OSM 道路匹配正常。
属性定义参考 [Mapbox raster style specification](https://docs.mapbox.com/style-spec/reference/layers/#raster)。

移动测试发现共享版固定宽度侧栏在 390 px 下遮挡地图，因此将已经完成的窄屏适配放在
单独的 `website/css/proposal-responsive.css` 中，只由 Proposal 和 Explore 加载。
原桌面样式及 Home/Story 样式不变。

## API 和单独部署步骤

**仍需单独部署 Google Apps Script。** 推送静态网站代码不会更新 Google 脚本。

最新共享版 `SITE.appsScriptUrl` 原值保留，Home/Story 的已有 GET 读取继续使用它。
新的 Proposal/Explore 提议功能使用独立的 `SITE.proposalApiUrl`，当前为空，防止把新 OSM
ID 发给不支持该发布版本的旧 API。该设置需要在兼容后端验证和部署后填写；网站与后端
应协调上线。本地预览服务器会同时将两个 URL 仅在内存响应中改为本地测试 API，
不会联系正式数据库。

部署兼容后端时复制 `apps-script/Code.gs`、`RegistryConfig.gs`、`RoadGeometry.gs`，
在隔离 Sheet 上验证 `setup()` 的追加式表头迁移和旧记录审核，设置 Script Property
`PROPOSAL_DATA_BASE_URL` 为已发布的 HTTPS `data/osm-complete/proposal-roads` 目录，
核对固定的 manifest SHA-256，再验证 UrlFetch、gzip 解压、权限/CORS 和 Sheets 配额。
`.gz` 静态资产作为 gzip 原始字节提供，不设置 `Content-Encoding: gzip`，由客户端显式解压。
不要修改原记录或重用保留 ID。通过后再将新部署 URL 填入 `proposalApiUrl`。

## 测试和复查

```powershell
npm test
npm run test:osm
npm run test:shared
npm run test:browser:osm
npm run test:basemap:real
python website-plan/osm-complete/verify.py --base-ref 785b7533
python -m unittest discover -s website-plan/osm-complete -p test_processing.py
git diff --check
```

Python 需安装 `website-plan/osm-complete/requirements.txt` 的依赖；本机复用原有地理处理 venv。
Playwright 使用已安装 Chrome，或按原处理文档准备浏览器和测试 vendor 文件。
隔离测试会阻止全部外部请求；真实底图测试只读 Mapbox，阻止 Google 后台。

结果文件：

- [完整数据和 main 保护验证](../osm-complete/validation.json)
- [桌面/移动浏览器结果](../osm-complete/browser-results.json)
- [真实卫星底图结果](real-basemap-results.json)

截图在忽略的 `local-outputs/shared-integration/` 及 `local-outputs/osm-complete/browser/` 下。
保守空间去重、复杂多线位置歧义、一个无效 OSM 面关系及真实 Google 部署验证的限制，
仍按原 OSM 处理报告记录；本次没有重新计算既有分析。
