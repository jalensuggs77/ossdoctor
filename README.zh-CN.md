# ossdoctor

[![ossdoctor score](https://img.shields.io/badge/ossdoctor-100%2F100-brightgreen)](https://github.com/jalensuggs77/ossdoctor)

[English](README.md)

**开源仓库的"体检"工具。** ossdoctor 检查维护者需要的文档、社区文件和自动化配置，
给仓库打出 0–100 分，并能自动生成缺失的文件。

- **快速、离线**：只读取工作区文件，不调用任何 API，不需要 token。
- **不只报问题，还能修**：`ossdoctor fix` 根据检测到的技术栈生成 LICENSE、
  贡献指南、安全策略、Issue 表单、Dependabot 配置、CI 工作流等，绝不覆盖已有文件。
  CI 工作流支持 Python（pip/uv/Poetry）、Node.js（npm/pnpm/Yarn/Bun）、Go、Rust 和 Java（Maven/Gradle），
  只调用项目里真实存在的脚本和测试。
- **适合 CI**：支持 Markdown（用于 Job Summary）、SARIF（用于 GitHub 代码扫描）、JSON 输出和 `--fail-under` 分数门槛。
- **零依赖**：只用 Python 标准库。

<p align="center">
  <img src="docs/images/check.svg" alt="ossdoctor 检查一个示例仓库，得分 50/100" width="820">
</p>

## 安装

```sh
pipx install ossdoctor      # 或者 pip install ossdoctor
```

需要 Python 3.11 及以上。

## 使用

```sh
ossdoctor                       # 检查当前目录
ossdoctor path/to/repo -v       # 显示每个失败项的修复建议
ossdoctor --format markdown     # 输出 Markdown 表格
ossdoctor --format json         # 输出 JSON
ossdoctor -f sarif -o ossdoctor.sarif   # 输出 SARIF，用于 GitHub 代码扫描
ossdoctor --fail-under 80       # 分数低于 80 时以状态码 1 退出

ossdoctor fix --dry-run         # 预览会生成哪些文件
ossdoctor fix --license MIT --email you@example.com --github-user 你的用户名

ossdoctor badge                 # 生成显示分数的 README 徽章
ossdoctor list                  # 列出所有检查项
```

生成的文件只是起点，提交前请检查并补充项目相关的内容。

### 分数徽章

`ossdoctor badge` 会输出一个显示当前分数的徽章，可以直接贴进 README。徽章只是一张图片，分数不会自己更新，
可以用 `ossdoctor badge --update README.md` 把 README 里的分数改成最新的；
在 CI 里加上 `--check`，徽章过时就会报错。

### GitHub Action

```yaml
- uses: actions/checkout@v7
- uses: jalensuggs77/ossdoctor@v0.3.0
  with:
    fail-under: "80"
```

### GitHub 代码扫描

给 Action 加上 `sarif-file: ossdoctor.sarif`，再用 `github/codeql-action/upload-sarif@v4` 上传，
检查结果就会出现在仓库的 **Security → Code scanning** 里，PR 中新出现的问题也会被标出来。
完整示例见 [英文 README](README.md#github-code-scanning)。

## 配置

在 `pyproject.toml` 中添加 `[tool.ossdoctor]`，或创建 `.ossdoctor.toml`：

```toml
[tool.ossdoctor]
disable = ["codeowners"]
fail-under = 80
large-file-mb = 10
ignore-paths = ["tests/fixtures/*"]
```

完整的检查项列表、评分规则和路线图见 [英文 README](README.md)。

## 参与贡献

欢迎提交 Issue 和 PR，详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 许可证

[MIT](LICENSE)
