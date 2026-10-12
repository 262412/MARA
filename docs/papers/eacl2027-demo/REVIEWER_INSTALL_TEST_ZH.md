# v0.0.40 评审下载与安装实测

测试日期：2026-09-23（北京时间）。测试入口：https://github.com/262412/MARA/releases/tag/v0.0.40 。

## 当前结论

**NO-GO：当前 Windows 环境按公开 README 安装未通过，尚未达到“下载后可启动并完成文档问答”的验收条件。** 这不表示所有操作系统均不可运行，也不等同于 EACL 已判定不合规；它表示本次不能给出安装及问答链路通过的实测结论。

测试使用公开下载的 v0.0.40 文件，没有使用开发分支替换代码。机器为 Windows 11 AMD64，Python 3.10.19，uv 0.11.19。虚拟环境、缓存、下载和运行数据均位于独立的 D:\MARA-reviewer-test\20260922T161319Z，未同步主仓库环境，未使用原有数据库、索引或 API 密钥。

## 链路结果

| 节点 | 实测结果 | 含义 |
| --- | --- | --- |
| 公开 release 元数据 | 成功取得 GitHub API 元数据 | 发布记录和附件确实存在 |
| Source code ZIP | HTTP 200，5,746,374 字节，CRC 通过 | 完整源码能够下载；本次约耗时 168 秒 |
| slide-app.zip | 初次超时，经 GitHub 官方 asset API 续传成功；877,687 字节，CRC 和官方 SHA-256 一致 | 附件可取得，下载速度问题单独记录为本地网络现象 |
| README Option 1：PyPI | 实际 pip install 返回 exit 1，找不到 mara-research-cli | 正式包安装入口失败 |
| README：TestPyPI fallback | 实际 pip install 返回 exit 1，找不到 mara-research-cli | 文档中的备用入口也失败 |
| README Option 2：源码安装 | uv sync --extra mara 返回 exit 1 | llama-cpp-python 0.2.7 本地构建因缺少编译器失败 |
| 启动、索引和问答 | 未执行成功 | 被安装阶段阻塞，不能记录为通过，也不能推断问答质量 |
| Computer use | Chrome 报 nodeRepl.fetch request failed；内置浏览器超时 | 未声称已通过浏览器操作完成下载或 UI 验证；实际下载与安装通过 HTTP/命令行执行 |

## 已确认的阻塞

### 1. 公开索引不存在指定包

在新的 Python 3.10 虚拟环境里执行了 README 中的包名和索引组合。PyPI 和 TestPyPI 安装均失败；两个对应的公开 JSON 元数据端点也均返回 HTTP 404。这不是用已有 MARA 环境进行的导入检查。

~~~text
ERROR: Could not find a version that satisfies the requirement mara-research-cli (from versions: none)
ERROR: No matching distribution found for mara-research-cli
~~~

### 2. 源码默认安装要求未披露的本地编译环境

解压完整源码后，在独立环境运行公开指令 uv sync --extra mara。解析了 376 个包，四个本地工作区包构建完成，但依赖安装整体失败。日志中的依赖链为：

~~~text
mara-app -> kotaemon[all] -> llama-cpp-python==0.2.7
~~~

实际错误：

~~~text
Running 'nmake' '-?' failed with: no such file or directory
CMAKE_C_COMPILER not set, after EnableLanguage
CMAKE_CXX_COMPILER not set, after EnableLanguage
~~~

此机没有在 PATH 上找到 cl、nmake、clang、gcc、ninja 或 Docker，也没有发现 Visual Studio Installer 的 vswhere。公开 README 未列出这项 Windows 编译工具前置条件。该失败说明安装说明和默认依赖组合对本测试环境不完整，不证明安装了适配编译工具的机器也必然失败。

本次未通过删除依赖、修改源码或借用现有开发环境来把失败改记为成功。原下载 ZIP 中 1,133 个文件均逐一对照，原始文件字节未变；uv.lock 的 SHA-256 在安装前后相同。

## 发布包的补充检查

slide-app.zip 内含 53 个文件，VERSION 为 v0.0.40，包含 app.py、flowsettings.py、环境示例、启动脚本及资源。它不含完整 kotaemon 核心源码，也没有根 pyproject.toml；其 Windows 启动脚本会从相同 Git tag 联网安装库。因此不能仅凭这个 ZIP 很小或文件名像应用包，就认为它是离线完整安装器。

已将脚本中的依赖安装命令放到另一个新 Python 3.10 虚拟环境中进行补充诊断。首次在构建依赖阶段遇到 setuptools>=61.0 无候选版本的错误；随后独立 pip index 控制检查能够读取该包版本。该现象不作为 MARA 缺少 setuptools 发布包的证据。

补充安装重试跨过了构建依赖阶段，进入运行依赖的解析与元数据下载，但出现重复的连接中断和续传。约 359 秒后结束了这项补充诊断；停止动作和进程身份单独记录在 launcher-retry-stop.json。该次退出是主动结束诊断，不能作为新的 MARA 安装缺陷，也不能作为成功安装的证据。标准 README 安装链路的两个已确认失败结论不受此项影响。

没有执行整个批处理安装器的 Miniconda/Portable Git 引导、关闭 TLS 校验的下载参数、缓存清理和自动模型安装。上述补充诊断不能替代整个批处理安装器的成功运行记录。

## 对投稿准备的影响

该 release URL 可以访问并提供真实文件，但本次结果不足以把“可安装且可完成问答”标记为已验证。优先需要一个经干净环境验证的安装路径：修正文档中不存在的包入口；为默认源码安装补齐 Windows 构建前提，或提供经过验证的依赖/安装包方案；然后重新验证启动、索引和一条带引用的问答。

已经准备了不含个人数据的测试文档，问题为 What is the review marker?，预期答案包含 ORCHID-7429。当前没有执行该问答，也没有模型调用费用或真实用户文档外传。本轮没有修改论文 PDF、Overleaf ZIP、软件源码或 GitHub release。

完整原始日志与隔离环境保留在 D:\MARA-reviewer-test\20260922T161319Z；关键日志及机器可读检查记录已归档到 audit/reviewer-install-2026-09-23。归档日志统一了换行和行末空白，原始文件及其 SHA-256 保留在检查清单中。
