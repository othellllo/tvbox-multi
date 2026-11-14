# TVBox 多仓源（自建 + 自检）

> 2026-11-14 构建 · 6 个仓库可用、全部 jar 校验通过 · 单仓 127 站 / 66 解析
> 仓库地址：<https://github.com/othellllo/tvbox-multi>

## 一、现成地址（直接粘进 App）

在 TVBox / 影视仓 / OK影视 的「设置 → 配置地址」里填：

| 用哪个 | 地址 |
| --- | --- |
| **多仓（推荐）** | `https://cdn.jsdelivr.net/gh/othellllo/tvbox-multi@main/tvbox-multi.json` |
| 单仓聚合 | `https://cdn.jsdelivr.net/gh/othellllo/tvbox-multi@main/tvbox-single.json` |
| 精简版（免 jar） | `https://cdn.jsdelivr.net/gh/othellllo/tvbox-multi@main/tvbox-lite.json` |

jsDelivr 走不通时换备用（内容一样）：

- `https://fastly.jsdelivr.net/gh/othellllo/tvbox-multi@main/tvbox-multi.json`
- `https://gh-proxy.com/https://raw.githubusercontent.com/othellllo/tvbox-multi/main/tvbox-multi.json`

> 实测：这套手机网络上 `raw.githubusercontent.com` 不通，jsDelivr / gh-proxy 两条都通，所以优先用 jsDelivr。

## 二、三个文件的分工

| 文件 | 用途 |
| --- | --- |
| `tvbox-multi.json` | **多仓索引**。App 里可切 6 个仓库，哪个仓库当天挂了就切另一个 |
| `tvbox-single.json` | **单仓聚合**。127 站一步到位：短剧 4 + 动漫 4 + 26 个免 jar 的 api 站，66 个解析 |
| `tvbox-lite.json` | **精简版**。27 个纯 api 直连站，不用 jar，最不容易坏 |

## 三、你要的分类在哪

| 分类 | 覆盖情况（实测站点数） |
| --- | --- |
| 电影 / 电视剧 / 综艺 | 6 个仓库全覆盖；单仓里另有 26 个 api 直连站（电影天堂、耐看、南柯、555 等） |
| 动漫 | 高天流云 14、老刘备 5、王二小 4、小盒子 3、挺好 3、小马 2 |
| 短剧 | 王二小 4（🍉好看/小猫/星星/小薇）、老刘备 4（🎧刷刷/BiL/葡萄/嗷嗷）、小盒子 1（🎭csp_Duanju） |
| AI 短剧 | 短剧站内有「AI 短剧」分类，选上面的短剧站就能看到，没有单独的仓库 |
| 红果短剧 | **公开 TVBox 源里没有官方红果接口**（扫了 4 个大仓，`红果` 关键词 0 命中）。原生体验用官方「红果短剧」App 或开源项目 [菲凡聚合](https://juejin.cn/post/7707184266061316130)；短剧站里也能搜到被搬运的红果/番茄系内容 |

## 四、长期怎么保证不失效

1. 隔一两个月跑一次：`python3 build.py`
   重新拉全部源 → 校验 jar 的 md5 → 把死掉的源从多仓里去掉 → 重新生成三个 json。
2. 某个源彻底死了：打开 `config/sources.json`，把新地址填进它的 `urls` 数组（依次回退），或 `"enabled": false` 停用。
3. 想加新源：照抄一段，`role` 填 `supplement`（默认）就进多仓，填 `base` 会当单仓主干。
4. 改完推上来，jsDelivr 会自动跟着更新（同分支，几秒生效）。

> 多仓的意义就是「不把鸡蛋放一个篮子」：哪个仓库当天挂了，在 App 里切另一个仓库就行。

### 想每天自动体检

仓库里已有 `.github/workflows/build.yml`，但上传时 token 没有 `workflow` 权限，所以没传上去。
在网页上手动新建这个文件（Actions → New workflow → 粘贴仓库里的内容），或者给我一个勾了 `workflow` 的 token，我帮你推。

## 五、当前源状态（2026-11-14 实测）

| 源 | 站点 | jar | 备注 |
| --- | --- | --- | --- |
| 🎬 王二小 | 100 | ✅ md5 通过 | 短剧/动漫齐，单仓主干 |
| 📺 老刘备 | 234 | ✅ | api 站最多，解析 27 个 |
| 🌸 高天流云 | 298 | ✅ | 动漫最多；jsDelivr 上 jar 403，因此配置走 gh-proxy |
| 🎬 小马 | 62 | ✅ | 40 个解析、10 条直播 |
| 🎭 小盒子 | 54 | ✅ | 含短剧 |
| 🦉 挺好分享 | 46 | ✅ | |
| 🚀 挺好 32 仓 | 32 子仓 | — | 现成多仓，可单独导入 `http://ztha.top/TVBox/GYCK.json` |

已停用（域名/反爬变动）：肥猫（404）、饭太硬（挑战页）、讴歌（连接重置）、拾光（返回非 JSON）。

## 六、免责声明

所有接口均来自互联网公开分享，本项目只做聚合、体检和索引，不存储、不提供任何视频内容；版权归各原始权利人所有。仅供个人学习与技术研究，请勿商用或传播。接口随时可能被上游改动，可用性以 `build.py` 每次体检结果为准。
